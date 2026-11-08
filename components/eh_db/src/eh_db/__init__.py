"""eh_db — persistence building blocks for the PostgreSQL-backed services.

Public interface:

* :class:`Base` / :class:`TimestampMixin` — declarative base with a stable
  constraint naming convention and created/updated timestamps.
* :class:`Database` — async engine + session factory, readiness ``ping`` and a
  FastAPI ``get_session`` dependency.
* :class:`BaseRepository` — generic CRUD repository.
* :class:`ProcessedEvent` / :class:`SqlIdempotencyStore` — ``event_id``
  deduplication table for idempotent event consumers.
* :func:`run_migrations` — body of every service's Alembic ``env.py``.
"""

from eh_db.base import Base, TimestampMixin
from eh_db.database import Database
from eh_db.idempotency import ProcessedEvent, SqlIdempotencyStore
from eh_db.migrations import run_migrations
from eh_db.repository import BaseRepository

__version__ = "1.0.0"

__all__ = [
    "Base",
    "BaseRepository",
    "Database",
    "ProcessedEvent",
    "SqlIdempotencyStore",
    "TimestampMixin",
    "run_migrations",
]
