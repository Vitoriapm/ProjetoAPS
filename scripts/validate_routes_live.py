"""Diagnose ORS configuration; optionally prove an actual route with a test block.

The key is read from process environment or project .env, never from arguments
or printed output. This uses public Ribeirao Preto coordinates and one labelled
fictitious exclusion, without writing reports to the running app.
"""
import argparse
import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_integration_config import configured, project_environment  # noqa: E402
from backend.shared.db import iso, utc_now  # noqa: E402
from backend.shared.geo import circle_polygon  # noqa: E402
from backend.shared.models import RouteRequest  # noqa: E402
from backend.shared.routes import calculate_route, ProviderUnavailable, RouteRejected  # noqa: E402


async def check(live=False):
    key = project_environment().get("ORS_API_KEY", "")
    has_key = configured(key)
    result = {"provider": "OpenRouteService / OpenStreetMap", "api_key_configured": has_key,
        "attempted_at_utc": iso(utc_now()), "live_requested": live, "live_attempted": False,
        "test_scope": "Real ORS adapter with a fictitious exclusion; no app/database modification"}
    if not live or not has_key:
        result["status"] = "configuration_ready" if has_key else "awaiting_ors_key"
        return result
    result["live_attempted"] = True
    route_request = RouteRequest.model_validate({"origem": {"latitude": -21.1875, "longitude": -47.8101},
        "destino": {"latitude": -21.1675, "longitude": -47.8101}, "perfil": "driving-car"})
    block = {"geometry": circle_polygon(-21.1775, -47.8101, 200), "properties": {"is_demo": True}}
    store = SimpleNamespace(active_features=lambda: [block])
    try:
        route = await calculate_route(store, SimpleNamespace(ors_key=key), route_request)
        result.update(status="passed", success=True, distance_m=route["distance_m"], duration_s=route["duration_s"],
            route_points=len(route["geometry"]["coordinates"]), avoided_incidents=route["avoided_incidents"],
            exclusion_is_fictitious=True, real_route=True, endpoints_and_exclusions_validated=True,
            source=route["source"], updated_at_utc=route["updated_at"])
    except (ProviderUnavailable, RouteRejected) as failure:
        result.update(status="failed", success=False, error_class=type(failure).__name__, message=str(failure))
        response = getattr(failure.__cause__, "response", None)
        if response is not None:
            result["http_status"] = response.status_code
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Call the real ORS service if a key is configured")
    parser.add_argument("--output", type=Path, help="Optional sanitized JSON evidence file")
    arguments = parser.parse_args()
    result = asyncio.run(check(arguments.live))
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    if result["status"] == "awaiting_ors_key":
        return 2
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
