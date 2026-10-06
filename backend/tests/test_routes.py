import asyncio
import copy
import json
from types import SimpleNamespace

import httpx
import pytest

from backend.shared.geo import circle_polygon
from backend.shared.models import RouteRequest
from backend.shared.routes import calculate_route, ProviderUnavailable, RouteRejected


def request(profile="driving-car"):
    return RouteRequest.model_validate({"origem": {"latitude": -21.1875, "longitude": -47.8101},
        "destino": {"latitude": -21.1675, "longitude": -47.8101}, "perfil": profile})


def feature(latitude=-21.1775, longitude=-47.8101):
    return {"geometry": circle_polygon(latitude, longitude, 200)}


def response():
    return {"features": [{"geometry": {"type": "LineString", "coordinates": [
        [-47.8101, -21.1875], [-47.82, -21.1875], [-47.82, -21.1675], [-47.8101, -21.1675]]},
        "properties": {"summary": {"distance": 4100, "duration": 550}}}]}


def run(handler, *, features=None, route=None, key="dummy-test-key", store=None):
    store = store or SimpleNamespace(active_features=lambda: features or [])
    async def execute():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await calculate_route(store, SimpleNamespace(ors_key=key), route or request(), client)
    return asyncio.run(execute())


@pytest.mark.parametrize("profile", ["driving-car", "foot-walking"])
def test_real_ors_post_contract_keeps_all_disjoint_and_overlapping_blocks(profile):
    from shapely.geometry import shape
    blocks = [feature(), feature(-21.1775, -47.8085), feature(-21.175, -47.802)]
    def provider(req):
        assert req.method == "POST"
        assert str(req.url) == f"https://api.openrouteservice.org/v2/directions/{profile}/geojson"
        assert req.headers["Authorization"] == "dummy-test-key"
        payload = json.loads(req.content)
        assert payload["coordinates"] == [[-47.8101, -21.1875], [-47.8101, -21.1675]]
        assert payload["radiuses"] == [200, 200]
        assert not payload["instructions"]
        excluded = shape(payload["options"]["avoid_polygons"])
        # GEOS computes intersection vertices with floating point arithmetic.
        assert all(excluded.buffer(1e-10).covers(shape(block["geometry"])) for block in blocks)
        return httpx.Response(200, json=response())
    result = run(provider, features=blocks, route=request(profile))
    assert result["avoided_incidents"] == 3
    assert result["source"] == "OpenRouteService / OpenStreetMap"


def test_no_incidents_does_not_send_empty_avoidance():
    def provider(req):
        assert "options" not in json.loads(req.content)
        return httpx.Response(200, json=response())
    assert run(provider)["avoided_incidents"] == 0


@pytest.mark.parametrize("bad", [
    {"type": "Point", "coordinates": [-47.81, -21.17]},
    {"type": "Polygon", "coordinates": []},
    {"type": "MultiPolygon", "coordinates": []},
    {"type": "Polygon", "coordinates": [[[-47.81, -21.17], [-47.82, -21.17], [-47.82, -21.18]]]},
    {"type": "Polygon", "coordinates": [[[181, -21.17], [-47.82, -21.17], [-47.82, -21.18], [181, -21.17]]]},
    {"type": "Polygon", "coordinates": [[[True, -21.17], [-47.82, -21.17], [-47.82, -21.18], [True, -21.17]]]},
    {"type": "Polygon", "coordinates": [[[-47.8, -21.17], [-47.82, -21.18], [-47.82, -21.17], [-47.8, -21.18], [-47.8, -21.17]]]},
])
def test_invalid_block_stops_before_any_network_request(bad):
    def no_network(req):
        pytest.fail("Invalid block must never be dropped before routing")
    with pytest.raises(RouteRejected, match="bloqueio inválida"):
        run(no_network, features=[{"geometry": bad}])


@pytest.mark.parametrize("coordinates", [[], [[-47.81, -21.18]], [[-47.81, -21.18], [181, -21.17]],
    [[-47.81, -21.18], [-47.81, 91]], [[-47.81, -21.18], [True, -21.17]],
    [[-47.81, -21.18], [-47.81, "-21.17"]], [[-47.81, -21.18, 0], [-47.81, -21.17, 0]],
    [[-47.81, -21.18], [-47.81, -21.18]]])
