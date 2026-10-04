import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from backend.shared.broker import handle_delivery, connect, topology
from pamqp.encode import field_table


def message(body=b'{"test":true}', headers=None):
    return SimpleNamespace(body=body, headers=headers or {}, message_id="test", ack=AsyncMock(), nack=AsyncMock())


def test_invalid_message_goes_to_confirmed_dlq_before_ack():
    original = message(b"invalid-json")
    exchange = SimpleNamespace(publish=AsyncMock(return_value=True))
    asyncio.run(handle_delivery(original, "ecopulse.risk.0", SimpleNamespace(default_exchange=exchange), AsyncMock()))
    assert exchange.publish.call_args.kwargs["routing_key"] == "ecopulse.risk.0.dlq"
    original.ack.assert_awaited_once()
    original.nack.assert_not_awaited()


def test_transient_failure_retries_with_persistent_message_and_limit():
    callback = AsyncMock(side_effect=ConnectionError("provider unavailable"))
    exchange = SimpleNamespace(publish=AsyncMock(return_value=True))
    for retry in range(4):
        original = message(headers={"ecopulse-retries": retry})
        asyncio.run(handle_delivery(original, "ecopulse.alerts", SimpleNamespace(default_exchange=exchange), callback))
        target = exchange.publish.call_args.kwargs["routing_key"]
        assert target.endswith(".retry" if retry < 3 else ".dlq")
        forwarded = exchange.publish.call_args.args[0]
        assert forwarded.delivery_mode.value == 2
        original.ack.assert_awaited_once()


def test_unconfirmed_republication_never_acknowledges_original():
    original = message()
    exchange = SimpleNamespace(publish=AsyncMock(side_effect=ConnectionError("broker down")))
    asyncio.run(handle_delivery(original, "ecopulse.alerts", SimpleNamespace(default_exchange=exchange), AsyncMock(side_effect=RuntimeError("FCM unavailable"))))
    original.ack.assert_not_awaited()
    original.nack.assert_awaited_once_with(requeue=True)


def test_effect_committed_before_consumer_ack():
    order = []
    original = message()
    async def callback(payload):
        order.append("commit")
    async def ack():
        order.append("ack")
    original.ack = ack
    asyncio.run(handle_delivery(original, "ecopulse.risk.0", SimpleNamespace(), callback))
    assert order == ["commit", "ack"]


def test_each_reconnection_attempt_can_select_another_broker_node():
    config = SimpleNamespace(amqp_urls=["amqp://node1/", "amqp://node2/", "amqp://node3/"])
    connection = object()
    mocked = AsyncMock(side_effect=[ConnectionError(), connection, ConnectionError(), ConnectionError(), connection])
    with patch("backend.shared.broker.aio_pika.connect", mocked):
        assert asyncio.run(connect(config)) is connection
        assert asyncio.run(connect(config)) is connection
    assert [call.args[0] for call in mocked.call_args_list] == ["amqp://node1/", "amqp://node2/", "amqp://node1/", "amqp://node2/", "amqp://node3/"]


def test_queue_arguments_encode_with_the_real_amqp_library():
    channel = SimpleNamespace(declare_exchange=AsyncMock(), declare_queue=AsyncMock())
    asyncio.run(topology(channel, SimpleNamespace(shard_count=4, quorum_size=3)))
    for call in channel.declare_queue.call_args_list:
        assert field_table(call.kwargs["arguments"])


def test_uvicorn_websocket_log_redacts_token():
    import logging
    from backend.api.main import RedactWebSocketToken
    record = logging.LogRecord("uvicorn.error", logging.INFO, "test", 1,
        '%s - "WebSocket %s" [accepted]', ("client", "/v1/ws?token=private-jwt&other=value"), None)
    assert RedactWebSocketToken().filter(record)
    assert "private-jwt" not in record.getMessage()
    assert "token=[redacted]&other=value" in record.getMessage()
