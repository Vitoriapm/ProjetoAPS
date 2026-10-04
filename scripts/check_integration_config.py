"""Read integration configuration and print boolean presence checks only.

No credential content is printed, authenticated provider called, or file changed.
Project .env values are considered with process environment taking precedence.
"""
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def project_environment():
    values = {}
    env_file = ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    values.update(os.environ)
    return values


def configured(value):
    value = value.strip()
    placeholders = ("troque", "changeme", "dummy", "sua_chave", "your_", "example")
    return bool(value) and not value.lower().startswith(placeholders)


def credentials_on_host(value):
    if not configured(value):
        return False
    # Compose exposes project secrets read-only at /run/secrets.
    if value.startswith("/run/secrets/"):
        path = ROOT / "secrets" / value.removeprefix("/run/secrets/")
    else:
        path = Path(value)
        if not path.is_absolute():
            path = ROOT / path
    return path.is_file()


def main():
    values = project_environment()
    fcm_file = values.get("FCM_CREDENTIALS_FILE", "")
    result = {
        "project_env_file_exists": (ROOT / ".env").is_file(),
        "ors_api_key_configured": configured(values.get("ORS_API_KEY", "")),
        "fcm_credentials_path_configured": configured(fcm_file),
        "fcm_credentials_file_exists_on_host": credentials_on_host(fcm_file),
        "android_google_services_file_exists": (ROOT / "mobile/android/app/google-services.json").is_file(),
        "ios_google_service_plist_exists": (ROOT / "mobile/ios/Runner/GoogleService-Info.plist").is_file(),
        "environment_source_is_open_meteo": values.get("ENVIRONMENT_SOURCE", "open-meteo") == "open-meteo",
        "environment_source_is_fixtures": values.get("ENVIRONMENT_SOURCE", "open-meteo") == "fixtures",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
