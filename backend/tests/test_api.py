from uuid import uuid4
from fastapi.testclient import TestClient
from backend.api.main import create_app
from backend.shared.config import Settings
from backend.shared.db import iso, utc_now
import pytest


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(mode="demo", database_url="sqlite:///" + str(tmp_path / "api.db")))
    with TestClient(app) as client:
        yield client


def headers(client):
    response = client.post("/v1/sessoes", json={"installation_id": str(uuid4())})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def payload():
    return {"id": str(uuid4()), "tipo": "alagamento", "gravidade": "baixa", "latitude": -21.1775,
        "longitude": -47.8101, "occurred_at": iso(utc_now()), "position_source": "manual", "is_demo": True}


def test_empty_get_health_mode_and_no_fake_route(client):
    assert client.get("/v1/relatos").json() == []
    health = client.get("/health").json()
    assert health["mode"] == "demo" and health["status"] == "ok"
    route = client.post("/v1/rotas", headers=headers(client), json={"origem": {"latitude": -21.17, "longitude": -47.81}, "destino": {"latitude": -21.18, "longitude": -47.82}})
    assert route.status_code == 503
    assert "OpenRouteService" in route.json()["detail"]


def test_post_idempotency_conflict_and_shared_get(client):
    data, auth = payload(), headers(client)
    first = client.post("/v1/relatos", json=data, headers=auth)
    assert first.status_code == 201 and first.json()["region_id"]
    second = client.post("/v1/relatos", json=data, headers=auth)
    assert second.status_code == 200 and second.json() == first.json()
    assert len(client.get("/v1/relatos").json()) == 1
    data["gravidade"] = "alta"
    assert client.post("/v1/relatos", json=data, headers=auth).status_code == 409
    assert client.get("/v1/incidentes/ativos").json()["features"][0]["geometry"]["type"] == "Polygon"


@pytest.mark.parametrize("field,value", [("latitude", 91), ("longitude", -181), ("gravidade", "critica"),
    ("occurred_at", "2026-10-03T12:00:00"), ("occurred_at", "bad date"), ("occurred_at", 1770000000),
    ("id", "not-uuid"), ("descricao", "x" * 501), ("latitude", True), ("accuracy_m", -1)])
def test_invalid_input_is_rejected(client, field, value):
    data = payload()
    data[field] = value
    assert client.post("/v1/relatos", json=data, headers=headers(client)).status_code == 422
    assert client.get("/v1/relatos").json() == []


def test_write_requires_valid_session(client):
    assert client.post("/v1/relatos", json=payload()).status_code == 401
    assert client.post("/v1/relatos", json=payload(), headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_websocket_subscribe_ping_and_update_second_client(client):
    auth = headers(client)
    token = auth["Authorization"].removeprefix("Bearer ")
    with client.websocket_connect("/v1/ws?token=" + token) as socket:
        socket.send_json({"type": "subscribe", "latitude": -21.1775, "longitude": -47.8101, "radius_m": 1000})
        subscribed = socket.receive_json()
        assert subscribed["type"] == "subscribed" and subscribed["region_ids"]
        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong"}
        assert client.post("/v1/relatos", json=payload(), headers=auth).status_code == 201
        event = socket.receive_json()
        assert event["type"] == "incidente.criado" and event["version"] == 1


def test_fixtures_always_identify_simulation(client):
    features = client.get("/v1/camadas/ambientais").json()["features"]
    assert {x["properties"]["kind"] for x in features} == {"aqi", "calor"}
    assert all(x["properties"]["is_demo"] and "simulados" in x["properties"]["label"] for x in features)


def test_full_mode_never_falls_back_to_sqlite():
    with pytest.raises(ValueError, match="PostgreSQL"):
        Settings(mode="full", database_url="sqlite:///:memory:", jwt_secret="x" * 32).validate()
