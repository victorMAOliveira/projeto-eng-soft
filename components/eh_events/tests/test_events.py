import json
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

import eh_events.consumer as consumer_module
import eh_events.publisher as publisher_module
from eh_events import (
    PAYLOAD_MODELS,
    ApplicationStatusChanged,
    Event,
    EventConsumer,
    EventPublisher,
    EventType,
    InMemoryIdempotencyStore,
    InMemoryPublisher,
    PlacementTerms,
    make_event,
    parse_event,
    typed_payload,
)


def user_payload(**overrides):
    return {"user_id": 1, "email": "a@ufal.test", "name": "Ana", "role": "student", **overrides}


class FakeMessage:
    def __init__(self, body: bytes, headers: dict | None = None):
        self.body = body
        self.headers = headers or {}
        self.message_id = "m1"
        self.acked = False
        self.rejected = None

    async def ack(self):
        self.acked = True

    async def reject(self, requeue: bool = False):
        self.rejected = requeue


class FakeExchange:
    def __init__(self):
        self.published = []

    async def publish(self, message, routing_key):
        self.published.append((message, routing_key))


class FakeQueue:
    def __init__(self, name):
        self.name = name
        self.bindings = []
        self.cancelled = None

    async def bind(self, exchange, routing_key):
        self.bindings.append(routing_key)

    async def consume(self, callback):
        self.callback = callback
        return "tag-1"

    async def cancel(self, tag):
        self.cancelled = tag


class FakeChannel:
    def __init__(self):
        self.exchanges = {}
        self.queues = {}
        self.default_exchange = FakeExchange()

    async def set_qos(self, prefetch_count):
        self.prefetch = prefetch_count

    async def declare_exchange(self, name, kind, durable):
        self.exchanges[name] = FakeExchange()
        return self.exchanges[name]

    async def declare_queue(self, name, durable, arguments=None):
        self.queues[name] = (FakeQueue(name), arguments)
        return self.queues[name][0]


class FakeConnection:
    def __init__(self):
        self.channel_obj = FakeChannel()
        self.is_closed = False

    async def channel(self, **kwargs):
        return self.channel_obj

    async def close(self):
        self.is_closed = True


@pytest.fixture
def fake_connection(monkeypatch):
    connection = FakeConnection()

    async def connect_robust(url):
        return connection

    monkeypatch.setattr(publisher_module.aio_pika, "connect_robust", connect_robust)
    return connection


def test_every_event_type_has_a_payload_model():
    assert set(PAYLOAD_MODELS) == set(EventType)


def test_make_and_parse_roundtrip():
    event = make_event(EventType.USER_REGISTERED, user_payload(), producer="user-service")
    assert event.schema_version == 1
    assert len(event.event_id) == 32
    parsed = parse_event(event.model_dump_json())
    assert parsed == event
    assert typed_payload(parsed).name == "Ana"


def test_make_event_rejects_invalid_payload():
    with pytest.raises(ValidationError):
        make_event("user.registered", {"user_id": "x"}, producer="p")


def test_nested_placement_terms_are_serialised():
    payload = ApplicationStatusChanged(
        application_id=1,
        internship_id=2,
        student_id=3,
        company_id=4,
        student_name="Ana",
        internship_title="Dev",
        from_status="under_review",
        to_status="approved",
        placement=PlacementTerms(
            start_date=date(2026, 12, 1),
            end_date=date(2027, 6, 1),
            hours_per_day=6,
            hours_per_week=30,
            stipend=1200,
            supervisor_name="Bruno",
            insurer="Seguradora",
            insurance_policy="AP-1",
        ),
    )
    event = make_event(EventType.APPLICATION_STATUS_CHANGED, payload, producer="application")
    assert event.payload["placement"]["start_date"] == "2026-12-01"
    assert typed_payload(event).placement.hours_per_week == 30


async def test_in_memory_publisher_records_events():
    publisher = InMemoryPublisher("svc")
    await publisher.connect()
    await publisher.publish(EventType.USER_REGISTERED, user_payload(), correlation_id="c1")
    await publisher.publish_event(
        make_event("internship.closed", {"internship_id": 1, "company_id": 2}, producer="x")
    )
    assert len(publisher.of_type("user.registered")) == 1
    assert publisher.events[0].correlation_id == "c1"
    assert await publisher.is_connected()
    await publisher.close()


