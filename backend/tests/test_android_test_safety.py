import json

from scripts import validate_android_push as checks


class FakeCluster:
    def __init__(self, args):
        pass

    def verify(self):
        pass


def test_default_plan_never_contacts_runtime_or_creates_state(monkeypatch, tmp_path):
    path = tmp_path / 'state.json'
    monkeypatch.setattr(checks, 'STATE_PATH', path)
    monkeypatch.setattr(checks, 'Cluster', lambda *_: (_ for _ in ()).throw(AssertionError('runtime contacted')))
    assert checks.main([]) == 0
    assert not path.exists()


def test_send_requires_explicit_execution_flag(monkeypatch, tmp_path):
    path = tmp_path / 'state.json'
    monkeypatch.setattr(checks, 'STATE_PATH', path)
    monkeypatch.setattr(checks, 'Cluster', FakeCluster)
    calls = []
    monkeypatch.setattr(checks, 'call', lambda *_: calls.append(True))
    assert checks.main(['--mode', 'foreground-send']) == 2
    assert not calls and not path.exists()


def test_uncertain_provider_result_is_never_blindly_sent_again(monkeypatch, tmp_path):
    path = tmp_path / 'state.json'
    monkeypatch.setattr(checks, 'STATE_PATH', path)
    monkeypatch.setattr(checks, 'Cluster', FakeCluster)
    calls = []
    def uncertain(cluster, value, code):
        if code != checks.FOREGROUND:
            return {'one_android_registered': True, 'fcm_configured': True}
        calls.append(True)
        raise TimeoutError('provider result unknown')
    monkeypatch.setattr(checks, 'call', uncertain)
    arguments = ['--mode', 'foreground-send', '--allow-send']
    assert checks.main(arguments) == 2
    assert json.loads(path.read_text())['foreground_attempted']
    assert checks.main(arguments) == 2
    assert calls == [True]
