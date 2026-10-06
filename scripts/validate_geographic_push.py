"""Inspect the isolated full geographic-push flow without exposing credentials.

Usage (root coordinates the already-running ecopulse-fcm-test project):
  python scripts/validate_geographic_push.py
  python scripts/validate_geographic_push.py --mode inspect --env-file .env --compose-file infra/compose.cluster.yaml --compose-file infra/compose.phone-test.yaml
  python scripts/validate_geographic_push.py --mode prepare --allow-registration --env-file .env --compose-file infra/compose.cluster.yaml --compose-file infra/compose.phone-test.yaml
  # Explicit alternative when the phone is elsewhere within the RP region:
  python scripts/validate_geographic_push.py --mode prepare --allow-registration --use-coarse-demo-grid --env-file .env --compose-file infra/compose.cluster.yaml --compose-file infra/compose.phone-test.yaml
  python scripts/validate_geographic_push.py --mode trigger --allow-send --env-file .env --compose-file infra/compose.cluster.yaml --compose-file infra/compose.phone-test.yaml

Default mode, plan, performs no network/Docker/file mutation. Inspect performs
only GET /health and SELECTs in the existing project's API container. Prepare
registers two fictional web devices (inside/outside); it never registers a phone,
creates a report, or calls FCM. The phone registers its own token/position through
the app, connected to this isolated project's API. No token-file option exists.

Trigger requires --allow-send, a prepared state and exactly one registered Android
with a fresh position inside the planned radius. It creates ONE fictional report
and repeats the identical POST to check UUID idempotency. Full workers can send a
real FCM notification; use this mode only after the phone owner is ready and has
authorized that fictional notification. --synthetic-only instead requires zero
Android/iOS devices and exercises web selection with no provider call.

The default test point is the public RP centre rounded to two decimals. Explicit
prepare --use-coarse-demo-grid resolves the sole fresh/token-bearing Android's
position inside the container and rounds latitude/longitude to a 0.01-degree
grid (about 1 km spacing). Only that fictional rounded point is stored in state;
raw GPS/accuracy values are neither returned, printed nor persisted. The chosen
point must remain within 50 km of RP and within 1000 + incident-influence metres
of the phone, also respecting its actual subscription radius. Outside RP is
refused and requires user action. The .runtime state is private and excluded
from the source ZIP; even the rounded point is omitted from public evidence.
These are demonstration coordinates, never a claim of precise GPS. Dispatch
uses device radius + incident influence (normally 1000 + 200 metres), whereas the
mobile local warning uses 1000 metres. Gravity does not gate backend delivery.
Web-inside must record unsupported; web-outside must have no delivery. Android
accepted means provider acceptance, not independently verified physical receipt.
This script does not inject retries, replay RabbitMQ messages, start/stop Docker,
read host .env/service-account/token files, initialize schemas, or change the
demo/previous validation projects. State under .runtime contains only fictional
UUIDs/report payload and flags; JWTs remain in the container's process memory.

Add --output docs/evidence/geographic-push.json for sanitized evidence. Inspect
can be repeated with --wait-seconds 45 to observe outbox/consumer convergence.
Compose loads its own environment file; stdout/stderr from failures are never
echoed. Base infra/compose.yaml is implicit; --compose-file adds each overlay in
order. Use the same overlays/environment as root used to start the test project.
"""
import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import time
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "ecopulse-fcm-test"
REGION_CENTER = {"latitude": -21.1775, "longitude": -47.8101}
DEFAULT_TEST_CENTER = {key: round(value, 2) for key, value in REGION_CENTER.items()}