def test_invalid_line_coordinates_are_never_presented(coordinates):
    data = response()
    data["features"][0]["geometry"]["coordinates"] = coordinates
    with pytest.raises(RouteRejected, match="inválida"):
        run(lambda req: httpx.Response(200, json=data))


def test_nonfinite_json_coordinate_is_rejected():
    data = response()
    data["features"][0]["geometry"]["coordinates"][0][0] = float("nan")
    with pytest.raises(RouteRejected, match="inválida"):
        run(lambda req: httpx.Response(200, content=json.dumps(data).encode()))


@pytest.mark.parametrize("value", [None, True, -1, "550", float("nan"), float("inf")])
def test_invalid_duration_is_not_presented(value):
    data = response()
    data["features"][0]["properties"]["summary"]["duration"] = value
    with pytest.raises(ProviderUnavailable, match="indisponível"):
        run(lambda req: httpx.Response(200, content=json.dumps(data).encode()))


@pytest.mark.parametrize("data", [{}, {"features": []}, {"features": [None]},
    {"features": [{"geometry": None}]}, {"features": [{"geometry": {"type": "LineString"}}]}])
def test_malformed_ors_response_returns_unavailable(data):
    with pytest.raises(ProviderUnavailable, match="indisponível"):
        run(lambda req: httpx.Response(200, json=data))


def test_unrelated_route_cannot_be_returned_even_when_it_avoids_incidents():
    data = response()
    data["features"][0]["geometry"]["coordinates"] = [[-47.82, -21.2], [-47.82, -21.19]]
    with pytest.raises(RouteRejected, match="origem e ao destino"):
        run(lambda req: httpx.Response(200, json=data), features=[feature()])


def test_snapped_access_segment_cannot_cross_block():
    data = response()
    data["features"][0]["geometry"]["coordinates"][0] = [-47.8101, -21.1862]
    block = {"geometry": circle_polygon(-21.18685, -47.8101, 20)}
    with pytest.raises(RouteRejected, match="cruza"):
        run(lambda req: httpx.Response(200, json=data), features=[block])


def test_incident_created_during_provider_request_is_checked_before_return():
    blocks = []
    def provider(req):
        blocks.append(feature(-21.1875, -47.815))
        return httpx.Response(200, json=response())
    with pytest.raises(RouteRejected, match="cruza"):
        run(provider, store=SimpleNamespace(active_features=lambda: copy.deepcopy(blocks)))


@pytest.mark.parametrize("status,message,exception", [(401, "chave válida", ProviderUnavailable),
    (403, "chave válida", ProviderUnavailable), (429, "limite", ProviderUnavailable),
    (400, "Não foi encontrada", RouteRejected), (404, "Não foi encontrada", RouteRejected),
    (422, "Não foi encontrada", RouteRejected), (503, "indisponível", ProviderUnavailable)])
def test_provider_error_is_explicit_and_never_retries_without_exclusions(status, message, exception):
    calls = []
    def provider(req):
        calls.append(json.loads(req.content))
        return httpx.Response(status)
    with pytest.raises(exception, match=message):
        run(provider, features=[feature()])
    assert len(calls) == 1 and "avoid_polygons" in calls[0]["options"]


def test_timeout_has_clear_message_and_no_unrestricted_retry():
    calls = []
    def provider(req):
        calls.append(req)
        raise httpx.ReadTimeout("controlled timeout", request=req)
    with pytest.raises(ProviderUnavailable, match="demorou demais"):
        run(provider, features=[feature()])
    assert len(calls) == 1


@pytest.mark.parametrize("key", ["", "   "])
def test_missing_key_never_calls_provider(key):
    def no_network(req):
        pytest.fail("Missing key must not cause a provider call")
    with pytest.raises(ProviderUnavailable, match="configuração"):
        run(no_network, key=key)


def test_same_origin_and_destination_is_rejected_without_network():
    data = request().model_dump()
    data["destino"] = data["origem"]
    with pytest.raises(RouteRejected, match="diferente"):
        run(lambda req: pytest.fail("No network expected"), route=RouteRequest.model_validate(data))


def test_over_50_km_is_rejected_without_network():
    data = request().model_dump()
    data["destino"] = {"latitude": -22.18, "longitude": -47.81}
    with pytest.raises(RouteRejected, match="50 km"):
        run(lambda req: pytest.fail("No network expected"), route=RouteRequest.model_validate(data))
