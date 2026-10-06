"""Historical Landsat contract and QA checks; no network or GDAL in API tests."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

from backend.shared.heat import DATASET_PATH, HeatDataError, heat_layers
from scripts.import_heat_landsat import clear_land_qa

NOW = datetime(2026, 10, 4, 15, tzinfo=timezone.utc)


def dataset():
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def write_dataset(tmp_path, data):
    path = tmp_path / "heat-test.geojson"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_real_dataset_has_historical_provenance_and_independent_cache_deadline():
    features = heat_layers(now=NOW)
    assert len(features) == 32
    for feature in features:
        properties = feature["properties"]
        assert properties["is_demo"] is False
        assert properties["updated_at"] == "2025-09-17T13:10:21.316674Z"
        assert properties["observation_type"] == "historic"
        assert "Histórico — 17/09/2025" in properties["label"]
        assert datetime.fromisoformat(properties["expires_at"]) == NOW + timedelta(hours=24)
        assert properties["value"] == pytest.approx(
            properties["surface_temperature_c"] - properties["reference_temperature_c"], abs=0.03)
    later = heat_layers(now=NOW + timedelta(hours=12))
    assert [feature["id"] for feature in features] == [feature["id"] for feature in later]
    assert features[0]["properties"]["updated_at"] == later[0]["properties"]["updated_at"]
    assert later[0]["properties"]["expires_at"] != features[0]["properties"]["expires_at"]


def test_source_crop_and_metadata_hashes_match_published_provenance():
    manifest = json.loads(DATASET_PATH.with_name("heat-provenance.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest() == manifest["dataset_sha256"]
    for name, digest in manifest["source_files"].items():
        assert hashlib.sha256((DATASET_PATH.parent / name).read_bytes()).hexdigest() == digest


def test_missing_dataset_fails_without_fixture_fallback(tmp_path):
    with pytest.raises(HeatDataError):
        heat_layers(now=NOW, path=tmp_path / "absent.geojson")


def test_corrupted_provenance_checksum_is_rejected(tmp_path):
    path = write_dataset(tmp_path, dataset())
    (tmp_path / "heat-provenance.json").write_text(json.dumps({
        "dataset_file": path.name, "dataset_sha256": "0" * 64}), encoding="utf-8")
    with pytest.raises(HeatDataError):
        heat_layers(now=NOW, path=path)


@pytest.mark.parametrize("change", [
    lambda data: data["features"][0]["properties"].update(is_demo=True),
    lambda data: data["features"][0]["properties"].update(value=float("nan")),
    lambda data: data["features"][0]["properties"].update(value=100),
    lambda data: data["features"][0]["properties"].update(observation_type="current"),
    lambda data: data["features"][0]["properties"].update(updated_at=NOW.isoformat()),
    lambda data: data["features"][0]["properties"].update(valid_fraction=0.5),
    lambda data: data["features"][0]["properties"].update(center_latitude=0),
    lambda data: data["features"][0]["geometry"].update(type="MultiPolygon"),
    lambda data: data["features"][0]["geometry"]["coordinates"][0].__setitem__(1, [0, 0]),
    lambda data: data["features"].append(deepcopy(data["features"][0])),
    lambda data: data["metadata"].update(observed_at=(NOW + timedelta(days=1)).isoformat()),
    lambda data: data["metadata"]["assets"].update(lwir11=data["metadata"]["assets"]["lwir11"] + "?sig=secret"),
])
def test_invalid_historical_spatial_data_is_rejected(tmp_path, change):
    data = dataset()
    change(data)
    with pytest.raises(HeatDataError):
        heat_layers(now=NOW, path=write_dataset(tmp_path, data))


@pytest.mark.parametrize("bit", [0, 1, 2, 3, 4, 5, 7])
def test_cloud_fill_water_and_snow_are_not_used_in_temperature_contrast(bit):
    assert not clear_land_qa((1 << 6) | (1 << bit))


@pytest.mark.parametrize("shift", [8, 10, 12, 14])
def test_medium_cloud_shadow_snow_or_cirrus_confidence_is_rejected(shift):
    assert not clear_land_qa((1 << 6) | (2 << shift))
    assert clear_land_qa((1 << 6) | (1 << shift))


def test_clear_land_can_be_used():
    assert clear_land_qa(1 << 6)