COMMON = r'''
import json, urllib.request, urllib.error
from datetime import timedelta
from sqlalchemy import select, func, text
from backend.shared.config import Settings
from backend.shared.db import (Store, devices, relatos, incidentes, links, outbox,
    processed, deliveries, utc_now, parse_time, iso)
from backend.alerts.main import geographic_devices
from backend.shared.models import RelatoRequest
from backend.shared.geo import distance_m

settings = Settings().validate()
if settings.mode != 'full' or not settings.database_url.startswith('postgresql'):
    raise RuntimeError('isolated_full_required')
store = Store(settings)  # No initialize(), DDL or transaction() writes.
if distance_m(REGION_CENTER['latitude'], REGION_CENTER['longitude'],
    CENTER['latitude'], CENTER['longitude']) > 50000:
    raise RuntimeError('test_center_outside_ribeirao_region')

def http(method, path, body=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    encoded = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request('http://127.0.0.1:8000' + path,
        data=encoded, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as failure:
        raise RuntimeError('api_http_' + str(failure.code)) from None

def session(installation):
    return http('POST', '/v1/sessoes', {'installation_id': installation})[1]['access_token']

def summary():
    _, health = http('GET', '/health')
    if health.get('mode') != 'full':
        raise RuntimeError('isolated_full_required')
    with store.engine.connect() as conn:
        conn.execute(text('SET TRANSACTION READ ONLY'))
        counts = {name: conn.execute(select(func.count()).select_from(table)).scalar_one()
            for name, table in [('reports', relatos), ('incidents', incidentes),
                ('devices', devices), ('deliveries', deliveries)]}
        rows = list(conn.execute(select(devices)).mappings())
        report = conn.execute(select(relatos).where(relatos.c.id == STATE['report_id'])).mappings().first()
        association = list(conn.execute(select(links).where(links.c.relato_id == STATE['report_id'])).mappings())
        current = None
        if association:
            current = conn.execute(select(incidentes).where(incidentes.c.id == association[0]['incidente_id'])).mappings().first()
        related = list(conn.execute(select(outbox).where(outbox.c.event['aggregate_id'].as_string()
            .in_([STATE['report_id']] + ([current['id']] if current else [])))).mappings())
        accepted = set(conn.execute(select(processed.c.consumer, processed.c.event_id)).all())
        delivery_rows = list(conn.execute(select(deliveries)).mappings())
        pending = conn.execute(select(func.count()).select_from(outbox)
            .where(outbox.c.published.is_(False))).scalar_one()
    now = utc_now()
    planned = {'properties': {'center_latitude': CENTER['latitude'],
        'center_longitude': CENTER['longitude'], 'radius_m': settings.influence_m,
        'expires_at': iso(now + timedelta(minutes=5))}}
    feature = current['data'] if current else planned
    eligible = {row['id'] for row in geographic_devices(store, feature, now)}
    report_events = [row for row in related if row['event']['tipo'] == 'relato.criado']
    incident_events = [row for row in related if row['event']['tipo'] in {'incidente.criado', 'incidente.atualizado'}]
    event_ids = [row['id'] for row in incident_events]

    def status_for(installation):
        return [row['status'] for row in delivery_rows
            if row['id'] in {installation + ':' + event_id for event_id in event_ids}]

    def fresh(data):
        return (data.get('latitude') is not None and data.get('longitude') is not None
            and bool(data.get('position_at'))
            and now - timedelta(seconds=settings.position_valid_s) <= parse_time(data['position_at'])
            <= now + timedelta(minutes=5))

    synthetic = {}
    for alias in ('inside', 'outside'):
        installation = STATE['installations'][alias]
        row = next((item for item in rows if item['id'] == installation), None)
        synthetic[alias] = {'registered': row is not None,
            'platform_web': bool(row and row['data'].get('platform') == 'web'),
            'token_present': bool(row and row['data'].get('token')),
            'fresh_position': bool(row and fresh(row['data'])),
            'selected_by_current_geofence': installation in eligible,
            'delivery_statuses': status_for(installation)}
    phones = [row for row in rows if row['data'].get('platform') == 'android']
    ios = [row for row in rows if row['data'].get('platform') == 'ios']
    phone_statuses = [status for row in phones for status in status_for(row['id'])]
    android = {'registered_count': len(phones),
        'token_present_count': sum(bool(row['data'].get('token')) for row in phones),
        'position_present_count': sum(row['data'].get('latitude') is not None
            and row['data'].get('longitude') is not None and bool(row['data'].get('position_at')) for row in phones),
        'fresh_position_count': sum(fresh(row['data']) for row in phones),
        'accuracy_present_count': sum(row['data'].get('accuracy_m') is not None for row in phones),
        'selected_by_current_geofence_count': sum(row['id'] in eligible for row in phones),
        'provider_accepted_count': phone_statuses.count('accepted'),
        'delivery_status_counts': {value: phone_statuses.count(value) for value in set(phone_statuses)},
        'device_receipt_verified': False}
    report_ok = bool(report and report['data'].get('is_demo') is True
        and report['installation_id'] == STATE['installations']['reporter'])
    payload_matches = False
    if report_ok and STATE.get('report_payload'):
        wanted = RelatoRequest.model_validate(STATE['report_payload']).model_dump(mode='json')
        wanted['occurred_at'] = iso(parse_time(wanted['occurred_at']))
        payload_matches = all(report['data'].get(key) == value for key, value in wanted.items())
    risk_count = sum(('risk', row['id']) in accepted for row in report_events)
    alerts_count = sum(('alerts', row['id']) in accepted for row in incident_events)
    complete = (report_ok and payload_matches and counts['reports'] == 1 and len(association) == 1
        and len(report_events) == len(incident_events) == 1
        and all(row['published'] for row in related) and risk_count == alerts_count == 1
        and synthetic['inside']['delivery_statuses'] == ['unsupported']
        and synthetic['outside']['delivery_statuses'] == []
        and (android['provider_accepted_count'] == 1 if STATE.get('phone_expected') else not phones))
    return {'health': {'status': health.get('status'), 'mode': health.get('mode'),
            'fcm_configured_in_api': bool(health.get('configuration', {}).get('fcm_configured'))},
        'counts': counts, 'outbox_pending': pending, 'synthetic': synthetic,
        'android': android, 'ios_registered_count': len(ios),
        'selection_rule': {'device_radius_m': 1000, 'incident_influence_m': settings.influence_m,
            'default_total_radius_m': 1000 + settings.influence_m,
            'position_valid_seconds': settings.position_valid_s,
            'high_severity_required': False},
        'pipeline': {'fictional_report_present': report_ok, 'immutable_report_payload_matches': payload_matches,
            'report_to_incident_links': len(association),
            'incident_report_count': current['data']['properties']['report_count'] if current else 0,
            'report_outbox_events': len(report_events), 'incident_outbox_events': len(incident_events),
            'related_outbox_published': sum(row['published'] for row in related),
            'risk_processed_count': risk_count, 'alerts_processed_count': alerts_count,
            'complete': bool(complete)}}
'''

