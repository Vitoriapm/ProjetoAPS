"""Real ORS routing, with every active incident kept in the exclusion set."""
import math

import httpx
from shapely.errors import GEOSException
from shapely.geometry import LineString, Point, mapping, shape
from shapely.ops import unary_union

from .db import iso, utc_now
from .geo import distance_m


ORS_URL = "https://api.openrouteservice.org/v2/directions"
SNAP_RADIUS_M = 200
MAX_DISTANCE_M = 50000


class ProviderUnavailable(Exception):
    pass


class RouteRejected(Exception):
    pass


def _number(value, lower, upper):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
        and math.isfinite(value) and lower <= value <= upper)


def _position(value):
    return (isinstance(value, (list, tuple)) and len(value) == 2
        and _number(value[0], -180, 180) and _number(value[1], -90, 90))


def _polygons(features):
    result = []
    try:
        for feature in features:
            geometry = feature["geometry"]
            if not isinstance(geometry, dict) or geometry.get("type") not in {"Polygon", "MultiPolygon"}:
                raise ValueError("Tipo de bloqueio inválido")
            polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
            if not isinstance(polygons, (list, tuple)) or not polygons:
                raise ValueError("Bloqueio vazio")
            for rings in polygons:
                if not isinstance(rings, (list, tuple)) or not rings:
                    raise ValueError("Bloqueio vazio")
                for ring in rings:
                    if (not isinstance(ring, (list, tuple)) or len(ring) < 4
                        or any(not _position(coordinate) for coordinate in ring) or ring[0] != ring[-1]):
                        raise ValueError("Anel de bloqueio inválido")
            polygon = shape(geometry)
            if polygon.is_empty or not polygon.is_valid:
                raise ValueError("Bloqueio inválido")
            result.append(polygon)
    except (KeyError, TypeError, ValueError, GEOSException) as exc:
        raise RouteRejected("Há uma geometria de bloqueio inválida; o cálculo foi interrompido.") from exc
    return result


def _route_line(data):
    route = data["features"][0]
    geometry = route["geometry"]
    coordinates = geometry["coordinates"]
    if (geometry["type"] != "LineString" or not isinstance(coordinates, (list, tuple))
        or len(coordinates) < 2 or any(not _position(coordinate) for coordinate in coordinates)):
        raise RouteRejected("O provedor retornou uma rota inválida.")
    line = LineString(coordinates)
    if line.is_empty or not line.is_valid or line.length == 0:
        raise RouteRejected("O provedor retornou uma rota inválida.")
    summary = route["properties"]["summary"]
    for value in (summary["distance"], summary["duration"]):
        if not _number(value, 0, math.inf):
            raise ValueError("Resumo de rota inválido")
    return geometry, line, summary


async def calculate_route(store, settings, request, client=None):
    if not settings.ors_key or not settings.ors_key.strip():
        raise ProviderUnavailable("Rotas aguardam a configuração da chave do OpenRouteService no servidor.")
    if request.perfil not in {"driving-car", "foot-walking"}:
        raise RouteRejected("Escolha uma rota de carro ou a pé.")
    start = Point(request.origem.longitude, request.origem.latitude)
    end = Point(request.destino.longitude, request.destino.latitude)
    if not _position([start.x, start.y]) or not _position([end.x, end.y]):
        raise RouteRejected("Informe coordenadas válidas para a origem e o destino.")
    separation = distance_m(start.y, start.x, end.y, end.x)
    if separation > MAX_DISTANCE_M:
        raise RouteRejected("Escolha um destino até 50 km da origem para esta demonstração.")
    if separation < 1:
        raise RouteRejected("Escolha um destino diferente da origem.")
    features = store.active_features()
    polygons = _polygons(features)
    if any(polygon.intersects(start) or polygon.intersects(end) for polygon in polygons):
        raise RouteRejected("A origem ou o destino está dentro de uma ocorrência registrada. Escolha outro ponto.")
    payload = {"coordinates": [[start.x, start.y], [end.x, end.y]], "instructions": False,
        "radiuses": [SNAP_RADIUS_M, SNAP_RADIUS_M]}
    if polygons:
        # Never discard an incident to satisfy provider limits or find a route.
        payload["options"] = {"avoid_polygons": mapping(unary_union(polygons))}
    owned = client is None
    client = client or httpx.AsyncClient(timeout=20)
    try:
        response = await client.post(f"{ORS_URL}/{request.perfil}/geojson", json=payload,
            headers={"Authorization": settings.ors_key}, timeout=20)
        if response.status_code in {401, 403}:
            raise ProviderUnavailable("O servidor precisa de uma chave válida do OpenRouteService para calcular rotas.")
        if response.status_code == 429:
            raise ProviderUnavailable("O limite de consultas de rotas foi atingido. Tente novamente mais tarde.")
        if response.status_code in {400, 404, 422}:
            raise RouteRejected("Não foi encontrada uma rota que evite as ocorrências registradas.")
        response.raise_for_status()
        geometry, line, summary = _route_line(response.json())
        snapped_start, snapped_end = line.coords[0], line.coords[-1]
        if (distance_m(start.y, start.x, snapped_start[1], snapped_start[0]) > SNAP_RADIUS_M
            or distance_m(end.y, end.x, snapped_end[1], snapped_end[0]) > SNAP_RADIUS_M):
            raise RouteRejected("A rota retornada não corresponde à origem e ao destino escolhidos.")
        # ORS snaps to nearby streets. Check these small access segments too.
        access = [LineString([start.coords[0], snapped_start]), LineString([snapped_end, end.coords[0]])]
        # An incident may arrive while the network request is running.
        current_polygons = polygons + _polygons(store.active_features())
        if any(line.intersects(polygon) or any(segment.intersects(polygon) for segment in access)
            for polygon in current_polygons):
            raise RouteRejected("A rota retornada cruza uma ocorrência. Nenhuma rota foi apresentada.")
        return {"geometry": geometry, "distance_m": summary["distance"], "duration_s": summary["duration"],
            "avoided_incidents": len(features), "source": "OpenRouteService / OpenStreetMap",
            "updated_at": iso(utc_now()), "label": "Rota alternativa evitando ocorrências registradas"}
    except (ProviderUnavailable, RouteRejected):
        raise
    except httpx.TimeoutException as exc:
        raise ProviderUnavailable("O cálculo da rota demorou demais. Tente novamente.") from exc
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, GEOSException) as exc:
        raise ProviderUnavailable("O serviço de rotas está indisponível. Tente novamente.") from exc
    finally:
        if owned:
            await client.aclose()
