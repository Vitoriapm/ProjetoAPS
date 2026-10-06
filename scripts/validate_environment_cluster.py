"""Validate real PostgreSQL -> RabbitMQ -> Redis environmental layers.

Run only against an already-started full cluster. This script never starts,
promotes or removes a database. It temporarily changes ONE heat cache key,
then rebuilds it from PostgreSQL. --test-redis-outage additionally stops and
restarts the six Redis services of the selected Compose project.
Credentials stay inside the application container; evidence contains no JWTs.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
PATH = "/v1/camadas/ambientais"
COMMON = """
import json, time
from copy import deepcopy
from datetime import timedelta
from sqlalchemy import select
from backend.shared.config import Settings
from backend.shared.db import Store, environment, outbox, processed, parse_time, utc_now, iso
from backend.shared.cache import (cluster_client, environment_key, environment_version,
    update_environment_cache, cached_environment_features, rebuild_cache)
from backend.shared.domain import make_event
settings = Settings().validate()
store = Store(settings)
cache = cluster_client(settings)
"""

PROBE = """
with store.engine.connect() as conn:
    observations = list(conn.execute(select(environment.c.data)).scalars())
    events = list(conn.execute(select(outbox.c.event, outbox.c.published)
        .where(outbox.c.route == 'camada.atualizada')).mappings())
    accepted = set(conn.execute(select(processed.c.event_id)
        .where(processed.c.consumer == 'alerts')).scalars())
    pending = len(list(conn.execute(select(outbox.c.id)
        .where(outbox.c.published.is_(False))).scalars()))
checks = []
for wanted in WANTED:
    feature = next(f for f in observations if f['properties']['id'] == wanted['id']
        and environment_version(f) == wanted['version'])
    raw = cache.get(environment_key(feature))
    saved = json.loads(raw) if raw else None
    ttl = cache.ttl(environment_key(feature))
    event = next((e for e in events if e['event']['aggregate_id'] == wanted['id']
        and e['event']['aggregate_version'] == wanted['version']), None)
    props = feature['properties']
    checks.append({'id': props['id'], 'kind': props['kind'], 'database_version':
        environment_version(feature), 'cache_version': saved.get('version') if saved else None,
        'cache_equals_database': bool(saved and saved['feature'] == feature),
        'ttl_seconds': ttl, 'remaining_validity_seconds':
        int((parse_time(props['expires_at']) - utc_now()).total_seconds()),
        'outbox_published': bool(event and event['published']),
        'alerts_consumer_processed': bool(event and event['event']['event_id'] in accepted),
        'is_demo': props['is_demo'], 'observed_at': props['updated_at'],
        'observation_type': props.get('observation_type', 'modelled'),
        'source': props['source']})
print(json.dumps({'layers': checks, 'outbox_pending': pending,
    'redis_slots_covered': sum(end-start+1 for start,end in cache.cluster_slots())}))
"""

RESILIENCE = """
with store.engine.connect() as conn:
    feature = next(f for f in conn.execute(select(environment.c.data)).scalars()
        if f['properties']['id'] == HEAT_ID)
key = environment_key(feature)
original = cache.get(key)
original_ttl = cache.ttl(key)
assert original and original_ttl > 0
result = {'heat_id': HEAT_ID}
try:
    old = deepcopy(feature)
    old['properties']['version'] = environment_version(feature) - 1
    old['properties']['value'] -= 0.1
    event = make_event('camada.atualizada', HEAT_ID, environment_version(old),
        old['properties']['region_id'], old)
    changed = update_environment_cache(cache, event)
    result['old_event_rejected'] = changed is False and cache.get(key) == original
    legacy = json.loads(original)
    legacy['version'] -= 1
    cache.set(key, json.dumps(legacy), ex=original_ttl)
    result['legacy_cache_falls_back_to_database'] = cached_environment_features(cache, [feature]) == [feature]
    cache.set(key, 'bad json', ex=original_ttl)
    result['corrupt_cache_read_falls_back_to_database'] = cached_environment_features(cache, [feature]) == [feature]
    rebuild_cache(cache, store)
    result['corrupt_cache_rebuilt'] = json.loads(cache.get(key))['feature'] == feature
    cache.expire(key, 1)
    time.sleep(1.3)
    result['redis_ttl_really_expired'] = cache.get(key) is None
    result['expired_cache_falls_back_to_database'] = cached_environment_features(cache, [feature]) == [feature]
    # Rebuild only reads committed observations. A provider request is forbidden.
    from unittest.mock import patch
    with patch('backend.shared.providers.environmental_layers', side_effect=AssertionError('provider called')) as provider:
        with patch('backend.shared.heat.heat_layers', side_effect=AssertionError('source called')) as source:
            rebuild_cache(cache, store)
    result['cache_miss_rebuilt_from_database'] = json.loads(cache.get(key))['feature'] == feature
    result['rebuild_did_not_call_providers_or_heat_importer'] = not provider.called and not source.called
