"""Live, credential-free display of the isolated RabbitMQ/Redis demonstration."""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import threading
import time
from uuid import UUID, uuid4

import httpx
import websockets

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.check_integration_config import project_environment

PROJECT = 'ecopulse-apresentacao'
BASE = 'http://127.0.0.1:8011'
RABBIT = 'http://127.0.0.1:15674'
STATE = ROOT / '.runtime/apresentacao-dsd-session.json'
EVIDENCE = ROOT / '.runtime/apresentacao-dsd-validacao.json'
LOCK = threading.RLock()
ACTION_LOCK = threading.Lock()

INSPECT = r'''
from sqlalchemy import select
from backend.shared.config import Settings
from backend.shared.db import Store, relatos, incidentes, links, outbox, processed
from backend.shared.cache import cluster_client
from backend.shared.geo import geohash
s = Settings().validate()
assert s.mode == 'full'
store = Store(s)
result = {'report_id': report_id, 'report_saved': False, 'incident_id': None,
          'cache_present': False, 'cache_matches_database': False}
with store.engine.connect() as connection:
    row = connection.execute(select(relatos.c.data).where(relatos.c.id == report_id)).scalar_one_or_none() if report_id else None
    if row is not None:
        assert row.get('is_demo') is True, 'only_demonstration_reports'
        result['report_saved'] = True
    incident_id = connection.execute(select(links.c.incidente_id).where(links.c.relato_id == report_id)).scalar_one_or_none() if row else None
    feature = connection.execute(select(incidentes.c.data).where(incidentes.c.id == incident_id)).scalar_one_or_none() if incident_id else None
    event_rows = list(connection.execute(select(outbox.c.id, outbox.c.event, outbox.c.published)).mappings())
    selected = [event for event in event_rows if str(event['event'].get('aggregate_id')) in {report_id, incident_id}]
    result['outbox_events'] = len(selected)
    result['outbox_published'] = sum(bool(event['published']) for event in selected)
    done = set(connection.execute(select(processed.c.consumer, processed.c.event_id)).all())
    result['risk_processed'] = any(('risk', event['id']) in done for event in selected)
    result['alerts_processed'] = any(('alerts', event['id']) in done for event in selected)
cache = cluster_client(s)
try:
    nodes = list(cache.get_nodes())
    result['redis_nodes'] = len(nodes)
    result['redis_primaries'] = sum(node.server_type == 'primary' for node in nodes)
    if feature:
        props = feature['properties']
        key = 'ecopulse:incident:{' + geohash(props['center_latitude'], props['center_longitude']) + '}:' + incident_id
        raw = cache.get(key)
        value = json.loads(raw) if raw else None
        result.update(incident_id=incident_id, database_version=props['version'], redis_key=key,
                      redis_ttl_seconds=cache.ttl(key), cache_present=value is not None)
        if value:
            result.update(cache_version=value['version'], cache_expired=value['expired'],
                          cache_matches_database=value['feature'] == feature and value['version'] == props['version'])
            result['cache_summary'] = {name: value['feature']['properties'].get(name)
                                       for name in ('id', 'tipo', 'gravidade', 'version', 'report_count', 'is_demo')}
finally:
    cache.close()
    store.engine.dispose()
print(json.dumps(result))
'''


class OperationError(RuntimeError):
    pass


def docker_path():
    found = shutil.which('docker')
    if found:
        return found
    for candidate in (Path.home() / 'AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe',
                      Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Docker/Docker/resources/bin/docker.exe'):
        if candidate.is_file():
            return str(candidate)
    raise OperationError('Docker nao encontrado')


def compose(*arguments, source=None, timeout=45):
    command = [docker_path(), 'compose', '-p', PROJECT, '--env-file', str(ROOT / '.env')]
    for name in ('compose.yaml', 'compose.cluster.yaml', 'compose.presentation.yaml'):
        command += ['-f', str(ROOT / 'infra' / name)]
    env = os.environ.copy(); env['ECOPULSE_IMAGE_TAG'] = 'apresentacao'
    try:
        result = subprocess.run(command + list(arguments), input=source, capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=timeout,
                                cwd=ROOT, env=env)
    except (OSError, subprocess.TimeoutExpired):
        raise OperationError('Docker sem resposta no prazo') from None
    if result.returncode:
        raise OperationError('Operacao Docker nao concluida; consultar diagnostico local')
    return result.stdout


def state():
    with LOCK:
        return json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}


