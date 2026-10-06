from dataclasses import dataclass, field
import os
from pathlib import Path


@dataclass
class Settings:
    mode: str = field(default_factory=lambda: os.getenv("ECOPULSE_MODE", "full"))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    amqp_urls: list[str] = field(default_factory=lambda: os.getenv("AMQP_URLS", "amqp://guest:guest@localhost/").split(","))
    redis_urls: list[str] = field(default_factory=lambda: os.getenv("REDIS_CLUSTER_URLS", "redis://localhost:6379").split(","))
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", ""))
    fcm_credentials: str = field(default_factory=lambda: os.getenv("FCM_CREDENTIALS_FILE", ""))
    ors_key: str = field(default_factory=lambda: os.getenv("ORS_API_KEY", ""))
    shard_count: int = field(default_factory=lambda: int(os.getenv("SHARD_COUNT", "4")))
    quorum_size: int = field(default_factory=lambda: int(os.getenv("RABBIT_QUORUM_SIZE", "1")))
    data_dir: str = field(default_factory=lambda: os.getenv("DATA_DIR", str(Path(__file__).resolve().parents[1] / "data")))
    environment_source: str = field(default_factory=lambda: os.getenv("ENVIRONMENT_SOURCE", "open-meteo"))
    heat_file: str = field(default_factory=lambda: os.getenv("HEAT_DATASET_FILE", ""))
    session_hours: int = 24 * 30
    influence_m: int = 200
    collaborative_window_s: int = 600
    expiration_s: int = 1800
    position_valid_s: int = 3600

    def validate(self):
        if self.mode not in {"demo", "full"}:
            raise ValueError("ECOPULSE_MODE deve ser demo ou full")
        if not 2 <= self.shard_count <= 32:
            raise ValueError("SHARD_COUNT deve estar entre 2 e 32")
        if self.mode == "full":
            if not self.database_url.startswith("postgresql"):
                raise ValueError("Modo full exige DATABASE_URL PostgreSQL/PostGIS; não há fallback para SQLite")
            if len(self.jwt_secret) < 32:
                raise ValueError("Modo full exige JWT_SECRET com pelo menos 32 caracteres")
        else:
            if not self.database_url:
                self.database_url = "sqlite:///" + str(Path(self.data_dir) / "ecopulse-demo.db")
            if not self.jwt_secret:
                self.jwt_secret = "apenas-demo-local-nao-usar-em-producao-ecopulse"
        return self
