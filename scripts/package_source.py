"""Empacota os fontes da APS sem bancos, caches ou credenciais locais."""
from pathlib import Path
import os
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "entregas" / "EcoPulse-fonte.zip"
FOLDERS = ("backend", "mobile", "infra", "scripts", "contracts", "docs")
PRUNE = {
    ".venv", "build", ".dart_tool", ".gradle", ".idea", "__pycache__",
    ".pytest_cache", "node_modules", "Pods", ".symlinks", "ephemeral", "data",
    "secrets", ".kotlin", ".cxx",
}
SKIP = {
    ".env", "google-services.json", "GoogleService-Info.plist",
    "local.properties", ".flutter-plugins-dependencies", "Generated.xcconfig",
    "flutter_export_environment.sh", ".DS_Store",
}


def source_files():
    for name in (
        "README.md", "PLANO_EXECUCAO_ECOPULSE.md", ".env.example",
        ".gitignore", ".dockerignore", "secrets/.gitkeep",
    ):
        candidate = ROOT / name
        if candidate.is_file():
            yield candidate
    for folder in FOLDERS:
        for current, directories, files in os.walk(ROOT / folder):
            directories[:] = [d for d in directories if d not in PRUNE]
            for name in files:
                if name in SKIP or name.startswith(".env") or name.endswith((".db", ".db-wal", ".db-shm", ".pyc", ".log", ".iml")):
                    continue
                yield Path(current) / name


def main():
    OUTPUT.parent.mkdir(exist_ok=True)
    paths = sorted(source_files())
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, arcname="EcoPulse/" + path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(OUTPUT) as archive:
        assert archive.testzip() is None, "Arquivo ZIP corrompido."
        assert not any(Path(name).name in SKIP for name in archive.namelist())
    print(f"Fonte empacotado: {OUTPUT.name}; {len(paths)} arquivos; {OUTPUT.stat().st_size} bytes.")


if __name__ == "__main__":
    main()