INSPECT = "print(json.dumps(summary()))\n"

COARSE_GRID = r'''
with store.engine.connect() as conn:
    conn.execute(text('SET TRANSACTION READ ONLY'))
    phones = [row for row in conn.execute(select(devices)).mappings()
        if row['data'].get('platform') == 'android']
if len(phones) != 1:
    raise RuntimeError('exactly_one_android_required_for_grid')
data = phones[0]['data']
now = utc_now()
if not (data.get('token') and data.get('latitude') is not None
    and data.get('longitude') is not None and data.get('position_at')
    and now - timedelta(seconds=settings.position_valid_s) <= parse_time(data['position_at'])
    <= now + timedelta(minutes=5)):
    raise RuntimeError('fresh_android_position_and_token_required_for_grid')
if distance_m(REGION_CENTER['latitude'], REGION_CENTER['longitude'],
    data['latitude'], data['longitude']) > 50000:
    raise RuntimeError('android_outside_ribeirao_region')
coarse = {'latitude': round(data['latitude'], 2), 'longitude': round(data['longitude'], 2)}
if distance_m(REGION_CENTER['latitude'], REGION_CENTER['longitude'],
    coarse['latitude'], coarse['longitude']) > 50000:
    raise RuntimeError('coarse_grid_outside_ribeirao_region')
delta = distance_m(coarse['latitude'], coarse['longitude'], data['latitude'], data['longitude'])
if delta > 1000 + settings.influence_m or delta > data.get('radius_m', 1000) + settings.influence_m:
    raise RuntimeError('coarse_grid_outside_phone_radius')
print(json.dumps({'test_center': coarse}))
'''

PREPARE = r'''
before = summary()
if any(before['counts'][name] for name in ('reports', 'incidents', 'deliveries')) or before['outbox_pending']:
    raise RuntimeError('fresh_test_database_required')
statuses = {}
for alias in ('inside', 'outside'):
    token = session(STATE['installations'][alias])
    fake_token = 'ecopulse-fictional-web-only-' + STATE['installations'][alias]
    registered, _ = http('PUT', '/v1/dispositivos/push',
        {'token': fake_token, 'platform': 'web', 'radius_m': 1000}, token)
    positioned, _ = http('POST', '/v1/dispositivos/posicao',
        {**POINTS[alias], 'position_at': iso(utc_now()), 'radius_m': 1000}, token)
    statuses[alias] = {'registration_http': registered, 'position_http': positioned}
print(json.dumps({'registration': statuses, 'inspection': summary()}))
'''

