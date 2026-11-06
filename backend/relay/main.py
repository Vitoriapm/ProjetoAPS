"""Publish the durable outbox independently of risk consumers."""
import asyncio
import logging

from backend.shared.broker import publish_loop
from backend.shared.config import Settings
from backend.shared.db import Store


async def run():
    settings = Settings().validate()
    if settings.mode != "full":
        raise ValueError("Relay separado exige ECOPULSE_MODE=full")
    store = Store(settings)
    store.initialize()
    try:
        await publish_loop(store, settings)
    finally:
        store.engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    asyncio.run(run())
