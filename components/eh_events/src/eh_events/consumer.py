"""Idempotent RabbitMQ consumer with retry/backoff and a dead-letter queue."""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, Protocol

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractQueue, AbstractRobustConnection
from pydantic import ValidationError

from eh_events.contracts import Event, parse_event
from eh_events.publisher import DLX_NAME, EXCHANGE_NAME, connect_with_retry

logger = logging.getLogger(__name__)

Handler = Callable[[Event], Awaitable[None]]
RETRY_HEADER = "x-retry"


class IdempotencyStore(Protocol):
    """Remembers which ``event_id`` values were already processed."""

    async def seen(self, event_id: str) -> bool:
        """Return ``True`` if the event was processed before."""
        ...

    async def mark(self, event_id: str, event_type: str) -> None:
        """Record the event as processed."""
        ...


class InMemoryIdempotencyStore:
    """Process-local store, used in tests and as reference implementation."""

    def __init__(self) -> None:
        self.ids: set[str] = set()

    async def seen(self, event_id: str) -> bool:
        """Return ``True`` if ``event_id`` was marked."""
        return event_id in self.ids

    async def mark(self, event_id: str, event_type: str) -> None:
        """Mark ``event_id``."""
        self.ids.add(event_id)


class EventConsumer:
    """Consume events from a durable queue bound to the topic exchange.

    Topology declared on :meth:`start`::

        estagiohub.events (topic) --routing keys--> <queue>
        <queue> --x-dead-letter-exchange--> estagiohub.events.dlx --> <queue>.dlq

    For each message: invalid payloads go straight to the DLQ; duplicates
    (same ``event_id``) are acknowledged and skipped; handler failures are
    retried ``max_retries`` times with exponential backoff and then
    dead-lettered.
    """

    def __init__(
        self,
        url: str,
        *,
        queue_name: str,
        routing_keys: Iterable[str],
        handler: Handler,
        idempotency: IdempotencyStore,
        max_retries: int = 3,
        retry_delay: float = 0.5,
        prefetch: int = 1,
        exchange_name: str = EXCHANGE_NAME,
    ) -> None:
        self.url = url
        self.queue_name = queue_name
        self.routing_keys = list(routing_keys)
        self.handler = handler
        self.idempotency = idempotency
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.prefetch = prefetch
        self.exchange_name = exchange_name
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractChannel | None = None
        self._queue: AbstractQueue | None = None
        self._consumer_tag: str | None = None

    @property
    def dlq_name(self) -> str:
        """Name of this consumer's dead-letter queue."""
        return f"{self.queue_name}.dlq"

    async def start(self) -> None:
        """Connect, declare the topology and start consuming."""
        self._connection = await connect_with_retry(self.url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self.prefetch)
        exchange = await self._channel.declare_exchange(
            self.exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
        )
        dlx = await self._channel.declare_exchange(
            DLX_NAME, aio_pika.ExchangeType.DIRECT, durable=True
        )
        dlq = await self._channel.declare_queue(self.dlq_name, durable=True)
        await dlq.bind(dlx, routing_key=self.dlq_name)
        self._queue = await self._channel.declare_queue(
            self.queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": DLX_NAME,
                "x-dead-letter-routing-key": self.dlq_name,
            },
        )
        for key in self.routing_keys:
            await self._queue.bind(exchange, routing_key=key)
        self._consumer_tag = await self._queue.consume(self.handle_message)
        logger.info("consumer started", extra={"queue": self.queue_name, "keys": self.routing_keys})

    async def handle_message(self, message: Any) -> str:
        """Process one delivery; returns the outcome (useful for tests and logs).

        Outcomes: ``processed``, ``duplicate``, ``retried`` or ``dead_lettered``.
        """
        try:
            event = parse_event(message.body)
        except (ValidationError, ValueError, KeyError):
            logger.error("invalid event sent to DLQ", extra={"queue": self.queue_name})
            await message.reject(requeue=False)
            return "dead_lettered"

        if await self.idempotency.seen(event.event_id):
            await message.ack()
            return "duplicate"

        try:
            await self.handler(event)
        except Exception:
            retries = int((message.headers or {}).get(RETRY_HEADER, 0))
            if retries < self.max_retries:
                logger.warning(
                    "handler failed, retrying",
                    exc_info=True,
                    extra={"event_id": event.event_id, "retry": retries + 1},
                )
                await asyncio.sleep(self.retry_delay * 2**retries)
                await self._republish(message, retries + 1)
                await message.ack()
                return "retried"
            logger.error(
                "handler failed, dead-lettering",
                exc_info=True,
                extra={"event_id": event.event_id},
            )
            await message.reject(requeue=False)
            return "dead_lettered"

        await self.idempotency.mark(event.event_id, event.event_type.value)
        await message.ack()
        return "processed"

    async def _republish(self, message: Any, retry: int) -> None:
        if self._channel is None:
            raise RuntimeError("consumer not started")
        headers = dict(message.headers or {})
        headers[RETRY_HEADER] = retry
        await self._channel.default_exchange.publish(
            aio_pika.Message(
                body=message.body,
                headers=headers,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                message_id=getattr(message, "message_id", None),
            ),
            routing_key=self.queue_name,
        )

    async def is_connected(self) -> bool:
        """Readiness probe: ``True`` while the connection is open."""
        return self._connection is not None and not self._connection.is_closed

    async def stop(self) -> None:
        """Cancel consumption and close the connection."""
        if self._queue is not None and self._consumer_tag is not None:
            await self._queue.cancel(self._consumer_tag)
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
