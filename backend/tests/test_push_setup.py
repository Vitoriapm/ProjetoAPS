import json
import plistlib

import pytest
from scripts import prepare_firebase


def files(tmp_path, project="academic-test"):
    android = tmp_path / "download-android.json"
    ios = tmp_path / "download-ios.plist"
    server = tmp_path / "download-server.json"
    android.write_text(json.dumps({"project_info": {"project_id": project}, "client": [{"client_info": {
        "mobilesdk_app_id": "test-mobile-id", "android_client_info": {"package_name": prepare_firebase.APP_ID}}, "api_key": [{"current_key": "fixture-api-key"}]}]}))
    ios.write_bytes(plistlib.dumps({"PROJECT_ID": project, "BUNDLE_ID": prepare_firebase.APP_ID, "GOOGLE_APP_ID": "test-ios-id", "GCM_SENDER_ID": "test-sender", "API_KEY": "fixture-api-key"}))
    server.write_text(json.dumps({"project_id": project, "type": "service_account", "client_email": "test@example.invalid",
        "private_key": "-----BEGIN PRIVATE KEY-----\nfixture-only-not-a-real-key\n-----END PRIVATE KEY-----"}))
    return {"android": android, "ios": ios, "server": server}


def test_prepare_validates_without_copy_or_env_changes(tmp_path, monkeypatch):
    paths = files(tmp_path)
    targets = {kind: tmp_path / "dest" / kind for kind in paths}
    monkeypatch.setattr(prepare_firebase, "DESTINATIONS", targets)
    result = prepare_firebase.prepare(paths)
    assert result["files_valid"] and not result["copied"] and not result["env_changed"]
    assert not any(path.exists() for path in targets.values())


def test_mismatched_firebase_projects_never_copy_partial_configuration(tmp_path, monkeypatch):
    paths = files(tmp_path)
    value = json.loads(paths["server"].read_text())
    value["project_id"] = "another-project"
    paths["server"].write_text(json.dumps(value))
    targets = {kind: tmp_path / "dest" / kind for kind in paths}
    monkeypatch.setattr(prepare_firebase, "DESTINATIONS", targets)
    with pytest.raises(ValueError, match="diferentes"):
        prepare_firebase.prepare(paths, apply=True)
    assert not any(path.exists() for path in targets.values())


def test_copy_requires_explicit_apply_and_protects_existing_files(tmp_path, monkeypatch):
    paths = files(tmp_path)
    targets = {kind: tmp_path / "dest" / kind for kind in paths}
    monkeypatch.setattr(prepare_firebase, "DESTINATIONS", targets)
    targets["server"].parent.mkdir()
    targets["server"].write_text("previous-local-configuration")
    with pytest.raises(ValueError, match="já existe"):
        prepare_firebase.prepare(paths, apply=True)
    assert targets["server"].read_text() == "previous-local-configuration"
    assert not targets["android"].exists()
    result = prepare_firebase.prepare(paths, apply=True, replace=True)
    assert result["copied"]
    assert all(path.read_bytes() == paths[kind].read_bytes() for kind, path in targets.items())


def test_wrong_native_identifier_is_rejected(tmp_path):
    paths = files(tmp_path)
    ios = plistlib.loads(paths["ios"].read_bytes())
    ios["BUNDLE_ID"] = "another.app"
    paths["ios"].write_bytes(plistlib.dumps(ios))
    with pytest.raises(ValueError, match="bundle"):
        prepare_firebase.prepare(paths)