def save_state(value):
    with LOCK:
        STATE.parent.mkdir(exist_ok=True)
        temporary = STATE.with_suffix('.tmp')
        temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
        temporary.replace(STATE)


def session(client, installation_id=None):
    response = client.post('/v1/sessoes', json={'installation_id': installation_id or str(uuid4())})
    response.raise_for_status()
    return response.json()['access_token']


def health():
    with httpx.Client(timeout=6) as client:
        response = client.get(BASE + '/health')
    result = response.json()
    return {key: result.get(key) for key in ('status', 'mode', 'services', 'outbox_pending')}


def queues():
    environment = project_environment()
    password = environment.get('RABBIT_PASSWORD')
    if not password:
        raise OperationError('Senha RabbitMQ local nao configurada')
    with httpx.Client(auth=('ecopulse', password), timeout=8) as client:
        response = client.get(RABBIT + '/api/queues/%2F', params={'columns':
            'name,type,messages_ready,messages_unacknowledged,consumers,state'})
        response.raise_for_status()
    result = []
    for row in response.json():
        if row['name'].startswith('ecopulse.'):
            result.append({key: row.get(key, 0) for key in
                ('name', 'type', 'messages_ready', 'messages_unacknowledged', 'consumers', 'state')})
    return sorted(result, key=lambda row: row['name'])


def database_cache():
    selected = state().get('report_id')
    if selected:
        selected = str(UUID(selected))
    program = 'import json\nreport_id = ' + repr(selected) + '\n' + INSPECT
    return json.loads(compose('exec', '-T', 'api', 'python', '-', source=program, timeout=18))


def snapshot():
    result = {'project': PROJECT, 'checked_at': datetime.now(timezone.utc).isoformat(), 'errors': []}
    with ThreadPoolExecutor(max_workers=3) as executor:
        tasks = {name: executor.submit(function) for name, function in
                 (('health', health), ('queues', queues), ('data', database_cache))}
        for name, task in tasks.items():
            try:
                result[name] = task.result()
            except Exception as failure:
                result[name] = [] if name == 'queues' else {}
                result['errors'].append({'component': name, 'type': type(failure).__name__})
    result['risk_ready'] = sum(row.get('messages_ready', 0) for row in result['queues']
                               if row['name'].startswith('ecopulse.risk.') and row['name'].count('.') == 2)
    result['risk_consumers'] = sum(row.get('consumers', 0) for row in result['queues']
                                   if row['name'].startswith('ecopulse.risk.') and row['name'].count('.') == 2)
    result['paused'] = state().get('paused', False)
    return result


def pause():
    compose('stop', '--timeout', '10', 'worker', 'worker2', timeout=45)
    value = state(); value['paused'] = True; save_state(value)
    return {'risk_consumers': 'paused', 'relay': 'continues_publishing', 'project': PROJECT}


def resume():
    compose('start', 'worker', 'worker2', timeout=45)
    value = state(); value['paused'] = False; save_state(value)
    return {'risk_consumers': 'resumed', 'project': PROJECT}


def create():
    installation_id = str(uuid4())
    payload = {'id': str(uuid4()), 'tipo': 'obstrucao', 'gravidade': 'media',
               'latitude': -21.1775, 'longitude': -47.8101,
               'descricao': 'APS apresentacao - exemplo ficticio',
               'occurred_at': datetime.now(timezone.utc).isoformat(),
               'position_source': 'demo', 'is_demo': True}
    with httpx.Client(base_url=BASE, timeout=12) as client:
        token = session(client, installation_id)
        response = client.post('/v1/relatos', headers={'Authorization': 'Bearer ' + token}, json=payload)
        response.raise_for_status()
    value = state(); value.update(report_id=payload['id'], payload=payload, installation_id=installation_id)
    save_state(value)
    return {'http_status': response.status_code, 'report_id': payload['id'], 'is_demo': True}


def replay():
    value = state()
    if not value.get('payload') or not value.get('installation_id'):
        raise OperationError('Reenvio disponivel somente para o exemplo criado por este painel')
    with httpx.Client(base_url=BASE, timeout=12) as client:
        token = session(client, value['installation_id'])
        response = client.post('/v1/relatos', headers={'Authorization': 'Bearer ' + token}, json=value['payload'])
        response.raise_for_status()
    return {'http_status': response.status_code, 'same_report_id': value['report_id']}


