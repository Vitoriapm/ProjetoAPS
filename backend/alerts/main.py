import asyncio
from datetime import timedelta
import logging
import firebase_admin
from firebase_admin import credentials, messaging
from sqlalchemy import select, update, text
from backend.shared.broker import consume_loop
from backend.shared.cache import cluster_client, update_cache, update_environment_cache
from backend.shared.config import Settings
from backend.shared.db import Store, devices, deliveries, processed, incidentes, utc_now, parse_time, iso
from backend.shared.geo import distance_m
from backend.shared.models import Event

log = logging.getLogger(__name__)


def geographic_devices(store, feature, now=None):
    now = now or utc_now()
    props = feature["properties"]
    if parse_time(props["expires_at"]) <= now:
        return []
    with store.engine.connect() as conn:
        rows = list(conn.execute(select(devices)).mappings())
    result = []
    for row in rows:
        data = row["data"]
        if not data.get("token") or data.get("latitude") is None or not data.get("position_at"):
            continue
        position_at = parse_time(data["position_at"])
        if position_at < now - timedelta(seconds=store.settings.position_valid_s) or position_at > now + timedelta(minutes=5):
            continue
        if distance_m(data["latitude"], data["longitude"], props["center_latitude"], props["center_longitude"]) <= data.get("radius_m", 1000) + props["radius_m"]:
            result.append(row)
    return result


class FcmAdapter:
    def __init__(self, settings):
        self.settings = settings
        self.app = None

    def send(self, token, event, *, dry_run=False):
        if not self.settings.fcm_credentials:
            raise RuntimeError("FCM não configurado; alerta real não foi enviado")
        if self.app is None:
            self.app = firebase_admin.initialize_app(credentials.Certificate(self.settings.fcm_credentials), name="ecopulse-alerts")
        feature = event["payload"]
        props = feature["properties"]
        ttl = max(0, min(1800, int((parse_time(props["expires_at"]) - utc_now()).total_seconds())))
        if ttl == 0:
            raise ValueError("Incidente expirou antes do envio")
        # The OS displays notification text while the app is closed, before it
        # can inspect data.is_demo. Simulation must be explicit in that text.
        notification = messaging.Notification(
            title="EcoPulse — demonstração" if props["is_demo"] else "EcoPulse",
            body="Alerta simulado para apresentação: ocorrência fictícia na área selecionada."
                if props["is_demo"] else "Há uma ocorrência registrada perto de você.")
        message = messaging.Message(token=token, notification=notification,
            data={"event_id": event["event_id"], "incident_id": props["id"], "version": str(props["version"]), "is_demo": str(props["is_demo"]).lower()},
            android=messaging.AndroidConfig(ttl=timedelta(seconds=ttl), priority="high",
                notification=messaging.AndroidNotification(channel_id="ecopulse_alertas", tag=props["id"], icon="ic_notification")),
            apns=messaging.APNSConfig(headers={"apns-expiration": str(int(utc_now().timestamp()) + ttl),
                "apns-push-type": "alert", "apns-priority": "10", "apns-collapse-id": props["id"]},
                payload=messaging.APNSPayload(aps=messaging.Aps(sound="default", thread_id=props["id"]))))
        return messaging.send(message, app=self.app, dry_run=dry_run)


def deliver_alert(store, row, event, adapter):
    delivery_id = row["id"] + ":" + event["event_id"]
    with store.transaction() as conn:
        previous = conn.execute(select(deliveries).where(deliveries.c.id == delivery_id)).mappings().first()
        if previous and previous["status"] in {"accepted", "unsupported", "invalid_token"}:
            return
        if previous:
            conn.execute(update(deliveries).where(deliveries.c.id == delivery_id).values(status="pending", updated_at=iso(utc_now())))
        else:
            conn.execute(deliveries.insert().values(id=delivery_id, status="pending", updated_at=iso(utc_now())))
    if row["data"]["platform"] == "web":
        provider_id, status = None, "unsupported"
    else:
        try:
            provider_id = adapter.send(row["data"]["token"], event)
            status = "accepted"
        except messaging.UnregisteredError:
            provider_id, status = None, "invalid_token"
            with store.transaction() as conn:
                current = conn.execute(select(devices.c.data).where(devices.c.id == row["id"])).scalar_one()
                # Do not erase a concurrently renewed token.
                if current.get("token") == row["data"]["token"]:
                    current = {**current, "token": None}
                    conn.execute(update(devices).where(devices.c.id == row["id"]).values(data=current))
    with store.transaction() as conn:
        conn.execute(update(deliveries).where(deliveries.c.id == delivery_id).values(status=status, provider_id=provider_id, updated_at=iso(utc_now())))
    # Provider acceptance is not evidence of receipt by a physical device.


async def run():
    settings = Settings().validate()
    if settings.mode != "full":
        raise ValueError("Alertas separados exigem ECOPULSE_MODE=full")
    store = Store(settings)
    store.initialize()
    cache = cluster_client(settings)
    adapter = FcmAdapter(settings)

    async def handle_effect(payload):
        evt = Event.model_validate(payload)
        event_id = str(evt.event_id)
        with store.engine.connect() as conn:
            if conn.execute(select(processed.c.event_id).where(processed.c.consumer == "alerts", processed.c.event_id == event_id)).first():
                return
        if evt.tipo == "camada.atualizada":
            await asyncio.to_thread(update_environment_cache, cache, payload)
        elif evt.tipo.startswith("incidente."):
            with store.engine.connect() as conn:
                current = conn.execute(select(incidentes.c.version, incidentes.c.active).where(incidentes.c.id == str(evt.aggregate_id))).mappings().first()
            if current is None:
                raise ValueError("Incidente do evento não existe")
            # A late old event cannot resurrect an expired risk in cache/push.
            if evt.aggregate_version < current["version"]:
                with store.transaction() as conn:
                    if not conn.execute(select(processed.c.event_id).where(processed.c.consumer == "alerts", processed.c.event_id == event_id)).first():
                        conn.execute(processed.insert().values(consumer="alerts", event_id=event_id, processed_at=iso(utc_now())))
                return
            await asyncio.to_thread(update_cache, cache, payload)
            if evt.tipo != "incidente.expirado":
                for row in await asyncio.to_thread(geographic_devices, store, payload["payload"]):
                    await asyncio.to_thread(deliver_alert, store, row, payload, adapter)
        else:
            raise ValueError("Tipo de evento não atendido pelo serviço de alertas")
        with store.transaction() as conn:
            # Insert is idempotent even if an event is delivered concurrently.
            if not conn.execute(select(processed.c.event_id).where(processed.c.consumer == "alerts", processed.c.event_id == event_id)).first():
                conn.execute(processed.insert().values(consumer="alerts", event_id=event_id, processed_at=iso(utc_now())))

    async def handle(payload):
        evt = Event.model_validate(payload)
        # Serialize same-event handling across alert replicas. The lock is on a
        # dedicated connection; providers and committed delivery records use
        # separate transactions, so retries can recover their partial effects.
        lock_id = evt.event_id.int & ((1 << 63) - 1)
        with store.engine.connect() as lock_connection:
            await asyncio.to_thread(lock_connection.execute, text("SELECT pg_advisory_lock(:lock)"), {"lock": lock_id})
            try:
                await handle_effect(payload)
            finally:
                await asyncio.to_thread(lock_connection.execute, text("SELECT pg_advisory_unlock(:lock)"), {"lock": lock_id})

    await consume_loop(store, settings, "alerts", handle)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    asyncio.run(run())
