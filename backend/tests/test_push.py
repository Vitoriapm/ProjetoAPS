from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from firebase_admin import messaging
from sqlalchemy import select, update

from backend.alerts.main import deliver_alert, FcmAdapter, geographic_devices
from backend.shared.config import Settings
from backend.shared.db import Store, devices, deliveries, iso, utc_now
from backend.shared.domain import ingest, process_report
from backend.shared.models import RelatoRequest


def setup(tmp_path):
    settings = Settings(mode="demo", database_url="sqlite:///" + str(tmp_path / "push.db"))
    settings.validate()
    store = Store(settings)
    store.initialize()
    report = RelatoRequest.model_validate({"id": str(uuid4()), "tipo": "alagamento", "gravidade": "alta",
        "latitude": -21.1775, "longitude": -47.8101, "occurred_at": iso(utc_now()), "is_demo": True})
    _, _, incoming = ingest(store, report, str(uuid4()))
    process_report(store, incoming)
    event = {"event_id": str(uuid4()), "payload": store.active_features()[0]}
    row = {"id": str(uuid4()), "data": {"token": "first-token", "platform": "android",
        "latitude": -21.1775, "longitude": -47.8101, "position_at": iso(utc_now()), "radius_m": 1000}}
    with store.transaction() as conn:
        conn.execute(devices.insert().values(**row))
    return store, settings, row, event


def test_accepted_provider_submission_is_idempotent_but_not_device_receipt(tmp_path):
    store, _, row, event = setup(tmp_path)
    adapter = type("Adapter", (), {"send": lambda self, token, payload: "provider-reference"})()
    with patch.object(adapter, "send", wraps=adapter.send) as sender:
        deliver_alert(store, row, event, adapter)
        deliver_alert(store, row, event, adapter)
    assert sender.call_count == 1
    with store.engine.connect() as conn:
        delivery = conn.execute(select(deliveries)).mappings().one()
    assert delivery["status"] == "accepted"
    assert delivery["provider_id"] == "provider-reference"


def test_transient_provider_failure_leaves_retryable_pending_then_accepts(tmp_path):
    store, _, row, event = setup(tmp_path)
    adapter = type("Adapter", (), {"send": lambda *args: None})()
    with patch.object(adapter, "send", side_effect=[ConnectionError("offline"), "provider-reference"]):
        with pytest.raises(ConnectionError):
            deliver_alert(store, row, event, adapter)
        with store.engine.connect() as conn:
            assert conn.execute(select(deliveries.c.status)).scalar_one() == "pending"
        deliver_alert(store, row, event, adapter)
    with store.engine.connect() as conn:
        assert conn.execute(select(deliveries.c.status)).scalar_one() == "accepted"


@pytest.mark.parametrize("renewed", [True, False])
def test_invalid_token_cleanup_does_not_erase_concurrent_renewal(tmp_path, renewed):
    store, _, row, event = setup(tmp_path)
    class Adapter:
        def send(self, token, payload):
            if renewed:
                with store.transaction() as conn:
                    conn.execute(update(devices).where(devices.c.id == row["id"]).values(data={**row["data"], "token": "renewed-token"}))
            raise messaging.UnregisteredError("expired-token")
    deliver_alert(store, row, event, Adapter())
    with store.engine.connect() as conn:
        device = conn.execute(select(devices.c.data)).scalar_one()
        status = conn.execute(select(deliveries.c.status)).scalar_one()
    assert device["token"] == ("renewed-token" if renewed else None)
    assert status == "invalid_token"


def test_browser_is_explicitly_unsupported_and_never_calls_fcm(tmp_path):
    store, _, row, event = setup(tmp_path)
    row["data"]["platform"] = "web"
    deliver_alert(store, row, event, None)
    with store.engine.connect() as conn:
        assert conn.execute(select(deliveries.c.status)).scalar_one() == "unsupported"


def test_expired_risk_or_missing_position_never_selects_devices(tmp_path):
    store, _, row, event = setup(tmp_path)
    now = utc_now()
    event["payload"]["properties"]["expires_at"] = iso(now - timedelta(seconds=1))
    assert geographic_devices(store, event["payload"], now) == []
    event["payload"]["properties"]["expires_at"] = iso(now + timedelta(minutes=5))
    with store.transaction() as conn:
        conn.execute(update(devices).values(data={**row["data"], "position_at": None}))
    assert geographic_devices(store, event["payload"], now) == []


def test_fcm_payload_uses_native_channel_bounded_ttl_and_stable_notification_identity(tmp_path):
    _, settings, row, event = setup(tmp_path)
    settings.fcm_credentials = "mock-credentials.json"
    with patch("backend.alerts.main.credentials.Certificate"), \
         patch("backend.alerts.main.firebase_admin.initialize_app", return_value=object()), \
         patch("backend.alerts.main.messaging.send", return_value="validation-only") as sender:
        FcmAdapter(settings).send(row["data"]["token"], event, dry_run=True)
    message = sender.call_args.args[0]
    props = event["payload"]["properties"]
    assert sender.call_args.kwargs["dry_run"] is True
    assert message.android.notification.channel_id == "ecopulse_alertas"
    assert message.android.notification.tag == props["id"]
    assert message.android.notification.icon == "ic_notification"
    assert message.apns.headers["apns-push-type"] == "alert"
    assert message.apns.headers["apns-collapse-id"] == props["id"]
    assert message.apns.payload.aps.thread_id == props["id"]
    assert 0 < message.android.ttl.total_seconds() <= 1800