TRIGGER = r'''
before = summary()
synthetic = before['synthetic']
if not all(synthetic[alias]['registered'] and synthetic[alias]['platform_web']
    and synthetic[alias]['token_present'] and synthetic[alias]['fresh_position'] for alias in ('inside', 'outside')):
    raise RuntimeError('prepare_required')
if not synthetic['inside']['selected_by_current_geofence'] or synthetic['outside']['selected_by_current_geofence']:
    raise RuntimeError('synthetic_selection_not_ready')
if before['ios_registered_count']:
    raise RuntimeError('unexpected_ios_device')
phone = before['android']
if STATE['phone_expected']:
    if not (phone['registered_count'] == phone['token_present_count'] == phone['fresh_position_count']
        == phone['selected_by_current_geofence_count'] == 1 and before['health']['fcm_configured_in_api']):
        raise RuntimeError('exactly_one_ready_android_required')
elif phone['registered_count']:
    raise RuntimeError('synthetic_only_requires_no_phone')
if before['counts']['devices'] != 2 + int(STATE['phone_expected']):
    raise RuntimeError('unexpected_device')
if before['counts']['reports'] > 1 or (before['counts']['reports'] == 1
    and not before['pipeline']['immutable_report_payload_matches']):
    raise RuntimeError('unexpected_report')
token = session(STATE['installations']['reporter'])
first, _ = http('POST', '/v1/relatos', STATE['report_payload'], token)
replay, _ = http('POST', '/v1/relatos', STATE['report_payload'], token)
print(json.dumps({'report_http': first, 'identical_replay_http': replay,
    'identical_replay_accepted': first in (200, 201) and replay == 200,
    'inspection': summary()}))
'''


class ValidationFailure(RuntimeError):
    """Only constant, sanitized error codes may cross the process boundary."""


def contained_path(value, roots):
    path = (ROOT / value).resolve()
    if not any(path.is_relative_to(root.resolve()) for root in roots):
        raise ValidationFailure("output_or_state_outside_allowed_directory")
    return path


def state_path(value):
    return contained_path(value, [ROOT / ".runtime"])


def fresh_state():
    return {"schema_version": 1, "project": PROJECT, "prepared": False,
        "installations": {alias: str(uuid4()) for alias in ("inside", "outside", "reporter")},
        "report_id": str(uuid4()), "report_payload": None, "phone_expected": False,
        "test_center": dict(DEFAULT_TEST_CENTER)}


def validate_state(state):
    if state.get("schema_version") != 1 or state.get("project") != PROJECT:
        raise ValidationFailure("state_project_mismatch")
    try:
        for alias in ("inside", "outside", "reporter"):
            UUID(state["installations"][alias])
        UUID(state["report_id"])
    except (KeyError, ValueError, TypeError):
        raise ValidationFailure("invalid_fictional_state") from None
    allowed = {"schema_version", "project", "prepared", "installations", "report_id", "report_payload", "phone_expected", "test_center"}
    if set(state) != allowed or set(state["installations"]) != {"inside", "outside", "reporter"}:
        raise ValidationFailure("unexpected_state_fields")
    if not isinstance(state["prepared"], bool) or not isinstance(state["phone_expected"], bool):
        raise ValidationFailure("invalid_state_flags")
    center = state["test_center"]
    if not isinstance(center, dict) or set(center) != {"latitude", "longitude"}:
        raise ValidationFailure("invalid_coarse_test_center")
    for key, limit in (("latitude", 85), ("longitude", 180)):
        value = center[key]
        if (type(value) not in (float, int) or not math.isfinite(value)
                or abs(value) > limit or round(value, 2) != value):
            raise ValidationFailure("test_center_must_use_two_decimal_grid")
    payload = state["report_payload"]
    if payload is not None:
        expected_keys = {"id", "tipo", "gravidade", "latitude", "longitude", "descricao", "occurred_at", "position_source", "is_demo"}
        if not isinstance(payload, dict) or set(payload) != expected_keys or not (
            payload["id"] == state["report_id"] and payload["is_demo"] is True
            and payload["position_source"] == "demo" and payload["tipo"] == "obstrucao"
            and payload["gravidade"] == "baixa" and payload["latitude"] == center["latitude"]
            and payload["longitude"] == center["longitude"]
            and payload["descricao"] == "TESTE FICTICIO APS - fluxo geografico isolado, sem risco real"
        ):
            raise ValidationFailure("state_report_must_remain_fictional")
    return state


