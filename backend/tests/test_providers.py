import asyncio
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy import select
import httpx
import pytest
from backend.shared.config import Settings
from backend.shared.db import Store, devices, iso, utc_now
from backend.shared.domain import ingest, process_report
from backend.shared.models import RelatoRequest, RouteRequest
from backend.shared.providers import calculate_route, environmental_layers, ProviderUnavailable, RouteRejected
from backend.alerts.main import geographic_devices, FcmAdapter


def store(tmp_path):
    config = Settings(mode="demo", database_url="sqlite:///" + str(tmp_path / "providers.db"), ors_key="dummy-test-key")
    config.validate()
    repository = Store(config)
    repository.initialize()
    return repository, config


def add_incident(repository):
    request = RelatoRequest.model_validate({"id": str(uuid4()), "tipo": "obstrucao", "gravidade": "alta",
        "latitude": -21.1775, "longitude": -47.8101, "occurred_at": iso(utc_now()), "is_demo": True})
    _, _, event = ingest(repository, request, str(uuid4()))
    process_report(repository, event)
    return repository.active_features()[0]


def request():
    return RouteRequest.model_validate({"origem": {"latitude": -21.1875, "longitude": -47.8101},
        "destino": {"latitude": -21.1675, "longitude": -47.8101}, "perfil": "driving-car"})


