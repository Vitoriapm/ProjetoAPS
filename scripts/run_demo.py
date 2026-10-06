"""Start the local demo with only provider settings from the project .env.

Explicit process values take precedence. Full-mode database URLs, data paths,
JWTs and infrastructure settings never become the demo's application settings.
No credential values are printed or modified.
"""
import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_integration_config import project_environment  # noqa: E402
from backend.shared.config import Settings  # noqa: E402

PROVIDER_KEYS = ("ORS_API_KEY", "FCM_CREDENTIALS_FILE", "ENVIRONMENT_SOURCE", "HEAT_DATASET_FILE")
INFRASTRUCTURE_KEYS = ("ECOPULSE_MODE", "DATABASE_URL", "DATA_DIR", "JWT_SECRET", "AMQP_URLS",
    "REDIS_CLUSTER_URLS", "SHARD_COUNT", "RABBIT_QUORUM_SIZE", "POSTGRES_PASSWORD",
    "REPLICATION_PASSWORD", "RABBIT_PASSWORD", "RABBIT_ERLANG_COOKIE", "REDIS_PASSWORD")


def local_provider_file(value):
    """Translate a mounted-secret path for host execution, retaining originals."""
    if not value:
        return ""
    if value.startswith("/run/secrets/"):
        path = ROOT / "secrets" / value.removeprefix("/run/secrets/")
    else:
        path = Path(value)
        if not path.is_absolute():
            path = ROOT / path
    return str(path.resolve())


def demo_settings():
    providers = {key: value for key, value in project_environment().items() if key in PROVIDER_KEYS}
    data_dir = (ROOT / "backend/data").resolve()
    # Pass every environment-derived infrastructure field explicitly. Even a
    # shell previously used for Docker/full mode stays on the local SQLite DB.
    return Settings(mode="demo", database_url="sqlite:///" + (data_dir / "ecopulse-demo.db").as_posix(),
        data_dir=str(data_dir), jwt_secret="", amqp_urls=[], redis_urls=[], shard_count=4,
        quorum_size=1, ors_key=providers.get("ORS_API_KEY", ""),
        fcm_credentials=local_provider_file(providers.get("FCM_CREDENTIALS_FILE", "")),
        environment_source=providers.get("ENVIRONMENT_SOURCE", "open-meteo"),
        heat_file=local_provider_file(providers.get("HEAT_DATASET_FILE", ""))).validate()


@contextmanager
def demo_import_environment():
    """Keep the API module's unused global app from reading full-mode values."""
    previous = {key: os.environ.get(key) for key in INFRASTRUCTURE_KEYS}
    try:
        for key in INFRASTRUCTURE_KEYS:
            os.environ.pop(key, None)
        os.environ["ECOPULSE_MODE"] = "demo"
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def create_demo_app():
    settings = demo_settings()
    # Import after Uvicorn configures logging, so the existing WS token filter
    # is installed on its final logger, just like the module CLI entry point.
    # main.py also builds a module-level app. Temporarily shield that import
    # from a shell with invalid full-mode numbers or infrastructure credentials.
    with demo_import_environment():
        from backend.api.main import create_app
    return create_app(settings)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    arguments = parser.parse_args(argv)
    if not 1 <= arguments.port <= 65535:
        parser.error("port must be between 1 and 65535")
    import uvicorn
    uvicorn.run(create_demo_app, factory=True, host="0.0.0.0", port=arguments.port, access_log=False)


if __name__ == "__main__":
    main()