def select_phone_report():
    with httpx.Client(timeout=8) as client:
        response = client.get(BASE + '/v1/relatos', params={'limit': 500})
        response.raise_for_status()
    rows = [row for row in response.json() if row.get('is_demo') is True and
            row.get('descricao', '').casefold().startswith('aps apresentacao')]
    if not rows:
        raise OperationError('Nenhum exemplo APS apresentacao recebido neste servidor')
    selected = max(rows, key=lambda row: row['received_at'])
    value = state(); value.update(report_id=selected['id'])
    value.pop('payload', None); value.pop('installation_id', None); save_state(value)
    return {'report_id': selected['id'], 'is_demo': True, 'selected_from_api': True}


def route():
    with httpx.Client(base_url=BASE, timeout=35) as client:
        token = session(client)
        response = client.post('/v1/rotas', headers={'Authorization': 'Bearer ' + token}, json={
            'origem': {'latitude': -21.1875, 'longitude': -47.8101},
            'destino': {'latitude': -21.1675, 'longitude': -47.8101}, 'perfil': 'driving-car'})
    result = {'http_status': response.status_code}
    if response.is_success:
        value = response.json()
        result.update({key: value.get(key) for key in ('distance_m', 'duration_s', 'avoided_incidents', 'source')})
        result['route_points'] = len(value.get('geometry', {}).get('coordinates', []))
    else:
        result['notice'] = 'Consulta nao concluida; conferir disponibilidade e pontos.'
    return result


def wait_snapshot(predicate, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = snapshot()
        if predicate(result):
            return result
        time.sleep(1)
    raise OperationError('O estado esperado nao foi observado no prazo')


async def validate():
    proof = {'started_at': datetime.now(timezone.utc).isoformat(), 'project': PROJECT}
    initial = await asyncio.to_thread(snapshot)
    assert initial['health'].get('mode') == 'full' and initial['health'].get('status') == 'ok'
    with httpx.Client(base_url=BASE, timeout=10) as client:
        token = session(client)
    address = httpx.URL(BASE + '/v1/ws').copy_with(scheme='ws', params={'token': token})
    try:
        async with websockets.connect(str(address), open_timeout=10) as socket:
            await socket.send(json.dumps({'type': 'subscribe', 'latitude': -21.1775,
                                          'longitude': -47.8101, 'radius_m': 10000}))
            assert json.loads(await socket.recv())['type'] == 'subscribed'
            await asyncio.to_thread(pause)
            await asyncio.to_thread(wait_snapshot, lambda row: row['risk_consumers'] == 0)
            proof['creation'] = await asyncio.to_thread(create)
            proof['replay'] = await asyncio.to_thread(replay)
            assert proof['creation']['http_status'] == 201 and proof['replay']['http_status'] == 200
            queued = await asyncio.to_thread(wait_snapshot, lambda row:
                row['risk_ready'] >= 1 and row['data'].get('report_saved') and
                not row['data'].get('incident_id') and row['data'].get('outbox_published', 0) >= 1)
            proof['queued_with_consumers_stopped'] = queued
            await asyncio.to_thread(resume)
            final = await asyncio.to_thread(wait_snapshot, lambda row:
                row['data'].get('cache_matches_database') and row['data'].get('alerts_processed') and
                row['data'].get('redis_ttl_seconds', 0) > 0 and row['risk_ready'] == 0)
            events = []
            while True:
                event = json.loads(await asyncio.wait_for(socket.recv(), timeout=12))
                events.append({key: event[key] for key in ('type', 'id', 'version') if key in event})
                if event.get('id') == final['data']['incident_id']:
                    break
            proof.update(status='PASSED', processed=final, websocket_events=events,
                         credentials_in_output=False, phone_operated=False)
    finally:
        if state().get('paused'):
            await asyncio.to_thread(resume)
    EVIDENCE.parent.mkdir(exist_ok=True)
    EVIDENCE.write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'status': proof['status'], 'creation_http': 201, 'replay_http': 200,
            'queued_ready': proof['queued_with_consumers_stopped']['risk_ready'],
            'redis_ttl_seconds': proof['processed']['data']['redis_ttl_seconds'],
            'cache_matches_database': True, 'websocket_received': True,
            'evidence': str(EVIDENCE.relative_to(ROOT))}


