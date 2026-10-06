import json
from datetime import timedelta

from backend.shared.cache import (cached_environment_features, environment_key,
    environment_region, environment_version, update_environment_cache, rebuild_cache)
from backend.shared.db import utc_now, iso, parse_time, environment
from backend.shared.domain import make_event


def feature(version=10, expires=None, kind="aqi"):
    return {"type": "Feature", "id": "test", "geometry": {
        "type": "Point", "coordinates": [-47.8, -21.2]}, "properties": {
        "id": "test", "kind": kind, "version": version, "region_id": "6u7test",
        "value": 60, "updated_at": iso(utc_now()),
        "expires_at": iso(expires or utc_now() + timedelta(minutes=15))}}


class Cache:
    def __init__(self, value=None):
        self.value = value
        self.writes = []
        self.publications = []

    def get(self, key):
        return self.value

    def eval(self, script, keys, key, version, value, ttl):
        self.writes.append((key, version, json.loads(value), ttl))
        return 1

    def publish(self, channel, payload):
        self.publications.append(json.loads(payload))


def test_requested_region_is_kept_when_aqi_model_grid_is_elsewhere():
    current = feature()
    assert environment_region(current) == "6u7test"
    assert "{6u7test}" in environment_key(current)
    cache = Cache(json.dumps({"version": 10, "feature": current}))
    assert cached_environment_features(cache, [current]) == [current]


def test_environment_cache_never_regresses_or_uses_expired_or_corrupt_value():
    current = feature()
    old = feature(version=9)
    expired = feature(expires=utc_now() - timedelta(seconds=1))
    for value in (json.dumps({"version": 9, "feature": old}),
                  json.dumps({"version": 10, "feature": expired}), "bad json",
                  json.dumps({"version": 10}), None):
        assert cached_environment_features(Cache(value), [current]) == [current]


def test_layer_expiration_prevents_cache_write_and_publish():
    expired = feature(expires=utc_now() - timedelta(seconds=1))
    evt = make_event("camada.atualizada", "test", 10, "6u7test", expired)
    cache = Cache()
    assert update_environment_cache(cache, evt) is False
    assert cache.writes == cache.publications == []


def test_heat_and_air_have_separate_versioned_keys_and_ttl():
    cache = Cache()
    for kind in ("aqi", "calor"):
        current = feature(kind=kind)
        evt = make_event("camada.atualizada", "test", 10, "6u7test", current)
        assert update_environment_cache(cache, evt)
    assert len({entry[0] for entry in cache.writes}) == 2
    assert all(0 < entry[3] <= 900 for entry in cache.writes)
    assert [evt["tipo"] for evt in cache.publications] == ["camada.atualizada"] * 2


def test_legacy_observation_version_can_be_rebuilt_from_acquisition_time():
    current = feature()
    del current["properties"]["version"]
    assert environment_version(current) == int(parse_time(
        current["properties"]["updated_at"]).timestamp() * 1_000_000)


def test_rebuild_restores_only_unexpired_environmental_observations(tmp_path):
    from backend.shared.config import Settings
    from backend.shared.db import Store
    store = Store(Settings(mode="demo", database_url="sqlite:///" + str(tmp_path / "cache.db")).validate())
    store.initialize()
    active, expired = feature(kind="calor"), feature(expires=utc_now() - timedelta(seconds=1))
    with store.transaction() as connection:
        connection.execute(environment.insert(), [{"id": "heat", "data": active}, {"id": "air", "data": expired}])
    cache = Cache()
    rebuild_cache(cache, store)
    assert len(cache.writes) == 1
    assert cache.writes[0][2]["feature"]["properties"]["kind"] == "calor"
    store.engine.dispose()
