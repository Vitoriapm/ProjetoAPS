from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import threading
from sqlalchemy import (Boolean, Column, Float, Integer, JSON, MetaData, String, Table, create_engine, event, select, text)

metadata = MetaData()
relatos = Table("relatos", metadata,
    Column("id", String(36), primary_key=True), Column("installation_id", String(36), nullable=False),
    Column("latitude", Float, nullable=False), Column("longitude", Float, nullable=False),
    Column("tipo", String(20), nullable=False), Column("occurred_at", String(32), nullable=False, index=True),
    Column("data", JSON, nullable=False))
incidentes = Table("incidentes", metadata,
    Column("id", String(36), primary_key=True), Column("latitude", Float, nullable=False),
    Column("longitude", Float, nullable=False), Column("tipo", String(20), nullable=False),
    Column("expires_at", String(32), nullable=False, index=True), Column("version", Integer, nullable=False),
    Column("active", Boolean, nullable=False, default=True), Column("data", JSON, nullable=False))
links = Table("relato_incidente", metadata,
    Column("relato_id", String(36), primary_key=True), Column("incidente_id", String(36), nullable=False, index=True))
outbox = Table("outbox", metadata,
    Column("id", String(36), primary_key=True), Column("route", String(100), nullable=False),
    Column("event", JSON, nullable=False), Column("published", Boolean, nullable=False, default=False, index=True),
    Column("created_at", String(32), nullable=False))
processed = Table("eventos_processados", metadata,
    Column("consumer", String(30), primary_key=True), Column("event_id", String(36), primary_key=True),
    Column("processed_at", String(32), nullable=False))
devices = Table("dispositivos", metadata,
    Column("id", String(36), primary_key=True), Column("data", JSON, nullable=False))
deliveries = Table("entregas_alerta", metadata,
    Column("id", String(100), primary_key=True), Column("status", String(30), nullable=False),
    Column("provider_id", String(300)), Column("updated_at", String(32), nullable=False))


def active_outbox_routes():
    # Retain historical rows from retired features without attempting to send
    # them to broker routes that no longer have consumers.
    return outbox.c.route.like("relato.%") | outbox.c.route.like("incidente.%")


def utc_now():
    return datetime.now(timezone.utc)


def iso(value):
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


class Store:
    def __init__(self, settings):
        self.settings = settings
        self.pg = settings.database_url.startswith("postgresql")
        if not self.pg:
            dbfile = settings.database_url.removeprefix("sqlite:///")
            if dbfile != ":memory:":
                Path(dbfile).parent.mkdir(parents=True, exist_ok=True)
        kwargs = {"pool_pre_ping": True}
        if not self.pg:
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": 20}
            if settings.database_url.endswith(":memory:"):
                from sqlalchemy.pool import StaticPool
                kwargs["poolclass"] = StaticPool
        self.engine = create_engine(settings.database_url, **kwargs)
        self.lock = threading.RLock()
        if not self.pg:
            @event.listens_for(self.engine, "connect")
            def sqlite_options(conn, _):
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA foreign_keys=ON")

    def initialize(self):
        with self.engine.begin() as conn:
            if self.pg:
                conn.execute(text("SELECT pg_advisory_xact_lock(82190501)"))
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            metadata.create_all(conn)
            if self.pg:
                conn.execute(text("ALTER TABLE relatos ADD COLUMN IF NOT EXISTS geom geometry(Point,4326)"))
                conn.execute(text("ALTER TABLE incidentes ADD COLUMN IF NOT EXISTS geom geometry(Polygon,4326)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS relatos_geography_idx ON relatos USING gist((geom::geography))"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS incidentes_geometry_idx ON incidentes USING gist(geom)"))

    @contextmanager
    def transaction(self, risk_lock=False):
        # A global aggregation lock is deliberate for this small academic demo:
        # cross-shard nearby reports cannot race to create separate incidents.
        with self.lock if not self.pg else _NullLock():
            with self.engine.begin() as conn:
                if risk_lock and self.pg:
                    conn.execute(text("SELECT pg_advisory_xact_lock(82190502)"))
                yield conn

    def ping(self):
        with self.engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    def list_reports(self, limit=200, offset=0):
        with self.engine.connect() as conn:
            return list(conn.execute(select(relatos.c.data).order_by(relatos.c.occurred_at.desc(), relatos.c.id).limit(limit).offset(offset)).scalars())

    def active_features(self, latitude=None, longitude=None, radius_m=10000, now=None):
        now = now or utc_now()
        with self.engine.connect() as conn:
            stmt = select(incidentes.c.data).where(incidentes.c.active.is_(True), incidentes.c.expires_at > iso(now))
            if self.pg and latitude is not None:
                stmt = stmt.where(text("ST_DWithin(geom::geography,ST_SetSRID(ST_MakePoint(:lon,:lat),4326)::geography,:radius)")).params(lon=longitude, lat=latitude, radius=radius_m)
            items = list(conn.execute(stmt.limit(1000)).scalars())
        if latitude is not None and not self.pg:
            from .geo import distance_m
            items = [x for x in items if distance_m(latitude, longitude, x["properties"]["center_latitude"], x["properties"]["center_longitude"]) <= radius_m + x["properties"]["radius_m"]]
        return items


class _NullLock:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False