HTML = r'''<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>EcoPulse | RabbitMQ e Redis</title>
<style>body{margin:0;background:#f5f7f8;color:#17302e;font:17px system-ui}main{max-width:1280px;margin:30px auto;padding:0 24px}h1{font-size:30px;margin-bottom:5px}.muted{color:#536862}nav{display:flex;gap:12px;margin:20px 0}a{color:#006e64}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.card,section{background:white;border:1px solid #d6e2de;border-radius:12px;padding:20px;margin-bottom:18px}.value{font-size:38px;font-weight:700}.controls{display:flex;gap:10px;flex-wrap:wrap}button{font:inherit;cursor:pointer;padding:11px 16px;border-radius:8px;border:1px solid #abc1b9;background:#eef5f1;color:#123d33}button.primary{background:#006b60;color:white}button:disabled{opacity:.5}table{width:100%;border-collapse:collapse;font-size:16px}td,th{text-align:left;padding:8px;border-bottom:1px solid #e4ebe8}code{font:14px Consolas,monospace;overflow-wrap:anywhere}#message{min-height:28px;font-weight:600}dl{display:grid;grid-template-columns:190px 1fr;gap:10px}dd{margin:0;overflow-wrap:anywhere}.ok{color:#087140}.warn{color:#9a5b00}.grid{display:grid;grid-template-columns:1.2fr 1fr;gap:18px}@media(max-width:850px){.grid,.cards{grid-template-columns:1fr}}</style>
<main><h1>EcoPulse · RabbitMQ e Redis em funcionamento</h1>
<div class="muted">API → PostgreSQL/outbox → relay → RabbitMQ → consumidores → Redis/WebSocket</div>
<nav><a href="http://127.0.0.1:8011/docs" target="_blank">FastAPI</a><a href="http://127.0.0.1:15674" target="_blank">RabbitMQ original</a><a href="http://127.0.0.1:8011/health" target="_blank">Saúde da API</a></nav>
<div class="cards"><div class="card">RabbitMQ · mensagens prontas<div class="value" id="ready">—</div><small>Filas de risco; mensagens reais do broker</small></div><div class="card">Redis · TTL da chave<div class="value" id="ttl">—</div><small>Segundos restantes; consulta real ao Redis</small></div><div class="card">Estado dos serviços<div class="value" id="health" style="font-size:26px">Consultando…</div><small id="mode"></small></div></div>
<section><div class="controls"><button data-action="pausar">1. Pausar consumidores</button><button data-action="criar">2. Criar exemplo fictício</button><button data-action="selecionar">Selecionar relato do celular</button><button class="primary" data-action="retomar">3. Retomar consumidores</button><button data-action="reenviar">Reenviar mesmo exemplo</button><button id="refresh">Atualizar</button></div><p id="message">O app do celular é operado pela equipe. Use a porta 8011.</p><div class="muted">Pausar mantém o relay publicando. Crie apenas um exemplo e observe a fila antes de retomar.</div></section>
<div class="grid"><section><h2>RabbitMQ · filas</h2><table><thead><tr><th>Fila</th><th>Prontas</th><th>Em processamento</th><th>Consumidores</th></tr></thead><tbody id="queues"></tbody></table></section>
<section><h2>Redis · registro selecionado</h2><dl id="cache"></dl><h3>Mensagem recebida na API</h3><div id="report"></div></section></div>
<div class="muted" id="checked"></div></main>
<script>const csrf=__CSRF__;const $=id=>document.getElementById(id);let busy=false;let loading=false;let timer;
function entry(dl,k,v){const dt=document.createElement('dt');dt.textContent=k;const dd=document.createElement('dd');dd.textContent=String(v??'—');dl.append(dt,dd)}
async function refresh(){if(loading)return;loading=true;try{const r=await fetch('/api/status');const s=await r.json();$('ready').textContent=s.risk_ready??'—';$('ttl').textContent=s.data?.redis_ttl_seconds??'sem chave';$('health').textContent=s.health?.status??'indisponível';$('mode').textContent='Modo: '+(s.health?.mode??'—')+' · '+s.project;const tbody=$('queues');tbody.replaceChildren();for(const q of s.queues??[]){if(q.name.endsWith('.retry')||q.name.endsWith('.dlq')){if(!q.messages_ready)continue}const tr=document.createElement('tr');for(const v of [q.name,q.messages_ready,q.messages_unacknowledged,q.consumers]){const td=document.createElement('td');td.textContent=v??0;tr.append(td)}tbody.append(tr)}const d=s.data??{};const dl=$('cache');dl.replaceChildren();entry(dl,'Incidente',d.incident_id);entry(dl,'Chave',d.redis_key);entry(dl,'Versão no banco',d.database_version);entry(dl,'Versão no Redis',d.cache_version);entry(dl,'Cache igual ao banco',d.cache_matches_database?'SIM':'ainda não');entry(dl,'Nós Redis',d.redis_nodes);entry(dl,'Processado em risco',d.risk_processed?'SIM':'ainda não');entry(dl,'Processado em alertas',d.alerts_processed?'SIM':'ainda não');$('report').textContent=(d.report_saved?'Salvo no PostgreSQL: ':'Selecione/crie um exemplo: ')+(d.report_id??'nenhum')+' · outbox publicada: '+(d.outbox_published??0);$('checked').textContent='Atualizado: '+new Date(s.checked_at).toLocaleTimeString()+(s.errors?.length?' · Consulta parcial; conferir diagnóstico.':'');}catch(e){$('message').textContent='Painel sem resposta; conferir o terminal.'}finally{loading=false}}
document.querySelectorAll('[data-action]').forEach(b=>b.onclick=async()=>{if(busy)return;busy=true;document.querySelectorAll('button').forEach(x=>x.disabled=true);$('message').textContent='Executando '+b.textContent+'…';try{const r=await fetch('/api/action',{method:'POST',headers:{'Content-Type':'application/json','X-Apresentacao-Token':csrf},body:JSON.stringify({action:b.dataset.action})});const d=await r.json();$('message').textContent=d.ok?'Concluído: '+JSON.stringify(d.result):d.error;}catch(e){$('message').textContent='Operação sem confirmação; confira o diagnóstico antes de repetir.'}finally{busy=false;document.querySelectorAll('button').forEach(x=>x.disabled=false);await refresh()}});$('refresh').onclick=refresh;refresh();timer=setInterval(refresh,5000);</script></html>'''


