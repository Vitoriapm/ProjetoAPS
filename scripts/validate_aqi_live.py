"""Exercise the actual public AQI adapter with an isolated temporary store.

Uses public city-centre coordinates; no credentials, push or routing are used.
This proves the provider adapter, not PostgreSQL/RabbitMQ/Redis or the live app.
"""
import argparse
import asyncio
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.shared.config import Settings  # noqa: E402
from backend.shared.db import Store, iso, utc_now  # noqa: E402
from backend.shared.providers import environmental_layers, ProviderUnavailable  # noqa: E402


async def check():
    result = {
        "adapter": "Open-Meteo / CAMS Global",
        "test_scope": "Public provider adapter, isolated SQLite store; no full infrastructure validation",
        "requested_latitude": -21.1775,
        "requested_longitude": -47.8101,
        "credentials_used": False,
        "attempted_at_utc": iso(utc_now()),
    }
    with TemporaryDirectory(prefix="ecopulse-aqi-validation-") as temporary:
        settings = Settings(mode="demo", database_url="sqlite:///" + str(Path(temporary) / "aqi.db"),
            ors_key="", fcm_credentials="", environment_source="open-meteo").validate()
        store = Store(settings)
        store.initialize()
        # Only enter the real-provider branch. Infrastructure stays isolated.
        settings.mode = "full"
        try:
            collection = await environmental_layers(store, settings, -21.1775, -47.8101)
            aqi = next(feature for feature in collection["features"] if feature["properties"]["kind"] == "aqi")
            properties = aqi["properties"]
            required = {"id", "kind", "value", "unit", "scale", "source", "updated_at", "is_demo", "label"}
            heat = [feature for feature in collection["features"] if feature["properties"]["kind"] == "calor"]
            result.update(
                success=required.issubset(properties) and properties["is_demo"] is False,
                geojson_contract_valid=required.issubset(properties),
                value=properties["value"], unit=properties["unit"], scale=properties["scale"],
                observed_at_utc=properties["updated_at"],
                grid_longitude=aqi["geometry"]["coordinates"][0],
                grid_latitude=aqi["geometry"]["coordinates"][1],
                source=properties["source"], label=properties["label"],
                aqi_is_demo=properties["is_demo"],
                heat_remains_simulated=bool(heat) and all(feature["properties"]["is_demo"] for feature in heat),
                heat_is_historical_landsat=bool(heat) and all(feature["properties"].get("observation_type") == "historic" for feature in heat),
            )
        except ProviderUnavailable as failure:
            # Exception text may contain provider URLs; only classes/status leave this script.
            result.update(success=False, error_class=type(failure).__name__,
                cause_class=type(failure.__cause__).__name__)
            response = getattr(failure.__cause__, "response", None)
            if response is not None:
                result["http_status"] = response.status_code
        finally:
            store.engine.dispose()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional JSON evidence file")
    arguments = parser.parse_args()
    result = asyncio.run(check())
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
