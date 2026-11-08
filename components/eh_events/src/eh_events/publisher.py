"""Event publishers: RabbitMQ (aio-pika) and an in-memory test double."""

import asyncio
import logging
from typing import Any, Protocol

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractRobustConnection
from pydantic import BaseModel

from eh_events.contracts import Event, EventType, make_event

EXCHANGE_NAME = "estagiohub.events"
DLX_NAME = "estagiohub.events.dlx"

logger = logging.getLogger(__name__)


class Publisher(Protocol):
    """What services depend on: anything able to publish an event."""

    async def publish(
        self,
        event_type: EventType | str,
        payload: BaseModel | dict[str, Any],
        *,
        correlation_id: str | None = None,
    ) -> Event:
        """Publish a new event and return it."""
        ...


async def connect_with_retry(
    url: str, *, attempts: int = 15, delay: float = 2.0
) -> AbstractRobustConnection:
    """Open a robust RabbitMQ connection, retrying while the broker boots."""
    for attempt in range(1, attempts + 1):
        try:
            return await aio_pika.connect_robust(url)
        except (OSError, aio_pika.exceptions.AMQPError) as exc:
            if attempt == attempts:
                raise
            logger.warning("broker not reachable (%s), retry %s/%s", exc, attempt, attempts)
            await asyncio.sleep(delay)
    raise RuntimeError("unreachable")  # pragma: no cover


class EventPublisher:
    """Publish events as persistent JSON messages on the topic exchange.

    The routing key is the event type (e.g. ``application.status_changed``),
    so consumers bind their queues with exact keys or wildcards.
    """

    def __init__(
        self,
        url: str,
        *,
        service_name: str,
        exchange_name: str = EXCHANGE_NAME,
        connect_attempts: int = 15,
        connect_delay: float = 2.0,
    ) -> None:
        self.url = url
        self.service_name = service_name
        self.exchange_name = exchange_name
        self.connect_attempts = connect_attempts
        self.connect_delay = connect_delay
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractChannel | None = None
        self._exchange: AbstractExchange | None = None

    async def connect(self) -> None:
        """Connect and declare the durable topic exchange."""
        self._connection = await connect_with_retry(
            self.url, attempts=self.connect_attempts, delay=self.connect_delay
        )
        self._channel = await self._connection.channel(publisher_confirms=True)
        self._exchange = await self._channel.declare_exchange(
            self.exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
        )

    async def publish(
        self,
        event_type: EventType | str,
        payload: BaseModel | dict[str, Any],
        *,
        correlation_id: str | None = None,
    ) -> Event:
        """Validate, wrap and publish an event; return the published envelope."""
        event = make_event(
            event_type, payload, producer=self.service_name, correlation_id=correlation_id
        )
        await self.publish_event(event)
        return event

    async def publish_event(self, event: Event) -> None:
        """Publish an already built :class:`Event`."""
        if self._exchange is None:
            raise RuntimeError("EventPublisher.connect() must be awaited first")
        message = aio_pika.Message(
            body=event.model_dump_json().encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            message_id=event.event_id,
            correlation_id=event.correlation_id,
            type=event.event_type.value,
            app_id=self.service_name,
        )
        await self._exchange.publish(message, routing_key=event.event_type.value)
        logger.info(
            "event published",
            extra={"event_type": event.event_type.value, "event_id": event.event_id},
        )

    async def is_connected(self) -> bool:
        """Readiness probe: ``True`` while the connection is open."""
        return self._connection is not None and not self._connection.is_closed

    async def close(self) -> None:
        """Close the connection."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
            self._exchange = None


class InMemoryPublisher:
    """Test double that records published events instead of sending them."""

    def __init__(self, service_name: str = "test") -> None:
        self.service_name = service_name
        self.events: list[Event] = []

    async def connect(self) -> None:
        """No-op."""

    async def publish(
        self,
        event_type: EventType | str,
        payload: BaseModel | dict[str, Any],
        *,
        correlation_id: str | None = None,
    ) -> Event:
        """Validate and store the event."""
        event = make_event(
            event_type, payload, producer=self.service_name, correlation_id=correlation_id
        )
        self.events.append(event)
        return event

    async def publish_event(self, event: Event) -> None:
        """Store an already built event."""
        self.events.append(event)

    def of_type(self, event_type: EventType | str) -> list[Event]:
        """Return recorded events of ``event_type``."""
        return [e for e in self.events if e.event_type == EventType(event_type)]

    async def is_connected(self) -> bool:
        """Always ready."""
        return True

    async def close(self) -> None:
        """No-op."""
