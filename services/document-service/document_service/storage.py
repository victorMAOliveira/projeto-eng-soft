"""Persistence ports and adapters: MongoDB for metadata, a volume for files.

The service code depends only on :class:`DocumentCollection`; MongoDB is
used in production and :class:`InMemoryCollection` in tests.
"""

import copy
from pathlib import Path
from typing import Any, Protocol

from pymongo import DESCENDING, AsyncMongoClient
from pymongo.errors import DuplicateKeyError


class DocumentCollection(Protocol):
    """Minimal document-store operations used by the service."""

    async def insert(self, doc: dict[str, Any]) -> None:
        """Insert ``doc`` (``_id`` must be unique)."""
        ...

    async def get(self, doc_id: str) -> dict[str, Any] | None:
        """Return the document with ``_id == doc_id``."""
        ...

    async def find(self, filters: dict[str, Any], limit: int = 200) -> list[dict[str, Any]]:
        """Documents matching equality ``filters``, newest first."""
        ...

    async def update(
        self, doc_id: str, set_fields: dict[str, Any], push: dict[str, Any] | None = None
    ) -> None:
        """Set fields and optionally append to array fields."""
        ...


class MongoCollection:
    """:class:`DocumentCollection` backed by a MongoDB collection."""

    def __init__(self, collection: Any) -> None:
        self._c = collection

    async def insert(self, doc: dict[str, Any]) -> None:
        """Insert one document."""
        await self._c.insert_one(doc)

    async def get(self, doc_id: str) -> dict[str, Any] | None:
        """Find by ``_id``."""
        return await self._c.find_one({"_id": doc_id})

    async def find(self, filters: dict[str, Any], limit: int = 200) -> list[dict[str, Any]]:
        """Find by equality filters, sorted by ``created_at`` descending."""
        cursor = self._c.find(filters).sort("created_at", DESCENDING).limit(limit)
        return await cursor.to_list(length=limit)

    async def update(
        self, doc_id: str, set_fields: dict[str, Any], push: dict[str, Any] | None = None
    ) -> None:
        """``$set`` (and ``$push``) on one document."""
        operation: dict[str, Any] = {"$set": set_fields}
        if push:
            operation["$push"] = push
        await self._c.update_one({"_id": doc_id}, operation)


class InMemoryCollection:
    """Dict-based :class:`DocumentCollection` for tests."""

    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    async def insert(self, doc: dict[str, Any]) -> None:
        """Insert, rejecting duplicate ``_id`` like MongoDB."""
        if doc["_id"] in self.docs:
            raise DuplicateKeyError("duplicate _id")
        self.docs[doc["_id"]] = copy.deepcopy(doc)

    async def get(self, doc_id: str) -> dict[str, Any] | None:
        """Find by ``_id``."""
        doc = self.docs.get(doc_id)
        return copy.deepcopy(doc) if doc else None

    async def find(self, filters: dict[str, Any], limit: int = 200) -> list[dict[str, Any]]:
        """Equality filters, newest first."""
        found = [
            copy.deepcopy(d)
            for d in self.docs.values()
            if all(d.get(k) == v for k, v in filters.items())
        ]
        found.sort(key=lambda d: d.get("created_at"), reverse=True)
        return found[:limit]

    async def update(
        self, doc_id: str, set_fields: dict[str, Any], push: dict[str, Any] | None = None
    ) -> None:
        """Apply ``$set``/``$push`` semantics."""
        doc = self.docs[doc_id]
        doc.update(copy.deepcopy(set_fields))
        for key, value in (push or {}).items():
            doc.setdefault(key, []).append(copy.deepcopy(value))


class Store:
    """The three collections of the ``documents`` database."""

    def __init__(
        self,
        agreements: DocumentCollection,
        reports: DocumentCollection,
        processed: DocumentCollection,
        ping: Any = None,
    ) -> None:
        self.agreements = agreements
        self.reports = reports
        self.processed = processed
        self._ping = ping
        self.client: AsyncMongoClient | None = None

    @classmethod
    def mongo(cls, url: str, database: str) -> "Store":
        """Connect to MongoDB (lazy; the driver connects on first use)."""
        client = AsyncMongoClient(url, serverSelectionTimeoutMS=3000, tz_aware=True)
        db = client[database]

        async def ping() -> bool:
            await client.admin.command("ping")
            return True

        store = cls(
            MongoCollection(db["agreements"]),
            MongoCollection(db["reports"]),
            MongoCollection(db["processed_events"]),
            ping,
        )
        store.client = client
        return store

    @classmethod
    def in_memory(cls) -> "Store":
        """Store for tests."""
        return cls(InMemoryCollection(), InMemoryCollection(), InMemoryCollection())

    async def ping(self) -> bool:
        """Readiness probe."""
        return await self._ping() if self._ping else True

    async def close(self) -> None:
        """Close the MongoDB client, if any."""
        if self.client is not None:
            await self.client.close()


class MongoIdempotencyStore:
    """``eh_events`` idempotency protocol on the ``processed_events`` collection."""

    def __init__(self, collection: DocumentCollection) -> None:
        self.collection = collection

    async def seen(self, event_id: str) -> bool:
        """``True`` if already processed."""
        return await self.collection.get(event_id) is not None

    async def mark(self, event_id: str, event_type: str) -> None:
        """Record as processed (duplicates ignored)."""
        from datetime import UTC, datetime

        try:
            await self.collection.insert(
                {"_id": event_id, "event_type": event_type, "created_at": datetime.now(UTC)}
            )
        except DuplicateKeyError:
            return


class FileStorage:
    """Binary files on the ``document-files`` volume."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base = Path(base_dir)

    def save(self, relative: str, content: bytes) -> str:
        """Write ``content`` and return the relative path."""
        target = self._resolve(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return relative

    def read(self, relative: str) -> bytes:
        """Read a stored file."""
        return self._resolve(relative).read_bytes()

    def _resolve(self, relative: str) -> Path:
        target = (self.base / relative).resolve()
        if self.base.resolve() not in target.parents:
            raise ValueError("path escapes the storage directory")
        return target
