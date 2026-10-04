from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select
from backend.shared.config import Settings
from backend.shared.db import Store, incidentes, outbox, processed, utc_now, iso
from backend.shared.domain import ConflictError, ingest, process_report, expire_incidents
from backend.shared.geo import covering_regions, geohash, distance_m, partition
from backend.shared.models import RelatoRequest
import pytest


def build_store(tmp_path):
    settings = Settings(mode="demo", database_url="sqlite:///" + str(tmp_path / "test.db"))
    settings.validate()
    store = Store(settings)
    store.initialize()
    return store


def report(now=None, **changes):
    data = dict(id=str(uuid4()), tipo="alagamento", gravidade="media", latitude=-21.1775,
        longitude=-47.8101, descricao="Ponto de teste", occurred_at=iso(now or utc_now()), position_source="manual", is_demo=True)
    return RelatoRequest.model_validate({**data, **changes})


def test_commit_response_lost_retry_and_restart(tmp_path):
    store = build_store(tmp_path)
    request, installation = report(), str(uuid4())
    original, created, evt = ingest(store, request, installation)
    assert created
    # Simulate committed POST whose response never arrived at the client.
    store.engine.dispose()
    restarted = build_store(tmp_path)
    recovered, created, repeated_event = ingest(restarted, request, installation)
    assert not created and repeated_event is None and recovered == original
    assert len(restarted.list_reports()) == 1
    with restarted.engine.connect() as conn:
        assert len(conn.execute(select(outbox)).all()) == 1
    process_report(restarted, evt)
    assert len(restarted.active_features()) == 1


def test_uuid_conflict_and_utc_equivalence(tmp_path):
    store = build_store(tmp_path)
    request, installation = report(), str(uuid4())
    ingest(store, request, installation)
    same = request.model_copy(update={"occurred_at": request.occurred_at.astimezone(__import__("datetime").timezone(timedelta(hours=-3)))})
    assert ingest(store, same, installation)[1] is False
    with pytest.raises(ConflictError):
        ingest(store, report(id=str(request.id), descricao="Outro conteúdo"), installation)


def test_event_replay_does_not_duplicate_incident(tmp_path):
    store = build_store(tmp_path)
    _, _, evt = ingest(store, report(), str(uuid4()))
    assert len(process_report(store, evt)) == 1
    assert process_report(store, evt) == []
    feature = store.active_features()[0]
    assert feature["properties"]["version"] == 1
    assert feature["properties"]["report_count"] == 1
    with store.engine.connect() as conn:
        assert len(conn.execute(select(processed)).all()) == 1


def test_three_distinct_installations_and_neighboring_cells(tmp_path):
    store = build_store(tmp_path)
    now = utc_now()
    # Pick two adjacent GeoHash cells around longitude -47.8125.
    points = [(-21.1775, -47.81251), (-21.1775, -47.81249), (-21.1776, -47.81248)]
    assert geohash(*points[0]) != geohash(*points[1])
    for lat, lon in points:
        _, _, evt = ingest(store, report(now, latitude=lat, longitude=lon), str(uuid4()), now)
        process_report(store, evt, now)
    feature = store.active_features(now=now)[0]
    assert len(store.active_features(now=now)) == 1
    assert feature["properties"]["estado"] == "colaborativo"
    assert feature["properties"]["version"] == 3
    regions = covering_regions(*points[0], 1000)
    assert geohash(*points[0]) in regions and geohash(*points[1]) in regions
    assert distance_m(*points[0], *points[1]) < 200
    assert len({partition(geohash(-21.1775 + n * 0.05, -47.8101), 4) for n in range(20)}) > 1


def test_multiple_reports_same_installation_are_not_collaborative(tmp_path):
    store = build_store(tmp_path)
    installation = str(uuid4())
    for _ in range(3):
        _, _, evt = ingest(store, report(), installation)
        process_report(store, evt)
    assert store.active_features()[0]["properties"]["estado"] == "relatado"


def test_old_offline_report_does_not_create_current_risk(tmp_path):
    store = build_store(tmp_path)
    now = utc_now()
    _, _, evt = ingest(store, report(now - timedelta(hours=1)), str(uuid4()), now)
    assert process_report(store, evt, now) == []
    assert store.active_features(now=now) == []
    assert len(store.list_reports()) == 1


def test_expiration_has_new_version_and_does_not_imply_safe(tmp_path):
    store = build_store(tmp_path)
    now = utc_now()
    _, _, evt = ingest(store, report(now), str(uuid4()), now)
    process_report(store, evt, now)
    expired = expire_incidents(store, now + timedelta(minutes=31))
    assert expired[0]["tipo"] == "incidente.expirado" and expired[0]["aggregate_version"] == 2
    assert store.active_features(now=now + timedelta(minutes=31)) == []
    assert expire_incidents(store, now + timedelta(minutes=32)) == []


def test_demo_and_real_reports_do_not_merge(tmp_path):
    store = build_store(tmp_path)
    for is_demo in (True, False):
        _, _, evt = ingest(store, report(is_demo=is_demo), str(uuid4()))
        process_report(store, evt)
    assert len(store.active_features()) == 2
