"""Validate downloaded Firebase files; copy only with --apply. Never writes .env."""
import argparse
import json
from pathlib import Path
import plistlib
import shutil

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "br.edu.ecopulse.ecopulse"
DESTINATIONS = {
    "android": ROOT / "mobile/android/app/google-services.json",
    "ios": ROOT / "mobile/ios/Runner/GoogleService-Info.plist",
    "server": ROOT / "secrets/fcm.json",
}


def project_for(path, kind):
    if kind == "ios":
        value = plistlib.loads(path.read_bytes())
        if value.get("BUNDLE_ID") != APP_ID:
            raise ValueError("bundle iOS diferente do EcoPulse")
        project = value.get("PROJECT_ID")
        if not value.get("GOOGLE_APP_ID") or not value.get("GCM_SENDER_ID") or not value.get("API_KEY"):
            raise ValueError("configuração iOS incompleta")
    else:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if kind == "android":
            project = value.get("project_info", {}).get("project_id")
            matches = [client for client in value.get("client", [])
                if client.get("client_info", {}).get("android_client_info", {}).get("package_name") == APP_ID]
            if not matches or not matches[0].get("client_info", {}).get("mobilesdk_app_id") or not any(
                item.get("current_key") for item in matches[0].get("api_key", [])):
                raise ValueError("pacote Android diferente do EcoPulse ou configuração incompleta")
        else:
            project = value.get("project_id")
            if value.get("type") != "service_account" or not value.get("client_email") or not value.get("private_key", "").startswith("-----BEGIN PRIVATE KEY-----"):
                raise ValueError("arquivo de conta de serviço inválido")
    if not isinstance(project, str) or not project.strip():
        raise ValueError("arquivo sem identificação do projeto Firebase")
    return project


def prepare(paths, *, apply=False, replace=False):
    projects = {kind: project_for(path, kind) for kind, path in paths.items()}
    if len(set(projects.values())) > 1:
        raise ValueError("arquivos pertencem a projetos Firebase diferentes")
    if apply:
        for kind, path in paths.items():
            destination = DESTINATIONS[kind]
            if destination.exists() and destination.read_bytes() != path.read_bytes() and not replace:
                raise ValueError("arquivo local diferente já existe; revise antes de usar --replace")
        for kind, path in paths.items():
            destination = DESTINATIONS[kind]
            destination.parent.mkdir(parents=True, exist_ok=True)
            if path.resolve() != destination.resolve():
                shutil.copyfile(path, destination)
    return {"files_valid": True, "same_firebase_project": True,
        "android_validated": "android" in paths, "ios_validated": "ios" in paths,
        "server_validated": "server" in paths, "copied": apply,
        "env_changed": False, "provider_contacted": False, "real_delivery_tested": False,
        "credential_authentication_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--android-file", type=Path)
    parser.add_argument("--ios-file", type=Path)
    parser.add_argument("--service-account-file", type=Path)
    parser.add_argument("--apply", action="store_true", help="copiar arquivos validados para os destinos locais")
    parser.add_argument("--replace", action="store_true", help="permitir substituir configuração local diferente")
    args = parser.parse_args()
    paths = {kind: path for kind, path in {"android": args.android_file, "ios": args.ios_file, "server": args.service_account_file}.items() if path}
    if not paths:
        paths = {kind: path for kind, path in DESTINATIONS.items() if path.is_file()}
    if not paths:
        print(json.dumps({"configuration_present": False, "copied": False, "real_delivery_tested": False}))
        return 2
    try:
        print(json.dumps(prepare(paths, apply=args.apply, replace=args.replace), ensure_ascii=False, indent=2))
        return 0
    except Exception:
        # Exceptions may contain paths or fragments of malformed credentials.
        print(json.dumps({"files_valid": False, "copied": False, "message": "Revise o formato, o pacote/bundle e o projeto dos arquivos locais."}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
