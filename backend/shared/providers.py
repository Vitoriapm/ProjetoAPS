from datetime import timedelta, datetime, timezone
import math
from uuid import UUID, uuid5
import httpx
from shapely.geometry import shape, Point, mapping
from shapely.ops import unary_union
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from .db import environment, utc_now, iso, parse_time
from .domain import make_event, save_event
from .geo import circle_polygon, distance_m, geohash

NAMESPACE = UUID("8c842f7a-9518-4ac7-bf01-6b57420510e0")


class ProviderUnavailable(Exception):
    pass


class RouteRejected(Exception):
    pass


def observation_upsert(key, feature, *, postgres):
    # Existence SELECT + INSERT races between separate API processes. Let the
    # database resolve the unique key atomically, in the same outbox transaction.
    insert = postgresql_insert if postgres else sqlite_insert
    statement = insert(environment).values(id=key, data=feature)
    return statement.on_conflict_do_update(index_elements=[environment.c.id],
        set_={"data": statement.excluded.data})


def fixture_layers(now=None):
    now = now or utc_now()
    expires = iso(now + timedelta(minutes=30))
    features = []
    for kind, lat, lon, value, unit, scale in [
        ("aqi", -21.1775, -47.8101, 58, "AQI", "US AQI: 0–50 boa; 51–100 moderada; >100 piora progressiva"),
        ("calor", -21.1908, -47.8236, 3.2, "°C", "Diferença térmica didática, sem medição real"),
        ("calor", -21.1668, -47.8000, 1.8, "°C", "Diferença térmica didática, sem medição real")]:
        feature_id = str(uuid5(NAMESPACE, kind + str(lat)))
        features.append({"type": "Feature", "id": feature_id,
            "geometry": {"type": "Point", "coordinates": [lon, lat]} if kind == "aqi" else circle_polygon(lat, lon, 550),
            "properties": {"id": feature_id, "kind": kind, "value": value, "unit": unit,
                "scale": scale, "source": "Fixture acadêmica EcoPulse — Ribeirão Preto",
                "updated_at": iso(now), "expires_at": expires, "is_demo": True,
                "label": "Dados simulados para demonstração"}})
    return features


async def environmental_layers(store, settings, latitude, longitude, client=None):
    fixtures = fixture_layers()
    if settings.mode == "demo" or settings.environment_source == "fixtures":
        return {"type": "FeatureCollection", "features": fixtures, "mode": "demo" if settings.mode == "demo" else "fixtures"}
    now = utc_now()
    region = geohash(latitude, longitude)
    key = "aqi:" + region
    with store.engine.connect() as conn:
        previous = conn.execute(select(environment.c.data).where(environment.c.id == key)).scalar_one_or_none()
    if previous and parse_time(previous["properties"]["expires_at"]) > now:
        return {"type": "FeatureCollection", "features": [previous] + [x for x in fixtures if x["properties"]["kind"] == "calor"]}
    owned = client is None
    client = client or httpx.AsyncClient(timeout=12)
    try:
        response = await client.get("https://air-quality-api.open-meteo.com/v1/air-quality", params={
            "latitude": latitude, "longitude": longitude, "current": "us_aqi", "domains": "cams_global", "timezone": "UTC"})
        response.raise_for_status()
        payload = response.json()
        current = payload["current"]
        value = current["us_aqi"]
        # Open-Meteo documents US AQI values beyond 500; do not suppress a
        # valid severe value. Reject missing, negative and non-finite values.
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError("AQI fora da escala suportada")
        grid_latitude, grid_longitude = payload["latitude"], payload["longitude"]
        for coordinate, lower, upper in [(grid_latitude, -90, 90), (grid_longitude, -180, 180)]:
            if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)) or not math.isfinite(coordinate) or not lower <= coordinate <= upper:
                raise ValueError("Coordenada de grade inválida")
        observed = datetime.fromisoformat(current["time"]).replace(tzinfo=timezone.utc)
        if observed < now - timedelta(hours=3) or observed > now + timedelta(minutes=30):
            raise ValueError("Fonte retornou horário fora da validade")
        feature_id = str(uuid5(NAMESPACE, key))
        feature = {"type": "Feature", "id": feature_id,
            "geometry": {"type": "Point", "coordinates": [grid_longitude, grid_latitude]},
            "properties": {"id": feature_id, "kind": "aqi", "value": value, "unit": "AQI", "scale": "US AQI",
                "source": "Open-Meteo / Copernicus CAMS Global (~45 km), previsão modelada",
                "updated_at": iso(observed), "expires_at": iso(now + timedelta(minutes=15)),
                "is_demo": False, "label": "AQI modelado; não é medição de estação local",
                "attribution": "CAMS ENSEMBLE / Open-Meteo, CC BY 4.0"}}
        with store.transaction() as conn:
            conn.execute(observation_upsert(key, feature, postgres=store.pg))
            event = make_event("camada.atualizada", feature_id, int(now.timestamp()), region, feature)
            save_event(conn, event, settings.shard_count)
        return {"type": "FeatureCollection", "features": [feature] + [x for x in fixtures if x["properties"]["kind"] == "calor"]}
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        raise ProviderUnavailable("Não foi possível consultar a qualidade do ar. Tente novamente.") from exc
    finally:
        if owned:
            await client.aclose()


