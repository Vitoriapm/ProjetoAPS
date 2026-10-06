"""Load the preprocessed public Landsat layer; GDAL is not needed by the API."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

from shapely.geometry import shape, Point

DATASET_PATH = Path(__file__).resolve().parents[1] / "datasets" / "heat-ribeirao-preto.geojson"
ALLOWED_BBOX = (-47.90, -21.27, -47.70, -21.09)


class HeatDataError(ValueError):
    """The real historical dataset is absent, corrupted or outside its contract."""


def _timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamp must include its timezone")
    return result.astimezone(timezone.utc)


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Expected a finite number")
    return value


def heat_layers(now=None, path=None):
    """Return verified historical surface-temperature contrast polygons.

    updated_at always remains the acquisition time. expires_at is a 24-hour
    cache-refresh deadline, not a statement that an old acquisition is current.
    Errors fail explicitly: no simulated layer is substituted for real data.
    """
    now = now or datetime.now(timezone.utc)
    location = Path(path) if path else DATASET_PATH
    try:
        raw = location.read_bytes()
        manifest_path = location.with_name("heat-provenance.json")
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest["dataset_file"] != location.name or hashlib.sha256(raw).hexdigest() != manifest["dataset_sha256"]:
                raise ValueError("Dataset checksum differs from its provenance")
        elif location == DATASET_PATH:
            raise ValueError("The default dataset requires its provenance manifest")
        payload = json.loads(raw)
        if payload["type"] != "FeatureCollection" or not 1 <= len(payload["features"]) <= 32:
            raise ValueError("Expected 1 to 32 spatial features")
        metadata = payload["metadata"]
        observed = _timestamp(metadata["observed_at"])
        if observed > now or metadata["method"] != "landsat-spatial-contrast-v1":
            raise ValueError("Invalid acquisition time or method")
        scene_id = metadata["scene_id"]
        if not scene_id.startswith(("LC08_L2SP_", "LC09_L2SP_")):
            raise ValueError("Expected Landsat 8/9 Level-2 temperature data")
        expected_item_url = f"https://planetarycomputer.microsoft.com/api/stac/v1/collections/landsat-c2-l2/items/{scene_id}"
        if metadata["stac_item_url"] != expected_item_url or _number(metadata["reference_pixels"]) < 500:
            raise ValueError("Acquisition source or spatial reference is missing")
        for key in ("lwir11", "red", "nir08", "qa_pixel", "qa_radsat", "qa", "cdist"):
            asset = urlsplit(metadata["assets"][key])
            if asset.scheme != "https" or asset.hostname != "landsateuwest.blob.core.windows.net" or asset.query:
                raise ValueError("Expected an unsigned public Landsat archive asset URL")
        features = deepcopy(payload["features"])
        seen = set()
        for feature in features:
            properties = feature["properties"]
            identifier = str(UUID(feature["id"]))
            if feature["type"] != "Feature" or identifier in seen or properties["id"] != identifier:
                raise ValueError("Invalid or repeated feature identifier")
            seen.add(identifier)
            geometry = feature["geometry"]
            if geometry["type"] != "Polygon" or len(geometry["coordinates"]) != 1:
                raise ValueError("Only Polygon without holes is supported by the mobile map")
            ring = geometry["coordinates"][0]
            if len(ring) < 4 or len(ring) > 20 or ring[0] != ring[-1]:
                raise ValueError("Invalid closed polygon ring")
            west, south, east, north = ALLOWED_BBOX
            for pair in ring:
                if len(pair) != 2 or not west <= _number(pair[0]) <= east or not south <= _number(pair[1]) <= north:
                    raise ValueError("Feature is outside the verified Ribeirao Preto crop")
            polygon = shape(geometry)
            if not polygon.is_valid or polygon.is_empty or polygon.area <= 0:
                raise ValueError("Invalid polygon geometry")
            if properties["kind"] != "calor" or properties["unit"] != "°C" or properties["is_demo"] is not False:
                raise ValueError("Expected a real surface-temperature contrast")
            if properties["observation_type"] != "historic" or properties["scene_id"] != scene_id:
                raise ValueError("Historical acquisition provenance is missing")
            if _timestamp(properties["updated_at"]) != observed:
                raise ValueError("Feature does not belong to the dataset acquisition")
            contrast = _number(properties["value"])
            temperature = _number(properties["surface_temperature_c"])
            reference = _number(properties["reference_temperature_c"])
            if contrast < 2 or abs(temperature - reference - contrast) > 0.03:
                raise ValueError("Inconsistent spatial surface-temperature contrast")
            if not 0.7 <= _number(properties["valid_fraction"]) <= 1 or _number(properties["valid_pixels"]) < 100:
                raise ValueError("Insufficient clear source pixels")
            center_latitude = _number(properties["center_latitude"])
            center_longitude = _number(properties["center_longitude"])
            if not polygon.covers(Point(center_longitude, center_latitude)):
                raise ValueError("Invalid geographic subscription center")
            if not 1 <= _number(properties["radius_m"]) <= 2000:
                raise ValueError("Invalid subscription radius")
            properties["expires_at"] = (now + timedelta(hours=24)).isoformat()
            properties["cache_validity_note"] = "Prazo de atualização do cache; a cena continua histórica"
            properties["dataset_sha256"] = hashlib.sha256(raw).hexdigest()
        return features
    except (OSError, KeyError, TypeError, ValueError, AttributeError) as exc:
        raise HeatDataError("Camada histórica Landsat ausente ou inválida. Reimporte o conjunto verificado de Ribeirão Preto.") from exc
