"""RabbitMQ: confirms, outbox durável e retry/DLQ com confirmação antes do ack."""
import asyncio
import json
import logging
from datetime import timedelta
import aio_pika
from pydantic import ValidationError
from sqlalchemy import select, update
from .db import outbox

log = logging.getLogger(__name__)
EXCHANGE = "ecopulse.events"
RETRY_SECONDS = (1, 5, 15)


async def connect(settings):
    last = None
    for url in settings.amqp_urls:
        try:
            # Recovery is controlled by our loop, which retries *all* nodes.
            # connect_robust would keep reconnecting only to the original host.
            return await aio_pika.connect(url.strip(), timeout=5)
        except Exception as exc:
            last = exc
    raise ConnectionError("RabbitMQ indisponível em todos os nós configurados") from last


async def topology(channel, settings):
    exchange = await channel.declare_exchange(EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True)
    names = [f"ecopulse.risk.{i}" for i in range(settings.shard_count)] + ["ecopulse.alerts"]
    queues = {}
    for name in names:
        quorum = {"x-queue-type": "quorum", "x-quorum-initial-group-size": settings.quorum_size}
        queue = await channel.declare_queue(name, durable=True, arguments={**quorum,
            "x-dead-letter-exchange": "", "x-dead-letter-routing-key": name + ".dlq",
            "x-overflow": "reject-publish"})
        route = "incidente.#" if name == "ecopulse.alerts" else f"relato.{name.rsplit('.', 1)[1]}"
        await queue.bind(exchange, route)
        if name == "ecopulse.alerts":
            await queue.bind(exchange, "camada.atualizada")
        await channel.declare_queue(name + ".retry", durable=True, arguments={
            **quorum, "x-dead-letter-exchange": "", "x-overflow": "reject-publish",
            "x-dead-letter-routing-key": name})
        # Unlimited DLQ redelivery is configured by the server policy. pamqp
        # encodes small negative integers as an unsigned octet and cannot
        # serialize x-delivery-limit=-1; a failed declaration stops consumers.
        await channel.declare_queue(name + ".dlq", durable=True, arguments=quorum)
        queues[name] = queue
    return exchange, queues


async def outbox_once(store, exchange):
    # Keep row locks until broker confirmation + database commit. If a crash
    # occurs after confirmation, a repeat is harmless to idempotent consumers.
    with store.transaction() as conn:
        stmt = select(outbox).where(outbox.c.published.is_(False)).order_by(outbox.c.created_at).limit(30)
        if store.pg:
            stmt = stmt.with_for_update(skip_locked=True)
        rows = list(conn.execute(stmt).mappings())
        for row in rows:
            message = aio_pika.Message(json.dumps(row["event"]).encode(), content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT, message_id=row["id"])
            confirmed = await exchange.publish(message, routing_key=row["route"], mandatory=True, timeout=10)
            if confirmed is False:
                raise ConnectionError("Publicação não confirmada pelo RabbitMQ")
            conn.execute(update(outbox).where(outbox.c.id == row["id"]).values(published=True))
    return len(rows)


async def publish_loop(store, settings, state=None):
    while True:
        connection = None
        try:
            connection = await connect(settings)
            channel = await connection.channel(publisher_confirms=True, on_return_raises=True)
            exchange, _ = await topology(channel, settings)
            if state is not None:
                state["broker"] = "ok"
            while True:
                if not connection.connected.is_set():
                    raise ConnectionError("Conexão RabbitMQ encerrada; tentando os outros nós")
                await outbox_once(store, exchange)
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if state is not None:
                state["broker"] = "indisponivel"
            log.warning("Outbox aguardando RabbitMQ: %s", type(exc).__name__)
            await asyncio.sleep(3)
        finally:
            if connection:
                await connection.close()


async def handle_delivery(message, queue_name, channel, callback):
    try:
        payload = json.loads(message.body)
        await callback(payload)
        await message.ack()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        retries = int((message.headers or {}).get("ecopulse-retries", 0))
        invalid = isinstance(exc, (ValueError, KeyError, ValidationError, json.JSONDecodeError))
        dead = invalid or retries >= len(RETRY_SECONDS)
        # No traceback/body/token in presentation logs. DLQ metadata identifies
        # event + error class, while original private data remains in its DB.
        headers = {**(message.headers or {}), "ecopulse-retries": retries + 1,
            "ecopulse-error": type(exc).__name__, "ecopulse-original-queue": queue_name}
        retry_message = aio_pika.Message(message.body, content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT, message_id=message.message_id,
            headers=headers, expiration=None if dead else timedelta(seconds=RETRY_SECONDS[retries]))
        try:
            confirmed = await channel.default_exchange.publish(retry_message,
                routing_key=queue_name + (".dlq" if dead else ".retry"), mandatory=True, timeout=10)
            if confirmed is False:
                raise ConnectionError("Retry não confirmado")
            await message.ack()
            log.warning("Mensagem enviada a %s (%s)", "DLQ" if dead else "retry", type(exc).__name__)
        except Exception:
            # Never acknowledge the original if re-publication was unconfirmed.
            await message.nack(requeue=True)
            log.error("Republicação falhou; mensagem original permanece no broker")


async def consume_loop(store, settings, service, callback):
    while True:
        connection = None
        try:
            connection = await connect(settings)
            disconnected = asyncio.Event()
            connection.close_callbacks.add(lambda *_: disconnected.set())
            channel = await connection.channel(publisher_confirms=True, on_return_raises=True)
            await channel.set_qos(prefetch_count=4)
            channel.close_callbacks.add(lambda *_: disconnected.set())
            _, queues = await topology(channel, settings)
            names = [f"ecopulse.risk.{i}" for i in range(settings.shard_count)] if service == "risk" else ["ecopulse.alerts"]
            for name in names:
                async def handler(message, queue_name=name):
                    await handle_delivery(message, queue_name, channel, callback)
                await queues[name].consume(handler, no_ack=False)
            # Both workers consume all partition queues. RabbitMQ shares work;
            # unacked deliveries return to the other worker after failure.
            await disconnected.wait()
            raise ConnectionError("Conexão do consumidor encerrada; tentando os outros nós")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("Consumidor %s aguardando broker: %s", service, type(exc).__name__)
            await asyncio.sleep(3)
        finally:
            if connection:
                await connection.close()
