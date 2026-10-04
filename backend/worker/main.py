import asyncio
import logging
from backend.shared.broker import consume_loop, publish_loop
from backend.shared.config import Settings
from backend.shared.db import Store
from backend.shared.domain import expire_incidents, process_report


async def run():
    settings = Settings().validate()
    if settings.mode != "full":
        raise ValueError("Worker separado exige ECOPULSE_MODE=full")
    store = Store(settings)
    store.initialize()

    async def process(payload):
        await asyncio.to_thread(process_report, store, payload)

    async def expiration():
        while True:
            await asyncio.to_thread(expire_incidents, store)
            await asyncio.sleep(15)

    await asyncio.gather(consume_loop(store, settings, "risk", process), publish_loop(store, settings), expiration())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    asyncio.run(run())
