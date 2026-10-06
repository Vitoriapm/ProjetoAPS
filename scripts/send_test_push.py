"""Validate or send one explicitly fictitious FCM alert to a token kept in a local file."""
import argparse
from datetime import timedelta
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.alerts.main import FcmAdapter
from backend.shared.config import Settings
from backend.shared.db import iso, utc_now


def test_event():
    now = utc_now()
    incident = str(uuid4())
    return {"event_id": str(uuid4()), "payload": {"type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-47.8101, -21.1775]},
        "properties": {"id": incident, "version": 1, "is_demo": True,
            "expires_at": iso(now + timedelta(minutes=5))}}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", type=Path, default=ROOT / "secrets/fcm.json")
    parser.add_argument("--token-file", type=Path, required=True, help="arquivo local contendo apenas o token FCM; não use o token na linha de comando")
    parser.add_argument("--send", action="store_true", help="enviar ao aparelho; padrão valida no FCM sem entrega (dry-run)")
    parser.add_argument("--output", type=Path, help="salvar somente o resultado sanitizado")
    args = parser.parse_args()
    result = {"dry_run": not args.send, "provider_accepted": False,
        "device_receipt_verified": False, "is_demo": True}
    try:
        token = args.token_file.read_text(encoding="utf-8-sig").strip()
        if not 20 <= len(token) <= 4096 or not args.credentials.is_file():
            raise ValueError("configuration absent")
        event = test_event()
        settings = Settings(mode="demo", fcm_credentials=str(args.credentials))
        FcmAdapter(settings).send(token, event, dry_run=not args.send)
        result["provider_accepted"] = True
        result["event_id"] = event["event_id"]
        result["message"] = "Validação FCM aceita, sem entrega." if not args.send else "FCM aceitou o envio fictício; registre separadamente a chegada no aparelho."
    except Exception:
        result["message"] = "Teste pendente ou rejeitado. Confira os arquivos locais, o projeto Firebase, o token e a conexão. Nenhuma credencial foi exibida."
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result["provider_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
