import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
import json
import logging
import re
from uuid import UUID
import jwt
from fastapi import Depends, FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError
from sqlalchemy import select, update, func
from backend.shared.broker import connect
from backend.shared.cache import CHANNEL, cluster_client, rebuild_cache, cached_features, cached_environment_features
from backend.shared.config import Settings
from backend.shared.db import Store, devices, relatos, outbox, utc_now, iso, parse_time
from backend.shared.domain import ConflictError, ingest, process_report, expire_incidents
from backend.shared.geo import covering_regions, distance_m
from backend.shared.models import SessionRequest, RelatoRequest, PositionRequest, PushRequest, Subscription, RouteRequest
from backend.shared.providers import environmental_layers, calculate_route, ProviderUnavailable, RouteRejected

log = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)


class RedactWebSocketToken(logging.Filter):
    """Uvicorn writes WS URLs to its error logger even without access logs."""
    def filter(self, record):
        message = record.getMessage()
        if "/v1/ws?" in message:
            record.msg = re.sub(r"([?&]token=)[^&\s\"']+", r"\1[redacted]", message)
            record.args = ()
        return True


if not any(isinstance(item, RedactWebSocketToken) for item in logging.getLogger("uvicorn.error").filters):
    logging.getLogger("uvicorn.error").addFilter(RedactWebSocketToken())


class Hub:
    def __init__(self):
        self.clients = {}

    async def broadcast(self, event):
        feature = event["payload"]
        props = feature.get("properties", {})
        if "center_latitude" in props:
            lat, lon, influence = props["center_latitude"], props["center_longitude"], props["radius_m"]
        elif feature.get("geometry", {}).get("type") == "Point":
            lon, lat = feature["geometry"]["coordinates"]
            influence = 0
        else:
            return
        for socket, subscription in list(self.clients.items()):
            if distance_m(lat, lon, subscription.latitude, subscription.longitude) > subscription.radius_m + influence:
                continue
            try:
                await asyncio.wait_for(socket.send_json({"type": event["tipo"], "id": event["aggregate_id"], "version": event["aggregate_version"]}), timeout=2)
            except Exception:
                self.clients.pop(socket, None)


