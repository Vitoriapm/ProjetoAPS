"""Two API processes can fetch a previously uncached AQI cell concurrently."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading

import httpx
from sqlalchemy import event, select, func
from sqlalchemy.dialects import postgresql

from backend.shared.config import Settings
from backend.shared.db import Store, environment, outbox, utc_now
from backend.shared.providers import environmental_layers, observation_upsert


def test_concurrent_first_aqi_fetches_share_one_durable_observation(tmp_path):
    database = "sqlite:///" + str(tmp_path / "concurrent-aqi.db")
    stores = []
    for _ in range(2):
        settings = Settings(mode="demo", database_url=database, environment_source="open-meteo").validate()
        repository = Store(settings)
        repository.initialize()
        settings.mode = "full"  # Only the provider branch; isolated SQLite test.
        stores.append(repository)

    responses_ready = threading.Barrier(2)
    stale_read_ready = threading.Barrier(2)

    def after_select(connection, cursor, statement, parameters, context, executemany):
        # Force the old SELECT-id/INSERT race to reproduce deterministically.
        # Atomic upsert has no existence SELECT; this hook is then unused.
        normalized = " ".join(statement.split()).lower()
        if normalized.startswith("select observacoes_ambientais.id "):
            stale_read_ready.wait(timeout=5)

    for repository in stores:
        event.listen(repository.engine, "after_cursor_execute", after_select)

    def fetch(repository, value):
        def provider(request):
            responses_ready.wait(timeout=5)
            return httpx.Response(200, json={"latitude": -21.2, "longitude": -47.8,
                "current": {"time": utc_now().replace(tzinfo=None).isoformat(timespec="minutes"), "us_aqi": value}})

        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as client:
                return await environmental_layers(repository, repository.settings, -21.1775, -47.8101, client)
        return asyncio.run(run())

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(fetch, repository, value)
                for repository, value in zip(stores, [61, 62])]
            collections = [future.result(timeout=10) for future in futures]
        assert [collection["features"][0]["properties"]["value"] for collection in collections] == [61, 62]
        with stores[0].engine.connect() as connection:
            assert connection.execute(select(func.count()).select_from(environment)).scalar_one() == 1
            assert connection.execute(select(func.count()).select_from(outbox)).scalar_one() == 2
            cached = connection.execute(select(environment.c.data)).scalar_one()
            assert cached["properties"]["value"] in {61, 62}
    finally:
        for repository in stores:
            repository.engine.dispose()


def test_postgresql_observation_uses_atomic_conflict_update():
    statement = observation_upsert("aqi:test-cell", {"properties": {"value": 61}}, postgres=True)
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "ON CONFLICT (id) DO UPDATE SET data = excluded.data" in sql
    assert compiled.params["id"] == "aqi:test-cell"
    assert compiled.params["data"]["properties"]["value"] == 61