async def calculate_route(store, settings, request, client=None):
    if not settings.ors_key:
        raise ProviderUnavailable("Rotas aguardam a configuração da chave do OpenRouteService no servidor.")
    if distance_m(request.origem.latitude, request.origem.longitude, request.destino.latitude, request.destino.longitude) > 50000:
        raise RouteRejected("Escolha um destino até 50 km da origem para esta demonstração.")
    features = store.active_features()
    polygons = [shape(feature["geometry"]) for feature in features]
    if any(not polygon.is_valid for polygon in polygons):
        raise RouteRejected("Há uma geometria de bloqueio inválida; o cálculo foi interrompido.")
    start = Point(request.origem.longitude, request.origem.latitude)
    end = Point(request.destino.longitude, request.destino.latitude)
    if any(polygon.intersects(start) or polygon.intersects(end) for polygon in polygons):
        raise RouteRejected("A origem ou o destino está dentro de uma ocorrência registrada. Escolha outro ponto.")
    payload = {"coordinates": [[start.x, start.y], [end.x, end.y]], "instructions": False}
    if polygons:
        # Union removes overlaps; every active polygon remains excluded.
        payload["options"] = {"avoid_polygons": mapping(unary_union(polygons))}
    owned = client is None
    client = client or httpx.AsyncClient(timeout=20)
    try:
        response = await client.post(f"https://api.openrouteservice.org/v2/directions/{request.perfil}/geojson",
            json=payload, headers={"Authorization": settings.ors_key})
        if response.status_code in {400, 404, 422}:
            raise RouteRejected("Não foi encontrada uma rota que evite as ocorrências registradas.")
        response.raise_for_status()
        data = response.json()
        route = data["features"][0]
        geometry = route["geometry"]
        line = shape(geometry)
        if geometry["type"] != "LineString" or line.is_empty or not line.is_valid:
            raise RouteRejected("O provedor retornou uma rota inválida.")
        if any(line.intersects(polygon) for polygon in polygons):
            raise RouteRejected("A rota retornada cruza uma ocorrência. Nenhuma rota foi apresentada.")
        summary = route["properties"]["summary"]
        for value in (summary["distance"], summary["duration"]):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError("Resumo de rota inválido")
        return {"geometry": geometry, "distance_m": summary["distance"], "duration_s": summary["duration"],
            "avoided_incidents": len(features), "source": "OpenRouteService / OpenStreetMap",
            "updated_at": iso(utc_now()), "label": "Rota alternativa evitando ocorrências registradas"}
    except RouteRejected:
        raise
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise ProviderUnavailable("O serviço de rotas está indisponível. Tente novamente.") from exc
    finally:
        if owned:
            await client.aclose()