def test_route_preserves_all_polygons_and_rejects_intersection(tmp_path):
    repository, config = store(tmp_path)
    add_incident(repository)
    captured = []
    def provider(req):
        import json
        captured.append(json.loads(req.content))
        return httpx.Response(200, json={"features": [{"geometry": {"type": "LineString",
            "coordinates": [[-47.8101, -21.1875], [-47.8101, -21.1675]]},
            "properties": {"summary": {"distance": 2300, "duration": 400}}}]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as client:
            with pytest.raises(RouteRejected, match="cruza"):
                await calculate_route(repository, config, request(), client)
    asyncio.run(run())
    assert captured[0]["options"]["avoid_polygons"]["type"] == "Polygon"


def test_route_accepts_actual_nonintersecting_line(tmp_path):
    repository, config = store(tmp_path)
    add_incident(repository)
    def provider(req):
        return httpx.Response(200, json={"features": [{"geometry": {"type": "LineString",
            "coordinates": [[-47.8101, -21.1875], [-47.82, -21.1875], [-47.82, -21.1675], [-47.8101, -21.1675]]},
            "properties": {"summary": {"distance": 4100, "duration": 550}}}]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as client:
            return await calculate_route(repository, config, request(), client)
    route = asyncio.run(run())
    assert route["avoided_incidents"] == 1 and route["distance_m"] == 4100


def test_origin_inside_incident_never_calls_provider(tmp_path):
    repository, config = store(tmp_path)
    add_incident(repository)
    data = request().model_dump()
    data["origem"] = {"latitude": -21.1775, "longitude": -47.8101}
    with pytest.raises(RouteRejected, match="dentro"):
        asyncio.run(calculate_route(repository, config, RouteRequest.model_validate(data)))


def test_provider_failure_never_removes_avoidance(tmp_path):
    repository, config = store(tmp_path)
    add_incident(repository)
    calls = []
    def provider(req):
        calls.append(req)
        return httpx.Response(503)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as client:
            with pytest.raises(ProviderUnavailable):
                await calculate_route(repository, config, request(), client)
    asyncio.run(run())
    assert len(calls) == 1 and b"avoid_polygons" in calls[0].content


def test_open_meteo_is_modelled_aqi_and_landsat_heat_remains_historical(tmp_path):
    repository, config = store(tmp_path)
    config.mode = "full"  # Provider branch only; no infrastructure validation implied.
    def provider(req):
        assert req.url.params["domains"] == "cams_global"
        return httpx.Response(200, json={"latitude": -21.2, "longitude": -47.8,
            "current": {"time": utc_now().replace(tzinfo=None).isoformat(timespec="minutes"), "us_aqi": 61}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as client:
            return await environmental_layers(repository, config, -21.1775, -47.8101, client)
    collection = asyncio.run(run())
    aqi = collection["features"][0]["properties"]
    assert aqi["value"] == 61 and not aqi["is_demo"]
    assert "modelada" in aqi["source"] and "estação local" in aqi["label"]
    assert all(not x["properties"]["is_demo"] and x["properties"]["observation_type"] == "historic"
        and "não representa o calor atual" in x["properties"]["label"] for x in collection["features"][1:])


def test_aqi_failure_does_not_silently_switch_to_fiction(tmp_path):
    repository, config = store(tmp_path)
    config.mode = "full"
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(503))) as client:
            with pytest.raises(ProviderUnavailable):
                await environmental_layers(repository, config, -21.1775, -47.8101, client)
    asyncio.run(run())


def test_push_selects_neighbor_nearby_only_with_valid_last_position(tmp_path):
    repository, _ = store(tmp_path)
    feature = add_incident(repository)
    now = utc_now()
    with repository.transaction() as conn:
        for label, lat, position_at in [("near", -21.1776, now), ("far", -21.28, now), ("stale", -21.1776, now - timedelta(hours=2))]:
            conn.execute(devices.insert().values(id=label, data={"token": "x" * 100, "platform": "android",
                "latitude": lat, "longitude": -47.8102, "position_at": iso(position_at), "radius_m": 1000}))
    assert [x["id"] for x in geographic_devices(repository, feature, now)] == ["near"]


def test_unconfigured_fcm_explicitly_fails(tmp_path):
    _, config = store(tmp_path)
    with pytest.raises(RuntimeError, match="não configurado"):
        FcmAdapter(config).send("test-token", {})


@pytest.mark.parametrize("is_demo", [True, False])
def test_fcm_notification_text_identifies_simulation_before_app_opens(tmp_path, is_demo):
    repository, config = store(tmp_path)
    feature = add_incident(repository)
    feature["properties"]["is_demo"] = is_demo
    event = {"event_id": str(uuid4()), "payload": feature}
    config.fcm_credentials = "not-opened-by-mocked-certificate.json"
    with patch("backend.alerts.main.credentials.Certificate"), \
         patch("backend.alerts.main.firebase_admin.initialize_app", return_value=object()), \
         patch("backend.alerts.main.messaging.send", return_value="mock-provider-id") as send:
        assert FcmAdapter(config).send("mock-device-token", event) == "mock-provider-id"
    message = send.call_args.args[0]
    assert message.data["is_demo"] == str(is_demo).lower()
    assert message.data["incident_id"] == feature["properties"]["id"]
    assert 0 < message.android.ttl.total_seconds() <= 1800
    if is_demo:
        assert "demonstração" in message.notification.title
        assert "simulado" in message.notification.body
        assert "fictícia" in message.notification.body
    else:
        assert message.notification.title == "EcoPulse"
        assert message.notification.body == "Há uma ocorrência registrada perto de você."


@pytest.mark.parametrize("value", [510, 0, 61.5])
def test_aqi_accepts_supported_numeric_values_including_above_500(tmp_path, value):
    repository, config = store(tmp_path)
    config.mode = "full"
    response = {"latitude": -21.2, "longitude": -47.8,
        "current": {"time": utc_now().replace(tzinfo=None).isoformat(timespec="minutes"), "us_aqi": value}}
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response))) as client:
            return await environmental_layers(repository, config, -21.1775, -47.8101, client)
    collection = asyncio.run(run())
    assert collection["features"][0]["properties"]["value"] == value
    assert not collection["features"][0]["properties"]["is_demo"]


@pytest.mark.parametrize("field,value", [("us_aqi", None), ("us_aqi", True), ("us_aqi", -1),
    ("latitude", None), ("latitude", True), ("latitude", 91), ("longitude", 181)])
def test_aqi_rejects_invalid_provider_payload_without_poisoning_cache(tmp_path, field, value):
    repository, config = store(tmp_path)
    config.mode = "full"
    response = {"latitude": -21.2, "longitude": -47.8,
        "current": {"time": utc_now().replace(tzinfo=None).isoformat(timespec="minutes"), "us_aqi": 61}}
    if field == "us_aqi":
        response["current"][field] = value
    else:
        response[field] = value
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response))) as client:
            with pytest.raises(ProviderUnavailable):
                await environmental_layers(repository, config, -21.1775, -47.8101, client)
    asyncio.run(run())
    from backend.shared.db import environment
    with repository.engine.connect() as conn:
        assert conn.execute(select(environment.c.id)).first() is None


@pytest.mark.parametrize("value", [None, True, -1, "2300"])
def test_route_rejects_invalid_provider_summary_without_presenting_geometry(tmp_path, value):
    repository, config = store(tmp_path)
    response = {"features": [{"geometry": {"type": "LineString",
        "coordinates": [[-47.8101, -21.1875], [-47.8101, -21.1675]]},
        "properties": {"summary": {"distance": value, "duration": 400}}}]}
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response))) as client:
            with pytest.raises(ProviderUnavailable):
                await calculate_route(repository, config, request(), client)
    asyncio.run(run())
