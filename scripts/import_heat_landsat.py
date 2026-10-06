"""Import a small, real Landsat surface-temperature crop for Ribeirao Preto.

Only the offline importer needs rasterio/numpy. No credentials or Earth Engine
account are required; Planetary Computer signs public data with temporary URLs.
Signed URLs are used in memory only and never written to the dataset.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid5

ROOT = Path(__file__).resolve().parents[1]
API = "https://planetarycomputer.microsoft.com/api/stac/v1"
DEFAULT_SCENE = "LC09_L2SP_220075_20250917_02_T1"
BBOX = (-47.88, -21.25, -47.72, -21.105)
URBAN_BBOX = (-47.855, -21.235, -47.745, -21.12)
ASSETS = ("lwir11", "red", "nir08", "qa_pixel", "qa_radsat", "qa", "cdist")
NAMESPACE = UUID("5df77f38-90e1-4504-8e77-b633174d5cc2")
REJECT_BITS = sum(1 << bit for bit in (0, 1, 2, 3, 4, 5, 7))


def clear_land_qa(qa):
    """Works on uint16 arrays and integers: reject clouds/water and medium QA."""
    return ((qa & REJECT_BITS) == 0) & (((qa >> 8) & 3) < 2) & \
        (((qa >> 10) & 3) < 2) & (((qa >> 12) & 3) < 2) & (((qa >> 14) & 3) < 2)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_crop(item, cache_path):
    import httpx
    import numpy as np
    import rasterio
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds, transform as window_transform

    arrays = {}
    transform = crs = window = None
    # Limit memory to the small ROI. HTTP Range reads the necessary COG blocks.
    with httpx.Client(timeout=60, follow_redirects=True) as client, rasterio.Env(
            GDAL_CACHEMAX=32, GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
            CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".TIF", GDAL_HTTP_TIMEOUT="60"):
        for key in ASSETS:
            raw_href = item["assets"][key]["href"]
            signed = client.get("https://planetarycomputer.microsoft.com/api/sas/v1/sign",
                                params={"href": raw_href})
            signed.raise_for_status()
            # Do not log or persist this URL: it includes an ephemeral SAS token.
            with rasterio.open(signed.json()["href"]) as source:
                if window is None:
                    bounds = transform_bounds("EPSG:4326", source.crs, *BBOX)
                    window = from_bounds(*bounds, transform=source.transform).round_offsets().round_lengths()
                    transform = window_transform(window, source.transform)
                    crs = source.crs.to_string()
                elif source.crs.to_string() != crs or source.transform != original_transform:
                    raise ValueError("Asset grids do not match")
                original_transform = source.transform
                arrays[key] = source.read(1, window=window)
            print(f"Read {key}: {arrays[key].shape}")
    np.savez_compressed(cache_path, **arrays, transform=np.array(tuple(transform)), crs=np.array(crs))
    return arrays, transform, crs


def build_dataset(item, arrays, transform, crs):
    import numpy as np
    from rasterio.warp import transform as transform_coords
    from rasterio.transform import xy

    temperature = arrays["lwir11"].astype("float64") * 0.00341802 + 149.0 - 273.15
    red = arrays["red"].astype("float64") * 0.0000275 - 0.2
    nir = arrays["nir08"].astype("float64") * 0.0000275 - 0.2
    denominator = nir + red
    ndvi = np.divide(nir - red, denominator, out=np.full(red.shape, np.nan), where=denominator > 0)
    valid = clear_land_qa(arrays["qa_pixel"]) & (arrays["qa_radsat"] == 0) & \
        (arrays["lwir11"] > 0) & (arrays["red"] > 0) & (arrays["nir08"] > 0) & \
        (arrays["qa"] >= 0) & (arrays["qa"] * 0.01 <= 3.0) & \
        (arrays["cdist"] * 0.01 >= 1.0) & np.isfinite(ndvi) & (ndvi >= -1) & (ndvi <= 1)
    rows, cols = np.indices(temperature.shape)
    xs, ys = xy(transform, rows.ravel(), cols.ravel(), offset="center")
    lons, lats = transform_coords(crs, "EPSG:4326", xs, ys)
    longitude = np.array(lons).reshape(temperature.shape)
    latitude = np.array(lats).reshape(temperature.shape)
    west, south, east, north = URBAN_BBOX
    inside = (longitude >= west) & (longitude < east) & (latitude >= south) & (latitude < north)
    # Vegetated outer ring on the same acquisition is a spatial comparison,
    # not a measured rural baseline or a climatological urban heat-island index.
    reference_mask = valid & ~inside & (ndvi >= 0.5)
    if int(reference_mask.sum()) < 500:
        raise ValueError("Fewer than 500 clear vegetated reference pixels")
    reference = float(np.median(temperature[reference_mask]))
    features = []
    now = datetime.now(timezone.utc)
    observed = item["properties"]["datetime"]
    observed_label = datetime.fromisoformat(observed.replace("Z", "+00:00")).strftime("%d/%m/%Y")
    for row in range(12):
        cell_south = round(south + row * 0.01, 6)
        cell_north = min(round(cell_south + 0.01, 6), north)
        if cell_south >= north:
            continue
        for col in range(11):
            cell_west = round(west + col * 0.01, 6)
            cell_east = min(round(cell_west + 0.01, 6), east)
            cell = (longitude >= cell_west) & (longitude < cell_east) & \
                (latitude >= cell_south) & (latitude < cell_north)
            count = int((cell & valid).sum())
            total = int(cell.sum())
            if count < 100 or total == 0 or count / total < 0.7:
                continue
            sample = cell & valid
            median = float(np.median(temperature[sample]))
            vegetation = float(np.median(ndvi[sample]))
            contrast = median - reference
            if contrast < 2.0 or vegetation > 0.35:
                continue
            feature_id = str(uuid5(NAMESPACE, item["id"] + f":{row}:{col}"))
            features.append({"type": "Feature", "id": feature_id,
                "geometry": {"type": "Polygon", "coordinates": [[[cell_west, cell_south],
                    [cell_east, cell_south], [cell_east, cell_north], [cell_west, cell_north],
                    [cell_west, cell_south]]]},
                "properties": {"id": feature_id, "kind": "calor", "value": round(contrast, 2),
                    "unit": "°C", "scale": "Contraste de temperatura da superfície versus vegetação na mesma cena",
                    "surface_temperature_c": round(median, 2), "reference_temperature_c": round(reference, 2),
                    "median_ndvi": round(vegetation, 3), "valid_pixels": count,
                    "valid_fraction": round(count / total, 4), "scene_id": item["id"],
                    "source": "USGS Landsat 9 Collection 2 Level-2 / Microsoft Planetary Computer",
                    "updated_at": observed, "expires_at": (now + timedelta(hours=24)).isoformat(),
                    "observation_type": "historic", "is_demo": False,
                    "label": f"Histórico — {observed_label}: contraste de temperatura da superfície; não representa o calor atual",
                    "attribution": "USGS/NASA Landsat, dados públicos; DOI 10.5066/P9OGBGM6",
                    "center_latitude": round((cell_south + cell_north) / 2, 6),
                    "center_longitude": round((cell_west + cell_east) / 2, 6), "radius_m": 850}})
    # A compact academic layer, selected by largest contrast; no invented cells.
    features.sort(key=lambda feature: (-feature["properties"]["value"], feature["id"]))
    features = features[:32]
    if not features:
        raise ValueError("No clear low-vegetation cells exceed the contrast threshold")
    return {"type": "FeatureCollection", "features": features, "metadata": {
        "dataset_version": 1, "scene_id": item["id"], "observed_at": observed,
        "imported_at": now.isoformat(), "bbox": list(BBOX), "analysis_bbox": list(URBAN_BBOX),
        "crs": "EPSG:4326", "source_pixel_spacing_m": 30,
        "thermal_sensor_resolution_m": 100, "display_cell_degrees": 0.01,
        "reference_temperature_c": round(reference, 6), "reference_pixels": int(reference_mask.sum()),
        "reference_ndvi_minimum": 0.5, "reference_region": "outer ring of ROI outside analysis bbox",
        "valid_pixels": int(valid.sum()), "total_pixels": int(valid.size),
        "temperature_range_c": [round(float(np.min(temperature[valid])), 3), round(float(np.max(temperature[valid])), 3)],
        "scene_cloud_cover_percent": item["properties"].get("eo:cloud_cover"),
        "qa": {"rejected_bits": [0, 1, 2, 3, 4, 5, 7], "reject_confidence_gte": 2,
               "qa_radsat_required": 0, "maximum_st_uncertainty_k": 3, "minimum_cloud_distance_km": 1},
        "method": "landsat-spatial-contrast-v1", "minimum_cell_valid_fraction": 0.7,
        "minimum_cell_pixels": 100, "minimum_contrast_c": 2, "maximum_cell_median_ndvi": 0.35,
        "maximum_display_cells": 32,
        "stac_item_url": f"{API}/collections/landsat-c2-l2/items/{item['id']}",
        "assets": {key: item["assets"][key]["href"] for key in ASSETS},
        "sources": ["https://www.usgs.gov/landsat-missions/landsat-collection-2-surface-temperature",
                    "https://www.usgs.gov/landsat-missions/landsat-collection-2-quality-assessment-bands",
                    "https://www.usgs.gov/landsat-missions/landsat-normalized-difference-vegetation-index"],
        "limitations": "Single historical acquisition; surface temperature, not air temperature. Vegetated spatial reference is not a rural climatology; hot bare soil can occur. No current alert is inferred."}}


def main():
    import httpx
    import numpy as np
    from affine import Affine
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", default=DEFAULT_SCENE)
    parser.add_argument("--from-crop", action="store_true", help="Reprocess saved source crop without network")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "backend" / "datasets")
    arguments = parser.parse_args()
    destination = arguments.output_dir
    source_dir = destination / "heat_source"
    source_dir.mkdir(parents=True, exist_ok=True)
    item_path = source_dir / "landsat-item.json"
    crop_path = source_dir / "landsat-crop.npz"
    if arguments.from_crop:
        item = json.loads(item_path.read_text(encoding="utf-8"))
        with np.load(crop_path, allow_pickle=False) as crop:
            arrays = {key: crop[key].copy() for key in ASSETS}
            transform = Affine(*crop["transform"][:6])
            crs = str(crop["crs"])
    else:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            response = client.get(f"{API}/collections/landsat-c2-l2/items/{arguments.scene}")
            response.raise_for_status()
            item = response.json()
        if item["properties"].get("landsat:correction") != "L2SP":
            raise ValueError("Scene must include a surface-temperature product (L2SP)")
        item_path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
        arrays, transform, crs = read_crop(item, crop_path)
    dataset = build_dataset(item, arrays, transform, crs)
    dataset["metadata"]["source_crop_sha256"] = sha256(crop_path)
    dataset["metadata"]["source_item_sha256"] = sha256(item_path)
    output = destination / "heat-ribeirao-preto.geojson"
    output.write_text(json.dumps(dataset, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    provenance = {"dataset_file": output.name, "dataset_sha256": sha256(output),
                  "source_files": {"heat_source/landsat-crop.npz": sha256(crop_path),
                                   "heat_source/landsat-item.json": sha256(item_path)},
                  "metadata": dataset["metadata"], "features": len(dataset["features"]),
                  "contrast_range_c": [min(f["properties"]["value"] for f in dataset["features"]),
                                       max(f["properties"]["value"] for f in dataset["features"])]}
    (destination / "heat-provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"scene": item["id"], "features": len(dataset["features"]),
                      "reference_c": dataset["metadata"]["reference_temperature_c"],
                      "valid_pixels": dataset["metadata"]["valid_pixels"],
                      "sha256": sha256(output)}, indent=2))


if __name__ == "__main__":
    main()
