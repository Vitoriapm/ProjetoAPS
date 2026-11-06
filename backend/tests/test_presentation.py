import json
import subprocess

import httpx
import pytest

from scripts import apresentacao_dsd as presentation


def test_docker_failure_does_not_expose_output_and_targets_only_presentation(monkeypatch):
    invoked = []
    def run(command, **kwargs):
        invoked.append((command, kwargs))
        return subprocess.CompletedProcess(command, 1, '', 'private-output-sentinel')
    monkeypatch.setattr(presentation, 'docker_path', lambda: 'docker')
    monkeypatch.setattr(presentation.subprocess, 'run', run)
    with pytest.raises(presentation.OperationError) as error:
        presentation.compose('stop', 'worker', 'worker2')
    assert 'private-output-sentinel' not in str(error.value)
    command, options = invoked[0]
    assert command[command.index('-p') + 1] == 'ecopulse-apresentacao'
    assert command[-3:] == ['stop', 'worker', 'worker2']
    assert options['capture_output'] is True
    assert not options.get('shell')


def test_phone_selection_excludes_real_reports_and_does_not_store_tokens(monkeypatch, tmp_path):
    rows = [
        {'id': 'real', 'is_demo': False, 'descricao': 'APS apresentacao', 'received_at': '2026-11-02T20:00:00Z'},
        {'id': 'other', 'is_demo': True, 'descricao': 'Other example', 'received_at': '2026-11-02T21:00:00Z'},
        {'id': 'example', 'is_demo': True, 'descricao': 'APS apresentacao - exemplo ficticio', 'received_at': '2026-11-02T19:00:00Z'},
    ]
    client = httpx.Client
    monkeypatch.setattr(presentation.httpx, 'Client', lambda **kwargs: client(
        **kwargs, transport=httpx.MockTransport(lambda request: httpx.Response(200, json=rows))))
    monkeypatch.setattr(presentation, 'STATE', tmp_path / 'state.json')
    result = presentation.select_phone_report()
    assert result['report_id'] == 'example'
    saved = json.loads(presentation.STATE.read_text())
    assert saved == {'report_id': 'example'}


def test_replay_preserves_payload_and_installation_without_persisting_jwt(monkeypatch, tmp_path):
    monkeypatch.setattr(presentation, 'STATE', tmp_path / 'state.json')
    payload = {'id': 'demo-report', 'is_demo': True, 'occurred_at': '2026-11-02T19:00:00Z'}
    presentation.save_state({'report_id': 'demo-report', 'payload': payload, 'installation_id': 'demo-installation'})
    seen = []
    def handler(request):
        seen.append((request.url.path, json.loads(request.content)))
        if request.url.path == '/v1/sessoes':
            return httpx.Response(200, json={'access_token': 'ephemeral-jwt-sentinel'})
        assert request.headers['authorization'] == 'Bearer ephemeral-jwt-sentinel'
        return httpx.Response(200, json=payload)
    client = httpx.Client
    monkeypatch.setattr(presentation.httpx, 'Client', lambda **kwargs: client(
        **kwargs, transport=httpx.MockTransport(handler)))
    result = presentation.replay()
    assert result['http_status'] == 200
    assert seen == [('/v1/sessoes', {'installation_id': 'demo-installation'}), ('/v1/relatos', payload)]
    assert 'ephemeral-jwt-sentinel' not in presentation.STATE.read_text()