async def test_event_publisher_publishes_persistent_message(fake_connection):
    publisher = EventPublisher("amqp://x", service_name="user-service")
    with pytest.raises(RuntimeError):
        await publisher.publish(EventType.USER_REGISTERED, user_payload())
    await publisher.connect()
    assert await publisher.is_connected()
    event = await publisher.publish(EventType.USER_REGISTERED, user_payload())
    exchange = fake_connection.channel_obj.exchanges["estagiohub.events"]
    message, routing_key = exchange.published[0]
    assert routing_key == "user.registered"
    assert json.loads(message.body)["event_id"] == event.event_id
    assert int(message.delivery_mode) == 2
    await publisher.close()
    assert not await publisher.is_connected()


async def test_connect_with_retry_retries_then_fails(monkeypatch):
    attempts = []

    async def failing(url):
        attempts.append(url)
        raise OSError("refused")

    monkeypatch.setattr(publisher_module.aio_pika, "connect_robust", failing)
    with pytest.raises(OSError):
        await publisher_module.connect_with_retry("amqp://x", attempts=3, delay=0)
    assert len(attempts) == 3


def build_consumer(handler, store=None, **kwargs):
    return EventConsumer(
        "amqp://x",
        queue_name="svc.events",
        routing_keys=["user.registered", "profile.#"],
        handler=handler,
        idempotency=store or InMemoryIdempotencyStore(),
        retry_delay=0,
        **kwargs,
    )


async def test_consumer_declares_topology_with_dlq(fake_connection):
    async def handler(event):
        pass

    consumer = build_consumer(handler)
    await consumer.start()
    channel = fake_connection.channel_obj
    queue, arguments = channel.queues["svc.events"]
    assert arguments["x-dead-letter-exchange"] == "estagiohub.events.dlx"
    assert arguments["x-dead-letter-routing-key"] == "svc.events.dlq"
    assert queue.bindings == ["user.registered", "profile.#"]
    assert channel.queues["svc.events.dlq"][0].bindings == ["svc.events.dlq"]
    assert channel.prefetch == 1
    assert await consumer.is_connected()
    await consumer.stop()
    assert queue.cancelled == "tag-1"
    assert not await consumer.is_connected()


async def test_consumer_processes_once_and_skips_duplicates(fake_connection):
    handled = []

    async def handler(event: Event):
        handled.append(event.event_id)

    consumer = build_consumer(handler)
    await consumer.start()
    body = make_event("user.registered", user_payload(), producer="p").model_dump_json().encode()
    first, second = FakeMessage(body), FakeMessage(body)
    assert await consumer.handle_message(first) == "processed"
    assert await consumer.handle_message(second) == "duplicate"
    assert len(handled) == 1
    assert first.acked and second.acked


async def test_consumer_retries_then_dead_letters(fake_connection):
    async def handler(event):
        raise RuntimeError("downstream failure")

    consumer = build_consumer(handler, max_retries=2)
    await consumer.start()
    body = make_event("user.registered", user_payload(), producer="p").model_dump_json().encode()

    message = FakeMessage(body)
    assert await consumer.handle_message(message) == "retried"
    republished, routing_key = fake_connection.channel_obj.default_exchange.published[0]
    assert routing_key == "svc.events"
    assert republished.headers["x-retry"] == 1
    assert message.acked

    exhausted = FakeMessage(body, headers={"x-retry": 2})
    assert await consumer.handle_message(exhausted) == "dead_lettered"
    assert exhausted.rejected is False


async def test_consumer_dead_letters_invalid_messages():
    async def handler(event):
        raise AssertionError("must not be called")

    consumer = build_consumer(handler)
    message = FakeMessage(b'{"not": "an event"}')
    assert await consumer.handle_message(message) == "dead_lettered"
    assert message.rejected is False


async def test_republish_requires_started_consumer():
    async def handler(event):
        raise RuntimeError

    consumer = build_consumer(handler)
    body = make_event("user.registered", user_payload(), producer="p").model_dump_json().encode()
    with pytest.raises(RuntimeError):
        await consumer.handle_message(FakeMessage(body))


def test_event_defaults_are_timezone_aware():
    event = Event(event_type="internship.closed", producer="x", payload={})
    assert event.occurred_at.tzinfo is not None
    assert event.occurred_at <= datetime.now(UTC)
    assert consumer_module.RETRY_HEADER == "x-retry"
