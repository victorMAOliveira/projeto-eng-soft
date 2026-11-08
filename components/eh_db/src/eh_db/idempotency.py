"""SQL implementation of the event idempotency store used by event consumers."""

from datetime import datetime

from sqlalchemy import DateTime, String, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from eh_db.base import Base
from eh_db.database import Database


class ProcessedEvent(Base):
    """One row per event already handled by this service (dedup by ``event_id``)."""

    __tablename__ = "processed_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SqlIdempotencyStore:
    """Implements the ``eh_events`` idempotency protocol on the service database."""

    def __init__(self, database: Database) -> None:
        self.database = database

    async def seen(self, event_id: str) -> bool:
        """Return ``True`` if ``event_id`` was already processed."""
        async with self.database.session() as session:
            found = await session.scalar(
                select(ProcessedEvent.event_id).where(ProcessedEvent.event_id == event_id)
            )
            return found is not None

    async def mark(self, event_id: str, event_type: str) -> None:
        """Record ``event_id`` as processed (safe to call twice)."""
        try:
            async with self.database.session() as session:
                session.add(ProcessedEvent(event_id=event_id, event_type=event_type))
        except IntegrityError:
            return