def read_state(path):
    if not path.is_file():
        return fresh_state()
    state = json.loads(path.read_text(encoding="utf-8"))
    # No report has been posted: old preparatory UUIDs can safely be retained,
    # but re-preparation is required before the new test point can be triggered.
    if "test_center" not in state and state.get("report_payload") is None:
        state["test_center"] = dict(DEFAULT_TEST_CENTER)
        state["prepared"] = False
    return validate_state(state)


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def code_for(state):
    center = state["test_center"]
    points = {"inside": center,
        "outside": {"latitude": round(center["latitude"] + .04, 2), "longitude": center["longitude"]}}
    return ("STATE = json.loads(" + repr(json.dumps(state)) + ")\n"
        + "REGION_CENTER = json.loads(" + repr(json.dumps(REGION_CENTER)) + ")\n"
        + "CENTER = json.loads(" + repr(json.dumps(center)) + ")\n"
        + "POINTS = json.loads(" + repr(json.dumps(points)) + ")\n")


def container_program(state, operation):
    # Prelude needs json before decoding data; all inputs are JSON, never code.
    return "import json\n" + code_for(state) + COMMON + operation


class Cluster:
    def __init__(self, args):
        executable = shutil.which("docker")
        fallback = Path.home() / "AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe"
        if not executable and fallback.is_file():
            executable = str(fallback)
        if not executable:
            raise ValidationFailure("docker_executable_unavailable")
        self.executable = executable
        self.command = [executable, "compose", "-p", PROJECT, "--env-file", str(ROOT / args.env_file),
            "-f", str(ROOT / "infra/compose.yaml")]
        for file in args.compose_file:
            self.command.extend(["-f", str(ROOT / file)])

    @staticmethod
    def run(command, code=None):
        try:
            result = subprocess.run(command, cwd=ROOT, input=code, text=True,
                encoding="utf-8", errors="replace", capture_output=True, timeout=90)
        except (OSError, subprocess.TimeoutExpired):
            raise ValidationFailure("isolated_runtime_unavailable") from None
        if result.returncode:
            raise ValidationFailure("isolated_runtime_operation_failed")
        return result.stdout

    def verify(self):
        identifiers = self.run(self.command + ["ps", "-q", "api"]).strip().splitlines()
        if len(identifiers) != 1:
            raise ValidationFailure("exactly_one_test_api_required")
        labels = json.loads(self.run([self.executable, "inspect", "--format", "{{json .Config.Labels}}", identifiers[0]]))
        if labels.get("com.docker.compose.project") != PROJECT or labels.get("com.docker.compose.service") != "api":
            raise ValidationFailure("container_project_mismatch")

    def python(self, state, operation):
        return json.loads(self.run(self.command + ["exec", "-T", "api", "python", "-"],
            container_program(state, operation)))

    def require_alerts_running(self):
        identifiers = self.run(self.command + ["ps", "-q", "alerts"]).strip().splitlines()
        if len(identifiers) != 1:
            raise ValidationFailure("exactly_one_running_test_alert_service_required")
        labels = json.loads(self.run([self.executable, "inspect", "--format", "{{json .Config.Labels}}", identifiers[0]]))
        running = self.run([self.executable, "inspect", "--format", "{{.State.Running}}", identifiers[0]]).strip()
        if labels.get("com.docker.compose.project") != PROJECT or running != "true":
            raise ValidationFailure("test_alert_service_not_running")


