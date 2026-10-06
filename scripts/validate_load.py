"""Bounded load test on ecopulse-load-test only; no FCM credentials/devices.

Default prints a plan. --execute requires an empty, already running project with
compose.yaml + compose.cluster.yaml + compose.load-test.yaml, port 8021. No host
secrets are read, no provider calls are made, and Docker projects are not stopped.
"""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import time
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
PROJECT = 'ecopulse-load-test'
BASE_URL = 'http://127.0.0.1:8021'
SNAPSHOT = r'''
import json
from sqlalchemy import select, func, text
from backend.shared.config import Settings
from backend.shared.db import Store, devices, relatos, incidentes, links, outbox, processed, deliveries
from backend.shared.cache import cluster_client
from backend.shared.geo import geohash
s = Settings().validate()
assert s.mode == 'full' and s.database_url.startswith('postgresql')
assert not s.fcm_credentials and not s.ors_key
store = Store(s)
with store.engine.connect() as conn:
    conn.execute(text('SET TRANSACTION READ ONLY'))
    counts = {name: conn.execute(select(func.count()).select_from(table)).scalar_one()
        for name, table in [('reports', relatos), ('incidents', incidentes), ('devices', devices), ('links', links), ('deliveries', deliveries)]}
    assert counts['devices'] == counts['deliveries'] == 0
    rows = list(conn.execute(select(relatos.c.id)).scalars())
    associations = list(conn.execute(select(links)).mappings())
    features = list(conn.execute(select(incidentes.c.data)).scalars())
    events = list(conn.execute(select(outbox)).mappings())
    done = set(conn.execute(select(processed.c.consumer, processed.c.event_id)).all())
cache = cluster_client(s)
matches = 0
for feature in features:
    p = feature['properties']
    region = geohash(p['center_latitude'], p['center_longitude'])
    raw = cache.get(f"ecopulse:incident:{{{region}}}:{p['id']}")
    if raw:
        entry = json.loads(raw)
        matches += entry['version'] == p['version'] and entry['feature'] == feature
report_events = [e for e in events if e['event']['tipo'] == 'relato.criado']
incident_events = [e for e in events if e['event']['tipo'].startswith('incidente.')]
expected = set(EXPECTED)
print(json.dumps({'counts': counts, 'expected_ids_exact': set(rows) == expected,
    'expected_link_ids_exact': {r['relato_id'] for r in associations} == expected,
    'incident_report_count_sum': sum(f['properties']['report_count'] for f in features),
    'outbox_pending': sum(not e['published'] for e in events),
    'report_events': len(report_events), 'incident_events': len(incident_events),
    'risk_processed': sum(('risk', e['id']) in done for e in report_events),
    'alerts_processed': sum(('alerts', e['id']) in done for e in incident_events),
    'cache_equal_count': matches, 'cache_all_equal': matches == len(features),
    'fcm_credentials_disabled': True, 'ors_disabled': True,
    'redis_nodes': len(cache.get_nodes()),
    'redis_slots': sum(end - start + 1 for start, end in cache.cluster_slots()),
    'postgis_used': True}))
'''


def docker():
    path = shutil.which('docker')
    fallback = Path.home() / 'AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
    return path or str(fallback)


def command(args, source=None):
    result = subprocess.run([docker(), *args], cwd=ROOT, input=source,
        capture_output=True, text=True, encoding='utf-8', timeout=30)
    if result.returncode:
        raise RuntimeError('isolated_docker_operation_failed')
    return result.stdout


def inspect(expected):
    name = PROJECT + '-api-1'
    labels = json.loads(command(['inspect', '--format', '{{json .Config.Labels}}', name]))
    assert labels['com.docker.compose.project'] == PROJECT
    assert labels['com.docker.compose.service'] == 'api'
    source = 'EXPECTED = ' + repr(expected) + '\n' + SNAPSHOT
    return json.loads(command(['exec', '-i', name, 'python', '-'], source))


def metrics(records, seconds):
    durations = sorted(r['seconds'] for r in records)
    percentile = lambda value: round(durations[max(0, math.ceil(len(durations) * value) - 1)] * 1000, 2)
    return {'requests': len(records), 'seconds': round(seconds, 3),
        'requests_per_second': round(len(records) / seconds, 2),
        'http_statuses': dict(Counter(str(r['status']) for r in records)),
        'p50_ms': percentile(.50), 'p95_ms': percentile(.95), 'p99_ms': percentile(.99)}


