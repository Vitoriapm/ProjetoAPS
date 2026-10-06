from datetime import timedelta, datetime, timezone
import math
from copy import deepcopy
from uuid import UUID, uuid5
import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from .db import environment, utc_now, iso, parse_time
from .domain import make_event, save_event
from .geo import circle_polygon, distance_m, geohash

NAMESPACE = UUID("8c842f7a-9518-4ac7-bf01-6b57420510e0")


from .routes import calculate_route, ProviderUnavailable, RouteRejected
from .heat import heat_layers, HeatDataError


def observation_upsert(key, feature, *, postgres):
    # Existence SELECT + INSERT races between separate API processes. Let the
    # database resolve the unique key atomically, in the same outbox transaction.
    insert = postgresql_insert if postgres else sqlite_insert
    statement = insert(environment).values(id=key, data=feature)
    return statement.on_conflict_do_update(index_elements=[environment.c.id],
        set_={"data": statement.excluded.data})


def fixture_layers(now=None):
    now = now or utc_now()
    # Stable examples during a 30-minute window; repeated reads do not create
    # new layer events or renew their validity indefinitely.
    now = datetime.fromtimestamp(int(now.timestamp()) // 1800 * 1800, timezone.utc)
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
                "center_latitude": lat, "center_longitude": lon,
                "radius_m": 550 if kind == "calor" else 0,
                "label": "Dados simulados para demonstração"}})
    return features



def _same_observation(left, right):
    def content(feature):
        clone = deepcopy(feature)
        for key in ("expires_at", "version"):
            clone["properties"].pop(key, None)
        return clone
    return content(left) == content(right)


def persist_environment_features(store, features):
    """Store observations and versioned events together, retaining valid TTLs.

    Postgres advisory locking serializes initial writes between API processes.
    The actual key insert still uses upsert for existing SQLite/legacy stores.
    """
    result = []
    with store.transaction(risk_lock=True) as connection:
        for raw in features:
            feature = deepcopy(raw)
            props = feature["properties"]
            region = props.get("region_id")
            if not region:
                if "center_latitude" in props:
                    region = geohash(props["center_latitude"], props["center_longitude"])
                else:
                    lon, lat = feature["geometry"]["coordinates"]
                    region = geohash(lat, lon)
                props["region_id"] = region
            key = ("aqi:" + region if props["kind"] == "aqi" and not props["is_demo"]
                   else ("fixture:" if props["is_demo"] else "") + props["kind"] + ":" + props["id"])
            previous = connection.execute(select(environment.c.data).where(environment.c.id == key)).scalar_one_or_none()
            now = utc_now()
            if (previous and previous["properties"].get("version")
                    and parse_time(previous["properties"]["expires_at"]) > now
                    and _same_observation(previous, feature)):
                result.append(previous)
                continue
            previous_version = previous["properties"].get("version", 0) if previous else 0
            props["version"] = max(int(now.timestamp() * 1_000_000), previous_version + 1)
            connection.execute(observation_upsert(key, feature, postgres=store.pg))
            event = make_event("camada.atualizada", props["id"], props["version"], region, feature)
            save_event(connection, event, store.settings.shard_count)
            result.append(feature)
    return result


async def environmental_layers(store, settings, latitude, longitude, client=None):
    fixtures = fixture_layers()
    if settings.environment_source == "fixtures":
        features = persist_environment_features(store, fixtures)
        return {"type": "FeatureCollection", "features": features, "mode": "fixtures"}
    try:
        heat = heat_layers(path=getattr(settings, "heat_file", "") or None)
    except HeatDataError as exc:
        raise ProviderUnavailable(str(exc)) from exc
    if settings.mode == "demo":
        # AQI remains a labelled fixture in the offline presentation mode.
        # Landsat is an actual archived acquisition, explicitly historical.
        features = persist_environment_features(store, [fixtures[0]] + heat)
        return {"type": "FeatureCollection", "features": features, "mode": "demo"}
    now = utc_now()
    region = geohash(latitude, longitude)
    key = "aqi:" + region
    with store.engine.connect() as connection:
        previous = connection.execute(select(environment.c.data).where(environment.c.id == key)).scalar_one_or_none()
    if (previous and not previous["properties"]["is_demo"]
            and parse_time(previous["properties"]["expires_at"]) > now):
        return {"type": "FeatureCollection", "features": [previous] + persist_environment_features(store, heat)}
    owned = client is None
    client = client or httpx.AsyncClient(timeout=12)
    try:
        response = await client.get("https://air-quality-api.open-meteo.com/v1/air-quality", params={
            "latitude": latitude, "longitude": longitude, "current": "us_aqi", "domains": "cams_global", "timezone": "UTC"})
        response.raise_for_status()
        payload = response.json()
        current = payload["current"]
        value = current["us_aqi"]
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
                "region_id": region, "is_demo": False, "label": "AQI modelado; não é medição de estação local",
                "attribution": "CAMS ENSEMBLE / Open-Meteo, CC BY 4.0"}}
        return {"type": "FeatureCollection", "features": persist_environment_features(store, [feature] + heat)}
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        raise ProviderUnavailable("Não foi possível consultar a qualidade do ar. Tente novamente.") from exc
    finally:
        if owned:
            await client.aclose()