def create_app(settings=None):
    settings = settings or Settings()
    hub = Hub()
    infrastructure = {"database": "iniciando", "broker": "iniciando", "cache": "iniciando"}

    async def redis_listener(application):
        while True:
            client = pubsub = None
            try:
                client = await asyncio.to_thread(cluster_client, settings)
                await asyncio.to_thread(client.ping)
                application.state.cache = client
                infrastructure["cache"] = "ok"
                await asyncio.to_thread(rebuild_cache, client, application.state.store)
                pubsub = client.pubsub()
                await asyncio.to_thread(pubsub.subscribe, CHANNEL)
                while True:
                    message = await asyncio.to_thread(pubsub.get_message, ignore_subscribe_messages=True, timeout=1)
                    if message and message["type"] == "message":
                        await hub.broadcast(json.loads(message["data"]))
                    await asyncio.sleep(0.02)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                infrastructure["cache"] = "indisponivel"
                application.state.cache = None
                log.warning("WebSocket aguardando Redis Cluster: %s", type(exc).__name__)
                await asyncio.sleep(3)
            finally:
                if pubsub:
                    await asyncio.to_thread(pubsub.close)
                if client:
                    await asyncio.to_thread(client.close)

    async def broker_probe():
        while True:
            connection = None
            try:
                connection = await connect(settings)
                infrastructure["broker"] = "ok"
            except Exception:
                infrastructure["broker"] = "indisponivel"
            finally:
                if connection:
                    await connection.close()
            await asyncio.sleep(15)

    async def demo_expiration(application):
        while True:
            for evt in await asyncio.to_thread(expire_incidents, application.state.store):
                await hub.broadcast(evt)
            await asyncio.sleep(5)

    @asynccontextmanager
    async def lifespan(application):
        settings.validate()
        store = Store(settings)
        await asyncio.to_thread(store.initialize)
        application.state.store, application.state.cache = store, None
        infrastructure["database"] = "ok"
        if settings.mode == "demo":
            infrastructure.update(broker="nao_aplicavel_demo", cache="nao_aplicavel_demo")
            tasks = [asyncio.create_task(demo_expiration(application))]
        else:
            tasks = [asyncio.create_task(redis_listener(application)), asyncio.create_task(broker_probe())]
        yield
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        store.engine.dispose()

    app = FastAPI(title="EcoPulse — APS", version="1.0.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_methods=["GET", "POST", "PUT", "OPTIONS"], allow_headers=["Authorization", "Content-Type"])

    def verify(token):
        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], audience="ecopulse", issuer="ecopulse")
            return str(UUID(payload["sub"]))
        except (jwt.PyJWTError, KeyError, ValueError, TypeError):
            raise HTTPException(401, "A sessão expirou. Reabra o aplicativo para renovar.")

    def installation(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(401, "É necessário iniciar uma sessão do aplicativo.")
        return verify(credentials.credentials)

    @app.get("/health")
    async def health(response: Response):
        try:
            await asyncio.to_thread(app.state.store.ping)
            infrastructure["database"] = "ok"
            with app.state.store.engine.connect() as conn:
                pending = conn.execute(select(func.count()).select_from(outbox).where(outbox.c.published.is_(False))).scalar_one()
        except Exception:
            infrastructure["database"] = "indisponivel"
            pending = None
        degraded = any(value in {"indisponivel", "iniciando"} for value in infrastructure.values())
        if degraded:
            response.status_code = 503
        return {"status": "degraded" if degraded else "ok", "mode": settings.mode,
            "services": infrastructure, "outbox_pending": pending,
            "configuration": {"shards": settings.shard_count, "fcm_configured": bool(settings.fcm_credentials),
                "routes_configured": bool(settings.ors_key),
                "heat_source": "fixture_simulada" if settings.environment_source == "fixtures" else "landsat_historico"},
            "notice": "Modo local simulado: não comprova sistemas distribuídos" if settings.mode == "demo" else "Infraestrutura real; validação requer evidências de execução"}

    @app.post("/v1/sessoes")
    async def session(request: SessionRequest):
        now = utc_now()
        token = jwt.encode({"sub": str(request.installation_id), "iat": now,
            "exp": now + timedelta(hours=settings.session_hours), "iss": "ecopulse", "aud": "ecopulse"}, settings.jwt_secret, algorithm="HS256")
        return {"access_token": token, "installation_id": str(request.installation_id)}

    @app.get("/v1/relatos")
    async def reports(limit: int = Query(200, ge=1, le=500), offset: int = Query(0, ge=0, le=100000)):
        return await asyncio.to_thread(app.state.store.list_reports, limit, offset)

    @app.post("/v1/relatos", status_code=201)
    async def report(request: RelatoRequest, response: Response, installation_id=Depends(installation)):
        if distance_m(-21.1775, -47.8101, request.latitude, request.longitude) > 50000:
            raise HTTPException(422, "Escolha um ponto na região de Ribeirão Preto, até 50 km do centro.")
        try:
            row, created, event = await asyncio.to_thread(ingest, app.state.store, request, installation_id)
        except ConflictError as exc:
            raise HTTPException(409, str(exc))
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        if not created:
            response.status_code = 200
        if settings.mode == "demo" and event:
            for evt in await asyncio.to_thread(process_report, app.state.store, event):
                await hub.broadcast(evt)
        return row

    @app.get("/v1/incidentes/ativos")
    async def incidents(latitude: float = Query(-21.1775, ge=-85, le=85), longitude: float = Query(-47.8101, ge=-180, le=180), radius_m: int = Query(10000, ge=100, le=50000)):
        features = await asyncio.to_thread(app.state.store.active_features, latitude, longitude, radius_m)
        if app.state.cache is not None:
            try:
                features = await asyncio.to_thread(cached_features, app.state.cache, features)
            except Exception:
                infrastructure["cache"] = "indisponivel"
                log.warning("Consulta de cache falhou; resposta mantém estado durável do PostgreSQL")
        return {"type": "FeatureCollection", "features": features}

    @app.get("/v1/camadas/ambientais")
    async def layers(latitude: float = Query(-21.1775, ge=-85, le=85), longitude: float = Query(-47.8101, ge=-180, le=180)):
        try:
            collection = await environmental_layers(app.state.store, settings, latitude, longitude)
            if app.state.cache is not None:
                try:
                    collection["features"] = await asyncio.to_thread(
                        cached_environment_features, app.state.cache, collection["features"])
                except Exception:
                    infrastructure["cache"] = "indisponivel"
                    log.warning("Cache ambiental indisponível; resposta preserva observações duráveis")
            return collection
        except ProviderUnavailable as exc:
            raise HTTPException(503, str(exc))

    @app.post("/v1/rotas")
    async def route(request: RouteRequest, _=Depends(installation)):
        try:
            return await calculate_route(app.state.store, settings, request)
        except ProviderUnavailable as exc:
            raise HTTPException(503, str(exc))
        except RouteRejected as exc:
            raise HTTPException(422, str(exc))

    def save_device(installation_id, incoming):
        with app.state.store.transaction(risk_lock=True) as conn:
            existing = conn.execute(select(devices.c.data).where(devices.c.id == installation_id)).scalar_one_or_none()
            data = {**(existing or {}), **{key: value for key, value in incoming.items() if value is not None}}
            if data.get("position_at"):
                data["position_at"] = iso(parse_time(data["position_at"]))
                if parse_time(data["position_at"]) > utc_now() + timedelta(minutes=5):
                    raise HTTPException(422, "O horário da posição está no futuro.")
            if existing is None:
                conn.execute(devices.insert().values(id=installation_id, data=data))
            else:
                conn.execute(update(devices).where(devices.c.id == installation_id).values(data=data))

    @app.put("/v1/dispositivos/push")
    async def push(request: PushRequest, installation_id=Depends(installation)):
        await asyncio.to_thread(save_device, installation_id, request.model_dump(mode="json"))
        return {"status": "registered", "delivery": "pending_fcm_configuration" if not settings.fcm_credentials else "configured", "mode": settings.mode}

    @app.post("/v1/dispositivos/posicao")
    async def position(request: PositionRequest, installation_id=Depends(installation)):
        await asyncio.to_thread(save_device, installation_id, request.model_dump(mode="json"))
        return {"status": "saved"}

    @app.websocket("/v1/ws")
    async def websocket(socket: WebSocket):
        try:
            verify(socket.query_params.get("token", ""))
        except HTTPException:
            await socket.close(code=1008)
            return
        await socket.accept()
        try:
            while True:
                message = await socket.receive_json()
                if message.get("type") == "ping":
                    await socket.send_json({"type": "pong"})
                elif message.get("type") == "subscribe":
                    try:
                        subscription = Subscription.model_validate(message)
                        regions = covering_regions(subscription.latitude, subscription.longitude, subscription.radius_m)
                    except (ValidationError, ValueError):
                        await socket.send_json({"type": "error", "message": "Confira a posição e o raio da área escolhida."})
                        continue
                    hub.clients[socket] = subscription
                    await socket.send_json({"type": "subscribed", "region_ids": regions})
                else:
                    await socket.send_json({"type": "error", "message": "Use subscribe ou ping."})
        except (WebSocketDisconnect, ValueError):
            pass
        finally:
            hub.clients.pop(socket, None)

    return app


app = create_app()
