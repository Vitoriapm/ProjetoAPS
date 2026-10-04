import json
from backend.shared.cache import cached_features
from backend.shared.geo import geohash


class Cache:
    def __init__(self, value):
        self.value = value

    def get(self, key):
        assert "{" + geohash(-21.1775, -47.8101) + "}" in key
        return json.dumps(self.value) if self.value else None


def feature(version):
    return {"type": "Feature", "properties": {"id": "test", "version": version,
        "center_latitude": -21.1775, "center_longitude": -47.8101}}


def test_late_cache_does_not_regress_database_version():
    current, old = feature(3), feature(1)
    assert cached_features(Cache({"version": 1, "expired": False, "feature": old}), [current]) == [current]


def test_expiration_tombstone_does_not_expose_geometry_as_active():
    current = feature(3)
    assert cached_features(Cache({"version": 3, "expired": True, "feature": current}), [current]) == [current]


def test_current_cache_version_is_returned():
    current = feature(3)
    cached = {**current, "cached": True}
    assert cached_features(Cache({"version": 3, "expired": False, "feature": cached}), [current]) == [cached]
