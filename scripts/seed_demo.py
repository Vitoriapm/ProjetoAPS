"""Insere relatos fictícios pela API, sem escrever diretamente no banco."""
import argparse
from datetime import datetime, timezone
import json
from uuid import UUID, uuid5
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

NAMESPACE = UUID("264a2710-5f46-4b95-8682-cdfafdf4a30b")


def call(url, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(url, data=None if data is None else json.dumps(data).encode(), headers=headers)
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description="Relatos fictícios EcoPulse (is_demo=true)")
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--batch", default=None, help="ID de rodada; padrão minuto UTC atual")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    now = datetime.now(timezone.utc)
    batch = args.batch or now.strftime("%Y%m%d%H%M")
    # Deterministic timestamp per batch gives idempotent identical re-runs.
    try:
        timestamp = datetime.strptime(batch, "%Y%m%d%H%M").replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    except ValueError:
        parser.error("--batch deve seguir AAAAMMDDHHMM (UTC)")
    points = [("alagamento", -21.1775, -47.8101, "media"),
              ("alagamento", -21.1778, -47.8100, "alta"),
              ("alagamento", -21.1776, -47.8104, "media"),
              ("obstrucao", -21.1936, -47.8152, "alta")]
    try:
        for index, (tipo, lat, lon, severity) in enumerate(points):
            installation_id = str(uuid5(NAMESPACE, "installation:" + str(index)))
            session = call(base + "/v1/sessoes", {"installation_id": installation_id})
            report = {"id": str(uuid5(NAMESPACE, batch + ":" + str(index))), "tipo": tipo,
                "latitude": lat, "longitude": lon, "gravidade": severity,
                "descricao": "Dados simulados para demonstração da APS. Este relato não indica uma ocorrência real.",
                "occurred_at": timestamp, "position_source": "demo", "accuracy_m": None, "is_demo": True}
            saved = call(base + "/v1/relatos", report, session["access_token"])
            print(f"Relato fictício {index + 1}: {saved['id']} ({tipo})")
    except HTTPError as exc:
        print("API recusou a operação:", exc.code, exc.read().decode())
        raise SystemExit(1)
    except URLError:
        print("Não foi possível acessar a API. Inicie o backend e confira --url.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
