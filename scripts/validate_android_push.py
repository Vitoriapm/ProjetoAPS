"""Additional Android checks in existing ecopulse-fcm-test, without exposing tokens.

plan is inert; inspect is read-only. foreground-send makes ONE direct, explicitly
fictional FCM send, after phone readiness is confirmed. outside-trigger creates
ONE fictional report only if the sole Android has a recent position outside the
planned geofence. It never edits a phone registration or its position. Each case
has immutable private state. Physical receipt is recorded separately by the user.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.validate_geographic_push import Cluster
STATE_PATH = ROOT / '.runtime/android-final-tests-state.json'
COMMON = r'''
import json, urllib.request
from datetime import timedelta
from sqlalchemy import select, text
from backend.shared.config import Settings
from backend.shared.db import Store, devices, relatos, links, outbox, processed, deliveries, utc_now, parse_time, iso
from backend.shared.geo import distance_m
from backend.alerts.main import geographic_devices, FcmAdapter
s = Settings().validate()
assert s.mode == 'full' and s.database_url.startswith('postgresql')
store = Store(s)
def phone():
    with store.engine.connect() as c:
        c.execute(text('SET TRANSACTION READ ONLY'))
        rows = list(c.execute(select(devices)).mappings())
    native = [r for r in rows if r['data'].get('platform') in {'android', 'ios'} and r['data'].get('token')]
    assert len(native) == 1 and native[0]['data']['platform'] == 'android', 'sole_android_required'
    assert native[0]['data'].get('token'), 'android_token_required'
    return native[0]
def ready():
    row = phone()
    d = row['data']
    positioned = all(d.get(k) is not None for k in ('latitude', 'longitude', 'position_at'))
    fresh = bool(positioned and utc_now() - timedelta(seconds=120)
        <= parse_time(d['position_at']) <= utc_now() + timedelta(seconds=30))
    total = d.get('radius_m', 1000) + s.influence_m
    outside = bool(positioned and distance_m(d['latitude'], d['longitude'], -21.1775, -47.8101) > total + 200)
    return {'one_android_registered': True, 'token_present': True,
        'position_present': positioned, 'position_recent_120s': fresh,
        'accuracy_present': d.get('accuracy_m') is not None,
        'outside_reference_geofence_with_200m_margin': outside,
        'fcm_configured': bool(s.fcm_credentials)}
def http(method, path, payload, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request('http://127.0.0.1:8000' + path,
        data=json.dumps(payload).encode(), headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.status, json.load(response)
def outside_summary():
    row = phone()
    with store.engine.connect() as c:
        c.execute(text('SET TRANSACTION READ ONLY'))
        report = c.execute(select(relatos).where(relatos.c.id == STATE['outside_report_id'])).mappings().first()
        associations = list(c.execute(select(links).where(links.c.relato_id == STATE['outside_report_id'])).mappings())
        report_events = list(c.execute(select(outbox).where(outbox.c.event['aggregate_id'].as_string() == STATE['outside_report_id'])).mappings())
        trace_ids = [e['event']['trace_id'] for e in report_events]
        related = list(c.execute(select(outbox).where(outbox.c.event['trace_id'].as_string().in_(trace_ids))).mappings()) if trace_ids else []
        done = set(c.execute(select(processed.c.consumer, processed.c.event_id)).all())
        statuses = []
        incident_events = [e for e in related if e['event']['tipo'] in {'incidente.criado', 'incidente.atualizado'}]
        for e in incident_events:
            status = c.execute(select(deliveries.c.status).where(deliveries.c.id == row['id'] + ':' + e['id'])).scalar_one_or_none()
            if status is not None:
                statuses.append(status)
    rejected = bool(incident_events and all(row['id'] not in {r['id'] for r in geographic_devices(store, e['event']['payload'])} for e in incident_events))
    complete = (bool(report and report['data']['is_demo']) and len(associations) == len(report_events) == len(incident_events) == 1
        and all(e['published'] for e in related)
        and ('risk', report_events[0]['id']) in done and ('alerts', incident_events[0]['id']) in done
        and rejected and not statuses)
    return {'report_present': report is not None, 'report_to_incident_links': len(associations),
        'report_events': len(report_events), 'incident_events': len(incident_events),
        'risk_processed': sum(('risk', e['id']) in done for e in report_events),
        'alerts_processed': sum(('alerts', e['id']) in done for e in incident_events),
        'related_outbox_published': sum(e['published'] for e in related),
        'android_excluded_by_current_geofence': rejected, 'android_delivery_statuses': statuses,
        'complete': complete}
'''
FOREGROUND = r'''
row = phone()
assert s.fcm_credentials
event = {'event_id': STATE['foreground_event_id'], 'payload': {'type': 'Feature',
    'geometry': {'type': 'Point', 'coordinates': [-47.8101, -21.1775]},
    'properties': {'id': STATE['foreground_incident_id'], 'version': 1, 'is_demo': True,
        'expires_at': iso(utc_now() + timedelta(minutes=5))}}}
FcmAdapter(s).send(row['data']['token'], event, dry_run=False)
print(json.dumps({'provider_accepted': True, 'direct_fcm_only': True,
    'geographic_pipeline_tested': False, 'device_receipt_verified': False}))
'''
OUTSIDE = r'''
assert ready()['position_recent_120s'] and ready()['outside_reference_geofence_with_200m_margin']
if STATE.get('outside_position_source') == 'gps':
    assert ready()['accuracy_present'], 'gps_accuracy_metadata_required'
planned = {'properties': {'center_latitude': -21.1775, 'center_longitude': -47.8101,
    'radius_m': s.influence_m, 'expires_at': iso(utc_now() + timedelta(minutes=5))}}
assert not [r for r in geographic_devices(store, planned) if r['data'].get('platform') in {'android', 'ios'}]
_, session = http('POST', '/v1/sessoes', {'installation_id': STATE['reporter_installation_id']})
token = session['access_token']
first, _ = http('POST', '/v1/relatos', STATE['outside_payload'], token)
replay, _ = http('POST', '/v1/relatos', STATE['outside_payload'], token)
print(json.dumps({'report_http': first, 'replay_http': replay, 'inspection': outside_summary()}))
'''


def state():
    if STATE_PATH.exists():
        value = json.loads(STATE_PATH.read_text(encoding='utf-8'))
    else:
        value = {'project': 'ecopulse-fcm-test', 'foreground_attempted': False,
            **{key: str(uuid4()) for key in ('foreground_event_id', 'foreground_incident_id', 'outside_report_id', 'reporter_installation_id')}}
    assert value['project'] == 'ecopulse-fcm-test'
    for key in ('foreground_event_id', 'foreground_incident_id', 'outside_report_id', 'reporter_installation_id'):
        UUID(value[key])
    return value


def save(value):
    STATE_PATH.parent.mkdir(exist_ok=True)
    STATE_PATH.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def call(cluster, value, code):
    program = 'import json\nSTATE=json.loads(' + repr(json.dumps(value)) + ')\n' + COMMON + code
    return json.loads(cluster.run(cluster.command + ['exec', '-T', 'api', 'python', '-'], program))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['plan', 'inspect', 'foreground-send', 'outside-trigger', 'outside-inspect'], default='plan')
    parser.add_argument('--allow-send', action='store_true')
    parser.add_argument('--position-source', choices=['manual', 'gps'], default='manual', help='outside test: source the user selected in the app')
    parser.add_argument('--output', help='sanitized result under docs/evidence or .runtime')
    args = parser.parse_args(argv)
    result = {'status': 'PLAN', 'mode': args.mode, 'project': 'ecopulse-fcm-test',
        'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'is_demo': True,
        'device_receipt_verified': False, 'gps_movement_tested': False,
        'physical_phones': 1, 'position_source_confirmed_by_user': False}
    try:
        if args.mode != 'plan':
            value = state()
            result['outside_position_source'] = value.get('outside_position_source')
            cluster = Cluster(SimpleNamespace(env_file='.env', compose_file=['infra/compose.cluster.yaml', 'infra/compose.phone-test.yaml']))
            cluster.verify()
            if args.mode == 'inspect':
                result.update(status='INSPECTED', readiness=call(cluster, value, 'print(json.dumps(ready()))'))
            elif args.mode == 'foreground-send':
                assert args.allow_send and not value['foreground_attempted'], 'new_send_not_authorized_or_already_attempted'
                # A read-only preflight failure cannot have contacted FCM.
                result['readiness'] = call(cluster, value, 'print(json.dumps(ready()))')
                value['foreground_attempted'] = True
                save(value)  # Never blindly repeat an uncertain provider call.
                result.update(call(cluster, value, FOREGROUND), status='PROVIDER_ACCEPTED_RECEIPT_PENDING')
            elif args.mode == 'outside-trigger':
                assert args.allow_send, 'explicit_test_trigger_required'
                if not value.get('outside_payload'):
                    value['outside_position_source'] = args.position_source
                    value['outside_payload'] = {'id': value['outside_report_id'], 'tipo': 'alagamento',
                        'gravidade': 'baixa', 'latitude': -21.1775, 'longitude': -47.8101,
                        'occurred_at': datetime.now(timezone.utc).isoformat(), 'position_source': 'demo',
                        'is_demo': True, 'descricao': 'TESTE FICTICIO APS - Android fora do raio, sem risco real'}
                    save(value)
                assert value['outside_position_source'] == args.position_source, 'outside_source_cannot_change'
                result['outside_position_source'] = value['outside_position_source']
                result.update(call(cluster, value, OUTSIDE), status='PIPELINE_PENDING')
            else:
                result['inspection'] = call(cluster, value, 'print(json.dumps(outside_summary()))')
                result['status'] = 'PASSED_BACKEND_SELECTION' if result['inspection']['complete'] else 'PIPELINE_PENDING'
    except Exception as failure:
        result.update(status='BLOCKED', error_type=type(failure).__name__)
    if args.output:
        output = (ROOT / args.output).resolve()
        assert output.is_relative_to(ROOT / 'docs/evidence') or output.is_relative_to(ROOT / '.runtime')
        assert output != STATE_PATH
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result['status'] == 'BLOCKED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