def plan():
    return {"default_has_no_side_effects": True, "project": PROJECT,
        "stages": {"inspect": "GET health and SELECT counts only in the existing test container",
            "prepare": "explicitly register two fictional web devices, no report or phone",
            "trigger": "explicitly create one simulated report; full dispatcher can call FCM"},
        "endpoints": ["POST /v1/sessoes", "PUT /v1/dispositivos/push",
            "POST /v1/dispositivos/posicao", "POST /v1/relatos"],
        "authorization": "anonymous installation session, Bearer kept only in process memory",
        "fictional_report": {"type": "obstrucao", "severity": "baixa", "is_demo": True,
            "position_source": "demo", "high_severity_required": False},
        "expected_selection": {"synthetic_web_inside": "unsupported, no FCM call",
            "synthetic_web_outside": "no delivery", "optional_self_registered_android": "accepted, receipt not verified"},
        "limits": ["FCM acceptance is not physical receipt", "no retry/redelivery injection",
            "no GPS movement, iOS, background/foreground presentation or availability proof"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=("plan", "inspect", "prepare", "trigger"), default="plan")
    parser.add_argument("--env-file", default=".env", help="Compose loads this; script does not read it")
    parser.add_argument("--compose-file", action="append", default=[], help="additional Compose overlays, in order")
    parser.add_argument("--state-file", default=".runtime/geographic-push-state.json")
    parser.add_argument("--allow-registration", action="store_true")
    parser.add_argument("--use-coarse-demo-grid", action="store_true", help="prepare only: private rounded demo grid from the sole eligible Android")
    parser.add_argument("--allow-send", action="store_true")
    parser.add_argument("--synthetic-only", action="store_true", help="trigger requires zero Android/iOS devices")
    parser.add_argument("--wait-seconds", type=int, default=0, choices=range(0, 61), metavar="0..60")
    parser.add_argument("--output", help="sanitized JSON, only under docs/evidence or .runtime")
    args = parser.parse_args(argv)
    result = {"schema_version": 1, "mode": args.mode, "project": PROJECT,
        "device_receipt_verified": False, "broker_retry_injected": False, "status": "PENDING"}
    exit_code = 0
    try:
        if args.use_coarse_demo_grid and args.mode != "prepare":
            raise ValidationFailure("coarse_demo_grid_requires_prepare_mode")
        if args.mode == "plan":
            result.update(status="PLAN", plan=plan())
        else:
            if args.mode == "prepare" and not args.allow_registration:
                raise ValidationFailure("prepare_requires_allow_registration")
            if args.mode == "trigger" and not args.allow_send:
                raise ValidationFailure("trigger_requires_allow_send")
            path = state_path(args.state_file)
            state = read_state(path)
            cluster = Cluster(args)
            cluster.verify()
            if args.mode == "prepare":
                if state.get("report_payload"):
                    raise ValidationFailure("prepared_report_state_cannot_be_replaced")
                if args.use_coarse_demo_grid:
                    state["test_center"] = cluster.python(state, COARSE_GRID)["test_center"]
                    validate_state(state)
                    result["coarse_demo_grid_used"] = True
                save_state(path, state)  # Keep UUIDs if a registration response is lost.
                result.update(cluster.python(state, PREPARE))
                state["prepared"] = True
                save_state(path, state)
                result["status"] = "PREPARED"
            elif args.mode == "trigger":
                if not state.get("prepared"):
                    raise ValidationFailure("prepare_required")
                cluster.require_alerts_running()
                expected_phone = not args.synthetic_only
                if state.get("report_payload") and state["phone_expected"] != expected_phone:
                    raise ValidationFailure("existing_trigger_phone_mode_mismatch")
                state["phone_expected"] = expected_phone
                if not state.get("report_payload"):
                    from datetime import datetime, timezone
                    state["report_payload"] = {"id": state["report_id"], "tipo": "obstrucao",
                        "gravidade": "baixa", **state["test_center"], "descricao": "TESTE FICTICIO APS - fluxo geografico isolado, sem risco real",
                        "occurred_at": datetime.now(timezone.utc).isoformat(), "position_source": "demo", "is_demo": True}
                save_state(path, state)  # Immutable payload permits an idempotent retry.
                result.update(cluster.python(state, TRIGGER))
                result["status"] = "TRIGGERED_PENDING_INSPECTION"
            else:
                result["inspection"] = cluster.python(state, INSPECT)
            deadline = time.monotonic() + args.wait_seconds
            while (args.mode in {"inspect", "trigger"} and args.wait_seconds
                    and not result["inspection"]["pipeline"]["complete"] and time.monotonic() < deadline):
                time.sleep(min(1, max(0, deadline - time.monotonic())))
                result["inspection"] = cluster.python(state, INSPECT)
            if args.mode in {"inspect", "trigger"}:
                result["status"] = "PASSED" if result["inspection"]["pipeline"]["complete"] else "PENDING"
    except Exception as failure:
        result["status"] = "BLOCKED"
        result["error"] = str(failure) if isinstance(failure, ValidationFailure) else "inspection_or_configuration_failed"
        exit_code = 2
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        try:
            output = contained_path(args.output, [ROOT / "docs/evidence", ROOT / ".runtime"])
            if output == state_path(args.state_file):
                raise ValidationFailure("evidence_cannot_replace_state")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered + "\n", encoding="utf-8")
        except Exception:
            print(json.dumps({"status": "BLOCKED", "error": "invalid_evidence_output"}))
            return 2
    print(rendered)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
