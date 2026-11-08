"""eh_events — event-driven communication between EstágioHub services.

Public interface:

* :class:`Event`, :class:`EventType` and one payload model per event — the
  versioned contracts (``event_id``, ``occurred_at``, ``schema_version``,
  ``payload``).
* :func:`make_event`, :func:`parse_event`, :func:`typed_payload` — helpers.
* :class:`EventPublisher` / :class:`InMemoryPublisher` — publish to the
  ``estagiohub.events`` topic exchange (or record them in tests).
* :class:`EventConsumer` — durable queue consumer with idempotency
  (deduplication by ``event_id``), retry with backoff and dead-letter queue.
* :class:`IdempotencyStore` / :class:`InMemoryIdempotencyStore` — protocol and
  reference implementation used by consumers.
"""

from eh_events.consumer import EventConsumer, IdempotencyStore, InMemoryIdempotencyStore
from eh_events.contracts import (
    PAYLOAD_MODELS,
    SCHEMA_VERSION,
    AgreementApproved,
    AgreementGenerated,
    ApplicationStatusChanged,
    ApplicationSubmitted,
    Event,
    EventType,
    InternshipClosed,
    InternshipPublished,
    PlacementTerms,
    ProfileUpdated,
    ReportDueSoon,
    ReportSubmitted,
    UserRegistered,
    make_event,
    parse_event,
    typed_payload,
)
from eh_events.publisher import (
    DLX_NAME,
    EXCHANGE_NAME,
    EventPublisher,
    InMemoryPublisher,
    Publisher,
)

__version__ = "1.0.0"

__all__ = [
    "DLX_NAME",
    "EXCHANGE_NAME",
    "PAYLOAD_MODELS",
    "SCHEMA_VERSION",
    "AgreementApproved",
    "AgreementGenerated",
    "ApplicationStatusChanged",
    "ApplicationSubmitted",
    "Event",
    "EventConsumer",
    "EventPublisher",
    "EventType",
    "IdempotencyStore",
    "InMemoryIdempotencyStore",
    "InMemoryPublisher",
    "InternshipClosed",
    "InternshipPublished",
    "PlacementTerms",
    "ProfileUpdated",
    "Publisher",
    "ReportDueSoon",
    "ReportSubmitted",
    "UserRegistered",
    "make_event",
    "parse_event",
    "typed_payload",
]
