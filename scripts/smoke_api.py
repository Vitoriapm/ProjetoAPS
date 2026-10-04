"""Teste ponta a ponta contra API em execução; só cria relato fictício."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4
import websockets


def call(base, endpoint, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(base + endpoint, headers=headers,
                      data=None if body is None else json.dumps(body).encode())
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


async def check(base):
    status, health = await asyncio.to_thread(call, base, "/health")
    assert status == 200, "API não saudável"
    installation = str(uuid4())
    _, session = await asyncio.to_thread(call, base, "/v1/sessoes",
                                        {"installation_id": installation})
    token = session["access_token"]
    ws_url = base.replace("http", "ws", 1) + "/v1/ws?token=" + token
    report = {
        "id": str(uuid4()), "tipo": "alagamento", "gravidade": "media",
        "latitude": -21.1795, "longitude": -47.807,
        "descricao": "Teste integrado HTTP/WebSocket. Ocorrência fictícia.",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "position_source": "demo", "accuracy_m": None, "is_demo": True,
    }
    async with websockets.connect(ws_url) as socket:
        await socket.send(json.dumps({"type": "subscribe", "latitude": -21.1775,
                                      "longitude": -47.8103, "radius_m": 1000}))
        assert json.loads(await asyncio.wait_for(socket.recv(), 5))["type"] == "subscribed"
        status, saved = await asyncio.to_thread(call, base, "/v1/relatos", report, token)
        assert status == 201 and saved["id"] == report["id"]
        event = json.loads(await asyncio.wait_for(socket.recv(), 20))
        assert event["type"] in {"incidente.criado", "incidente.atualizado"}
        assert event["version"] >= 1
        await socket.send('{"type":"ping"}')
        assert json.loads(await asyncio.wait_for(socket.recv(), 5))["type"] == "pong"
    status, repeated = await asyncio.to_thread(call, base, "/v1/relatos", report, token)
    assert status == 200 and repeated == saved, "Replay deve ser idempotente"
    status, _ = await asyncio.to_thread(call, base, "/v1/relatos",
                                      {**report, "gravidade": "alta"}, token)
    assert status == 409, "Payload diferente deve gerar conflito"
    status, collection = await asyncio.to_thread(call, base, "/v1/incidentes/ativos")
    assert status == 200 and collection["type"] == "FeatureCollection"
    assert any(item["properties"]["id"] == event["id"] for item in collection["features"])
    status, layers = await asyncio.to_thread(call, base, "/v1/camadas/ambientais")
    assert status == 200 and {"aqi", "calor"} <= {
        item["properties"]["kind"] for item in layers["features"]}
    route_check = "configurada; não solicitada neste teste"
    if not health["configuration"]["routes_configured"]:
        status, _ = await asyncio.to_thread(call, base, "/v1/rotas", {
            "origem": {"latitude": -21.1900, "longitude": -47.8200},
            "destino": {"latitude": -21.1940, "longitude": -47.8250},
            "perfil": "foot-walking",
        }, token)
        assert status == 503, "Sem chave não deve inventar rota"
        route_check = "503 correto sem chave"
    return {"executed_at": datetime.now(timezone.utc).isoformat(),
            "mode": health["mode"], "checks": [
                "health", "sessão", "POST 201", "replay 200", "conflito 409",
                "WebSocket subscribe/evento/pong", "GeoJSON", "AQI/calor", route_check],
            "report_is_demo": True,
            "distributed_cluster_validated": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", default="docs/evidence/api-smoke.json")
    args = parser.parse_args()
    result = asyncio.run(check(args.url.rstrip("/")))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("PASS: HTTP, idempotência, GeoJSON e WebSocket. Modo:", result["mode"])
