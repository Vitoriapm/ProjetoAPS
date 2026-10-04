-- Schema inicial equivalente à criação protegida por advisory lock em shared/db.py.
-- Para execução manual no PostgreSQL da demonstração, antes de iniciar serviços.
BEGIN;
SELECT pg_advisory_xact_lock(82190501);
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE TABLE IF NOT EXISTS relatos (
    id VARCHAR(36) PRIMARY KEY, installation_id VARCHAR(36) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL, longitude DOUBLE PRECISION NOT NULL,
    tipo VARCHAR(20) NOT NULL, occurred_at VARCHAR(32) NOT NULL,
    data JSON NOT NULL, geom geometry(Point,4326)
);
CREATE INDEX IF NOT EXISTS ix_relatos_occurred_at ON relatos(occurred_at);
CREATE INDEX IF NOT EXISTS relatos_geography_idx ON relatos USING gist((geom::geography));
CREATE TABLE IF NOT EXISTS incidentes (
    id VARCHAR(36) PRIMARY KEY, latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL, tipo VARCHAR(20) NOT NULL,
    expires_at VARCHAR(32) NOT NULL, version INTEGER NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE, data JSON NOT NULL,
    geom geometry(Polygon,4326)
);
CREATE INDEX IF NOT EXISTS ix_incidentes_expires_at ON incidentes(expires_at);
CREATE INDEX IF NOT EXISTS incidentes_geometry_idx ON incidentes USING gist(geom);
CREATE TABLE IF NOT EXISTS relato_incidente (
    relato_id VARCHAR(36) PRIMARY KEY, incidente_id VARCHAR(36) NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_relato_incidente_incidente_id ON relato_incidente(incidente_id);
CREATE TABLE IF NOT EXISTS outbox (
    id VARCHAR(36) PRIMARY KEY, route VARCHAR(100) NOT NULL,
    event JSON NOT NULL, published BOOLEAN NOT NULL DEFAULT FALSE,
    created_at VARCHAR(32) NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_outbox_published ON outbox(published);
CREATE TABLE IF NOT EXISTS eventos_processados (
    consumer VARCHAR(30) NOT NULL, event_id VARCHAR(36) NOT NULL,
    processed_at VARCHAR(32) NOT NULL, PRIMARY KEY(consumer,event_id)
);
CREATE TABLE IF NOT EXISTS dispositivos (id VARCHAR(36) PRIMARY KEY, data JSON NOT NULL);
CREATE TABLE IF NOT EXISTS entregas_alerta (
    id VARCHAR(100) PRIMARY KEY, status VARCHAR(30) NOT NULL,
    provider_id VARCHAR(300), updated_at VARCHAR(32) NOT NULL
);
CREATE TABLE IF NOT EXISTS observacoes_ambientais (id VARCHAR(80) PRIMARY KEY, data JSON NOT NULL);
COMMIT;