async def run(result):
    before = await asyncio.to_thread(inspect, [])
    assert before['counts']['reports'] == before['counts']['incidents'] == before['outbox_pending'] == 0
    result['before'] = before
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=25) as client:
        health = (await client.get('/health')).json()
        assert health['status'] == 'ok' and health['mode'] == 'full'
        assert not health['configuration']['fcm_configured'] and not health['configuration']['routes_configured']
        tokens = []
        for _ in range(8):
            response = await client.post('/v1/sessoes', json={'installation_id': str(uuid4())})
            response.raise_for_status()
            tokens.append(response.json()['access_token'])
        records, payloads = [], []
        gate = asyncio.Semaphore(8)
        async def submit(index):
            payload = {'id': str(uuid4()), 'tipo': 'obstrucao', 'gravidade': 'baixa',
                'latitude': -21.155 - (index % 20 // 5) * .006,
                'longitude': -47.830 + (index % 5) * .006,
                'occurred_at': datetime.now(timezone.utc).isoformat(),
                'position_source': 'demo', 'is_demo': True,
                'descricao': 'TESTE FICTICIO APS - carga isolada, sem risco real'}
            async with gate:
                start = time.monotonic()
                try:
                    response = await client.post('/v1/relatos', json=payload,
                        headers={'Authorization': 'Bearer ' + tokens[index % 8]})
                    status = response.status_code
                except httpx.HTTPError:
                    status = 0
                record = {'id': payload['id'], 'status': status, 'seconds': time.monotonic() - start}
                records.append(record)
                payloads.append((index, payload))
                return record
        start_all = time.monotonic()
        sustained_start = time.monotonic()
        tasks = []
        for index in range(500):
            target = sustained_start + index / 20
            await asyncio.sleep(max(0, target - time.monotonic()))
            tasks.append(asyncio.create_task(submit(index)))
        sustained = await asyncio.gather(*tasks)
        result['sustained'] = metrics(sustained, time.monotonic() - sustained_start)
        burst_start = time.monotonic()
        burst = await asyncio.gather(*(submit(i) for i in range(500, 1000)))
        result['burst'] = metrics(burst, time.monotonic() - burst_start)
        result['entry'] = metrics(records, time.monotonic() - start_all)
        expected = [r['id'] for r in records]
        assert all(r['status'] == 201 for r in records), 'unexpected_http_result'
        deadline = time.monotonic() + 120
        while True:
            snapshot = await asyncio.to_thread(inspect, expected)
            ready = (snapshot['expected_ids_exact'] and snapshot['expected_link_ids_exact']
                and snapshot['incident_report_count_sum'] == snapshot['risk_processed'] == 1000
                and snapshot['outbox_pending'] == 0 and snapshot['alerts_processed'] == snapshot['incident_events']
                and snapshot['cache_all_equal'])
            if ready or time.monotonic() >= deadline:
                break
            await asyncio.sleep(2)
        result['convergence_seconds_from_start'] = round(time.monotonic() - start_all, 3)
        result['after'] = snapshot
        assert ready, 'pipeline_convergence_timeout'
        replay_statuses = []
        for index, payload in sorted(payloads)[:20]:
            response = await client.post('/v1/relatos', json=payload,
                headers={'Authorization': 'Bearer ' + tokens[index % 8]})
            replay_statuses.append(response.status_code)
        assert replay_statuses == [200] * 20
        after_replay = await asyncio.to_thread(inspect, expected)
        assert after_replay['counts'] == snapshot['counts'] and after_replay['report_events'] == 1000
        result['replay'] = {'requests': 20, 'http_200': 20, 'counts_unchanged': True}
        result['status'] = 'PASSED'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--output', default='docs/evidence/load-extended.json')
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    assert output.is_relative_to(ROOT / 'docs/evidence') or output.is_relative_to(ROOT / '.runtime')
    result = {'status': 'PLAN', 'project': PROJECT,
        'started_at_utc': datetime.now(timezone.utc).isoformat(), 'reports': 1000,
        'sustained_target_rps': 20, 'maximum_concurrent_posts': 8, 'geographic_groups': 20,
        'is_demo': True, 'physical_hosts': 1, 'providers_contacted': False,
        'phone_project_modified': False, 'postgres_replication_tested': False,
        'websocket_receipt_tested': False,
        'limitation': 'Bounded local synthetic load; not a capacity ceiling, production SLA or proof of multiple-host resilience.'}
    if args.execute:
        try:
            asyncio.run(run(result))
        except Exception as failure:
            result.update(status='FAILED', error_type=type(failure).__name__)
        result['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        result['backend_source_sha256'] = hashlib.sha256((ROOT / 'backend/shared/db.py').read_bytes()).hexdigest()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] in {'PLAN', 'PASSED'} else 2


if __name__ == '__main__':
    raise SystemExit(main())
