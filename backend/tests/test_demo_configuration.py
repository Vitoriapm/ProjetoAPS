import os
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest

from scripts import check_integration_config, run_demo


@pytest.fixture
def isolated_project(tmp_path, monkeypatch):
    # Only the test directory receives an .env; the real project is untouched.
    monkeypatch.setattr(check_integration_config, "ROOT", tmp_path)
    monkeypatch.setattr(run_demo, "ROOT", tmp_path)
    for key in run_demo.PROVIDER_KEYS:
        monkeypatch.delenv(key, raising=False)
    return tmp_path


def test_dotenv_provider_configuration_reaches_demo_without_modifying_files(isolated_project):
    root = isolated_project
    path = root / ".env"
    content = ('# local test values\nORS_API_KEY="test-ors-key"\n'
        'FCM_CREDENTIALS_FILE=/run/secrets/fcm.json\nENVIRONMENT_SOURCE=fixtures\n'
        'HEAT_DATASET_FILE=backend/datasets/custom.geojson\n'
        'DATABASE_URL=postgresql+psycopg://test-full-db/test\nJWT_SECRET=full-test-secret\n')
    path.write_text(content, encoding="utf-8")
    before = path.read_bytes()
    settings = run_demo.demo_settings()
    assert settings.ors_key == "test-ors-key"
    assert settings.fcm_credentials == str((root / "secrets/fcm.json").resolve())
    assert settings.environment_source == "fixtures"
    assert settings.heat_file == str((root / "backend/datasets/custom.geojson").resolve())
    with TestClient(run_demo.create_demo_app()) as client:
        health = client.get("/health").json()
        assert health["status"] == "ok" and health["mode"] == "demo"
        assert health["configuration"]["routes_configured"] is True
        assert health["configuration"]["fcm_configured"] is True
    assert path.read_bytes() == before
    assert not (root / "secrets/fcm.json").exists()  # No credential copy was attempted.


@pytest.mark.parametrize("override", ["process-key", ""])
def test_explicit_process_provider_value_has_precedence_including_disable(isolated_project, monkeypatch, override):
    (isolated_project / ".env").write_text("ORS_API_KEY=dotenv-key\nENVIRONMENT_SOURCE=fixtures\n", encoding="utf-8")
    monkeypatch.setenv("ORS_API_KEY", override)
    settings = run_demo.demo_settings()
    assert settings.ors_key == override
    assert settings.environment_source == "fixtures"


def test_full_environment_cannot_redirect_demo_database_or_infrastructure(isolated_project, monkeypatch):
    inherited = {"ECOPULSE_MODE": "full", "DATABASE_URL": "postgresql+psycopg://full-only-db/test",
        "DATA_DIR": str(isolated_project / "outside-demo"), "JWT_SECRET": "full-secret-that-demo-must-ignore",
        "AMQP_URLS": "amqp://full-only-broker/", "REDIS_CLUSTER_URLS": "redis://full-only-cache/",
        "SHARD_COUNT": "invalid-full-value", "RABBIT_QUORUM_SIZE": "invalid-full-value"}
    for key, value in inherited.items():
        monkeypatch.setenv(key, value)
    settings = run_demo.demo_settings()
    target = (isolated_project / "backend/data/ecopulse-demo.db").resolve()
    assert settings.mode == "demo"
    assert settings.database_url == "sqlite:///" + target.as_posix()
    assert settings.data_dir == str(target.parent)
    assert settings.jwt_secret != inherited["JWT_SECRET"]
    assert settings.amqp_urls == [] and settings.redis_urls == []
    assert settings.shard_count == 4 and settings.quorum_size == 1
    with TestClient(run_demo.create_demo_app()) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/v1/relatos").json() == []
    assert target.is_file()
    assert not (isolated_project / "outside-demo").exists()
    # Child app configuration does not rewrite the caller's environment.
    assert all(os.environ[key] == value for key, value in inherited.items())


@pytest.mark.parametrize("form", ["mounted", "relative", "absolute"])
def test_fcm_path_resolves_to_host_file_without_copying_or_reading_credentials(isolated_project, monkeypatch, form):
    target = isolated_project / "secrets/fcm.json"
    target.parent.mkdir()
    target.write_bytes(b"test-only-content-not-a-credential")
    values = {"mounted": "/run/secrets/fcm.json", "relative": "secrets/fcm.json", "absolute": str(target)}
    monkeypatch.setenv("FCM_CREDENTIALS_FILE", values[form])
    assert run_demo.demo_settings().fcm_credentials == str(target.resolve())
    assert target.read_bytes() == b"test-only-content-not-a-credential"


def test_missing_dotenv_preserves_offline_demo_defaults(isolated_project):
    settings = run_demo.demo_settings()
    assert settings.ors_key == "" and settings.fcm_credentials == ""
    assert settings.environment_source == "open-meteo" and settings.heat_file == ""
    assert not (isolated_project / ".env").exists()


def test_fresh_process_api_import_ignores_invalid_full_settings_and_restores_environment(isolated_project):
    # A previously imported backend.api.main would hide this startup bug.
    code = r'''
import os, sys
from pathlib import Path
from fastapi.testclient import TestClient
from scripts import check_integration_config, run_demo
root = Path(sys.argv[1])
check_integration_config.ROOT = root
run_demo.ROOT = root
before = {key: os.environ.get(key) for key in run_demo.INFRASTRUCTURE_KEYS}
app = run_demo.create_demo_app()
assert {key: os.environ.get(key) for key in run_demo.INFRASTRUCTURE_KEYS} == before
with TestClient(app) as client:
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json()['mode'] == 'demo'
assert (root / 'backend/data/ecopulse-demo.db').is_file()
print('fresh-process-demo-ok')
'''
    environment = os.environ.copy()
    environment.update(ECOPULSE_MODE="full", DATABASE_URL="postgresql+psycopg://invalid-full-host/test",
        DATA_DIR="/unavailable/full-data", JWT_SECRET="full-secret-to-ignore",
        SHARD_COUNT="not-an-integer", RABBIT_QUORUM_SIZE="not-an-integer",
        AMQP_URLS="amqp://invalid-full-host/", REDIS_CLUSTER_URLS="redis://invalid-full-host/",
        POSTGRES_PASSWORD="test-infra-secret")
    completed = subprocess.run([sys.executable, "-c", code, str(isolated_project)],
        cwd=Path(__file__).resolve().parents[2], env=environment,
        text=True, capture_output=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "fresh-process-demo-ok"
    assert "test-infra-secret" not in completed.stdout + completed.stderr