finally:
    try:
        restored = json.loads(cache.get(key) or 'null')
    except (ValueError, TypeError):
        restored = None
    if not restored or restored.get('feature') != feature:
        cache.set(key, original, ex=max(1, original_ttl))
print(json.dumps(result))
"""


class ValidationFailure(RuntimeError):
    pass


def docker_path():
    found = shutil.which("docker")
    fallback = Path.home() / "AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe"
    if found:
        return found
    if fallback.is_file():
        return str(fallback)
    raise ValidationFailure("Docker executable not found")


class Cluster:
    def __init__(self, arguments):
        self.project = arguments.project
        files = [ROOT / "infra/compose.yaml", ROOT / "infra/compose.cluster.yaml"]
        files.extend(ROOT / value for value in arguments.compose_file)
        if arguments.promoted:
            files.append(ROOT / "infra/compose.failover.yaml")  # MUST stay last.
        self.command = [docker_path(), "compose", "-p", self.project,
                        "--env-file", str(ROOT / arguments.env_file)]
        for file in files:
            self.command.extend(["-f", str(file)])

    def run(self, extra, code=None, timeout=90):
        completed = subprocess.run(self.command + extra, cwd=ROOT, input=code,
            text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=timeout)
        if completed.returncode:
            # Docker/provider output can contain sensitive URLs. Do not echo it.
            raise ValidationFailure("Compose operation failed: " + extra[0])
        return completed.stdout

    def python(self, code, service="api"):
        return json.loads(self.run(["exec", "-T", service, "python", "-"], code))

    def probe(self, wanted):
        return self.python(COMMON + "WANTED = " + repr(wanted) + "\n" + PROBE)


def request(base, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base.rstrip("/") + path, data=data,
        headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def signature(collection):
    return sorted((f["properties"]["id"], f["properties"]["version"],
                   f["properties"]["value"]) for f in collection["features"])


def poll(check, timeout=75):
    deadline = time.monotonic() + timeout
    while True:
        try:
            result = check()
            if result:
                return result
        except (OSError, ValueError, ValidationFailure):
            pass
        if time.monotonic() >= deadline:
            raise ValidationFailure("Timed out waiting for cluster convergence")
        time.sleep(1)


async def websocket_rebuild(cluster, base, wanted):
    import websockets
    token = request(base, "/v1/sessoes", {"installation_id": str(uuid4())})["access_token"]
    websocket_url = base.replace("http://", "ws://").replace("https://", "wss://")
    expected = {item["id"]: item["version"] for item in wanted}
    async with websockets.connect(websocket_url + "/v1/ws?token=" + token) as first:
        async with websockets.connect(websocket_url + "/v1/ws?token=" + token) as second:
            for socket in (first, second):
                await socket.send(json.dumps({"type": "subscribe", "latitude": -21.1775,
                    "longitude": -47.8101, "radius_m": 10000}))
                assert json.loads(await asyncio.wait_for(socket.recv(), 10))["type"] == "subscribed"
            async def receive(socket):
                seen = {}
                async with asyncio.timeout(40):
                    while len(seen) < len(expected):
                        event = json.loads(await socket.recv())
                        if event["type"] == "camada.atualizada" and event["id"] in expected:
                            seen[event["id"]] = event["version"]
                return seen
            tasks = [asyncio.create_task(receive(first)), asyncio.create_task(receive(second))]
            started = time.monotonic()
            await asyncio.to_thread(cluster.python, COMMON + "rebuild_cache(cache, store)\nprint('{}')")
            received = await asyncio.gather(*tasks)
            assert all(events == expected for events in received)
            return {"clients": 2, "layers_received_by_each": len(expected),
                "versions_equal_database": True, "rebuild_seconds": round(time.monotonic()-started, 3)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--project", default="ecopulse")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--compose-file", action="append", default=[], help="Extra overlay, repeatable")
    parser.add_argument("--promoted", action="store_true", help="Append failover overlay LAST; old primary must already be fenced")
    parser.add_argument("--test-redis-outage", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evidence/environment-cache.json")
    args = parser.parse_args()
    result = {"attempted_at_utc": datetime.now(timezone.utc).isoformat(),
        "project": args.project, "database_promoted_overlay": args.promoted,
        "scope": "Real environmental layer persistence, outbox, broker consumer and Redis Cluster; no capacity claim"}
    try:
        cluster = Cluster(args)
        health = poll(lambda: request(args.base_url, "/health"))
        assert health["mode"] == "full" and health["status"] == "ok"
        started = time.monotonic()
        layers = request(args.base_url, PATH)
        wanted = [{"id": f["properties"]["id"], "version": f["properties"]["version"]}
                  for f in layers["features"]]
        assert wanted and any(f["properties"]["kind"] == "aqi" for f in layers["features"])
        assert all(f["properties"]["is_demo"] is False for f in layers["features"])
        def converged():
            backing = cluster.probe(wanted)
            return backing if all(f["cache_equals_database"] and f["outbox_published"]
                and f["alerts_consumer_processed"] and f["ttl_seconds"] > 0
                and abs(f["ttl_seconds"] - f["remaining_validity_seconds"]) <= 3
                for f in backing["layers"]) else None
        result["backing"] = poll(converged)
        result["initial_convergence_seconds"] = round(time.monotonic() - started, 3)
        result["layer_count"] = len(wanted)
        result["two_api_instances"] = {}
        for service in ("api", "api2"):
            collection = cluster.python("import urllib.request,json\n"
                "print(json.dumps(json.load(urllib.request.urlopen('http://127.0.0.1:8000" + PATH + "',timeout=30))))", service)
            assert signature(collection) == signature(layers)
            result["two_api_instances"][service] = {"layer_count": len(collection["features"]), "same_ids_versions_values": True}
        heat_id = next(f["properties"]["id"] for f in layers["features"] if f["properties"]["kind"] == "calor")
        result["cache_resilience"] = cluster.python(COMMON + "HEAT_ID = " + repr(heat_id) + "\n" + RESILIENCE)
        assert all(value is True for key,value in result["cache_resilience"].items() if key != "heat_id")
        result["environment_websocket"] = asyncio.run(websocket_rebuild(cluster, args.base_url, wanted))
        if args.test_redis_outage:
            redis_services = ["redis" + str(number) for number in range(1, 7)]
            try:
                cluster.run(["stop", "--timeout", "5", *redis_services])
                outage = {}
                for service in ("api", "api2"):
                    collection = cluster.python("import urllib.request,json\n"
                        "print(json.dumps(json.load(urllib.request.urlopen('http://127.0.0.1:8000" + PATH + "',timeout=30))))", service)
                    assert signature(collection) == signature(layers)
                    outage[service] = {"http_status": 200, "same_ids_versions_values": True}
                result["redis_outage_database_fallback"] = outage
            finally:
                cluster.run(["start", *redis_services], timeout=120)
            poll(lambda: request(args.base_url, "/health"), timeout=120)
            result["redis_recovery"] = poll(converged, timeout=120)
        result["success"] = True
    except Exception as failure:
        result.update(success=False, error_class=type(failure).__name__)
        import traceback
        result['failure_location'] = [{"function": frame.name, "line": frame.lineno}
            for frame in traceback.extract_tb(failure.__traceback__)]
        # Do not include exception text: SDK/network errors can expose credentials.
    result["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "evidence": str(args.output),
        "layer_count": result.get("layer_count"), "error_class": result.get("error_class")}))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