def serve(port):
    csrf = secrets.token_urlsafe(24)
    cached = {'at': 0, 'value': None}
    cache_lock = threading.Lock()
    actions = {'pausar': pause, 'criar': create, 'retomar': resume,
               'selecionar': select_phone_report, 'reenviar': replay}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, value, status=200, html=False):
            body = value.encode('utf-8') if html else json.dumps(value, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8' if html else 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)

        def valid_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{port}', f'localhost:{port}'}

        def do_GET(self):
            if not self.valid_host():
                return self.send({'error': 'Host invalido'}, 403)
            if self.path == '/':
                return self.send(HTML.replace('__CSRF__', json.dumps(csrf)), html=True)
            if self.path == '/api/status':
                with cache_lock:
                    if time.monotonic() - cached['at'] > 2 or cached['value'] is None:
                        cached.update(at=time.monotonic(), value=snapshot())
                    return self.send(cached['value'])
            self.send({'error': 'Pagina nao encontrada'}, 404)

        def do_POST(self):
            if not self.valid_host() or self.headers.get('X-Apresentacao-Token') != csrf:
                return self.send({'error': 'Operacao recusada'}, 403)
            if self.path != '/api/action':
                return self.send({'error': 'Operacao desconhecida'}, 404)
            if not ACTION_LOCK.acquire(blocking=False):
                return self.send({'error': 'Aguarde a operacao atual'}, 409)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length < 1000:
                    raise OperationError('Pedido invalido')
                action = json.loads(self.rfile.read(length)).get('action')
                if action not in actions:
                    raise OperationError('Operacao desconhecida')
                result = actions[action]()
                cached['at'] = 0
                self.send({'ok': True, 'result': result})
            except Exception as failure:
                message = str(failure) if isinstance(failure, OperationError) else type(failure).__name__
                self.send({'ok': False, 'error': message}, 400)
            finally:
                ACTION_LOCK.release()

    print(f'Painel local: http://127.0.0.1:{port} | projeto {PROJECT}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('status', 'filas', 'redis', 'pausar', 'criar', 'retomar',
                                         'selecionar', 'reenviar', 'rota', 'validar', 'painel'))
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    try:
        if args.command == 'painel':
            serve(args.port); return 0
        actions = {'status': snapshot, 'filas': queues, 'redis': database_cache,
                   'pausar': pause, 'criar': create, 'retomar': resume,
                   'selecionar': select_phone_report, 'reenviar': replay, 'rota': route}
        result = asyncio.run(validate()) if args.command == 'validar' else actions[args.command]()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except KeyboardInterrupt:
        print('\nPainel encerrado; os servicos Docker permanecem ativos.'); return 0
    except Exception as failure:
        # HTTP/Docker exceptions can contain URLs and credentials. Print types only.
        print('Operacao nao concluida: ' + type(failure).__name__)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
