"""Inspect Firebase/native configuration offline; print no keys, tokens or project IDs."""
import json
from pathlib import Path
import plistlib
import xml.etree.ElementTree as ET

from check_integration_config import credentials_on_host, project_environment
from prepare_firebase import DESTINATIONS, project_for

ROOT = Path(__file__).resolve().parents[1]
ANDROID_NS = "{http://schemas.android.com/apk/res/android}"


def inspect_setup():
    result = {"provider_contacted": False, "real_delivery_tested": False,
        "credential_authentication_verified": False, "configuration_checks_are_structural": True}
    projects = []
    for kind, path in DESTINATIONS.items():
        result[kind + "_file_present"] = path.is_file()
        valid = False
        if path.is_file():
            try:
                projects.append(project_for(path, kind))
                valid = True
            except Exception:
                pass
        result[kind + "_file_valid"] = valid
    result["same_firebase_project"] = bool(projects) and len(set(projects)) == 1
    values = project_environment()
    configured_path = values.get("FCM_CREDENTIALS_FILE", "")
    result["server_env_path_configured"] = bool(configured_path)
    result["server_env_file_present"] = credentials_on_host(configured_path)
    manifest = ET.parse(ROOT / "mobile/android/app/src/main/AndroidManifest.xml").getroot()
    result["android_notification_permission"] = any(
        item.get(ANDROID_NS + "name") == "android.permission.POST_NOTIFICATIONS"
        for item in manifest.findall("uses-permission"))
    native = (ROOT / "mobile/android/app/src/main/kotlin/br/edu/ecopulse/ecopulse/MainActivity.kt").read_text(encoding="utf-8")
    result["android_notification_channel_declared"] = "ecopulse_alertas" in native and "IMPORTANCE_HIGH" in native
    plist = plistlib.loads((ROOT / "mobile/ios/Runner/Info.plist").read_bytes())
    result["ios_swizzling_allowed"] = plist.get("FirebaseAppDelegateProxyEnabled", True) is not False
    result["ios_background_modes_declared"] = {"fetch", "remote-notification"}.issubset(plist.get("UIBackgroundModes", []))
    result["ios_apns_entitlement_present"] = False
    for path in (ROOT / "mobile/ios").rglob("*.entitlements"):
        try:
            if plistlib.loads(path.read_bytes()).get("aps-environment") in {"development", "production"}:
                result["ios_apns_entitlement_present"] = True
        except Exception:
            pass
    result["android_ready_for_real_test"] = result["android_file_valid"] and result["server_file_valid"] and result["same_firebase_project"] and result["server_env_file_present"]
    result["ios_ready_for_real_test"] = result["ios_file_valid"] and result["server_file_valid"] and result["same_firebase_project"] and result["server_env_file_present"] and result["ios_apns_entitlement_present"]
    # External APNs upload, signing, physical hardware, enabled Dart define and
    # network reachability cannot be proven by these offline file checks.
    result["external_apns_signing_and_device_verified"] = False
    return result


if __name__ == "__main__":
    print(json.dumps(inspect_setup(), ensure_ascii=False, indent=2, sort_keys=True))
