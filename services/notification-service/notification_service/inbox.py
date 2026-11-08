"""Redis-backed inboxes.

Keys:

* ``inbox:user:<id>`` / ``inbox:role:<role>`` — lists of JSON notifications
  (newest first, capped at :data:`MAX_ITEMS`);
* ``read:<user_id>`` — set of notification ids read by the user (role
  inboxes are shared, so read state is per user);
* ``processed:<event_id>`` — idempotency marker with a TTL.
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis

from notification_service.rules import Notice

MAX_ITEMS = 200
PROCESSED_TTL_SECONDS = 7 * 24 * 3600


class Inbox:
    """Read and write notifications in Redis."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def deliver(self, notice: Notice, event_type: str | None = None) -> dict[str, Any]:
        """Push ``notice`` on the recipient's inbox and return the stored item."""
        item = {
            "id": uuid.uuid4().hex,
            "recipient": notice.recipient,
            "title": notice.title,
            "message": notice.message,
            "kind": notice.kind,
            "link": notice.link,
            "event_type": event_type,
            "created_at": datetime.now(UTC).isoformat(),
        }
        key = f"inbox:{notice.recipient}"
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.lpush(key, json.dumps(item, ensure_ascii=False))
            pipe.ltrim(key, 0, MAX_ITEMS - 1)
            await pipe.execute()
        return item

    async def list_for(self, user_id: int, role: str, limit: int = 50) -> list[dict[str, Any]]:
        """Merge personal and role inboxes, newest first, with the ``read`` flag."""
        personal = await self.redis.lrange(f"inbox:user:{user_id}", 0, MAX_ITEMS - 1)
        shared = await self.redis.lrange(f"inbox:role:{role}", 0, MAX_ITEMS - 1)
        read = await self.redis.smembers(f"read:{user_id}")
        items = [json.loads(raw) for raw in [*personal, *shared]]
        items.sort(key=lambda i: i["created_at"], reverse=True)
        for item in items:
            item["read"] = item["id"] in read
        return items[:limit]

    async def unread_count(self, user_id: int, role: str) -> int:
        """Number of unread notifications."""
        return sum(1 for i in await self.list_for(user_id, role, MAX_ITEMS) if not i["read"])

    async def mark_read(self, user_id: int, ids: list[str]) -> None:
        """Mark notifications as read for ``user_id``."""
        if ids:
            await self.redis.sadd(f"read:{user_id}", *ids)

    async def seen(self, event_id: str) -> bool:
        """Idempotency: ``True`` if the event was processed."""
        return bool(await self.redis.exists(f"processed:{event_id}"))

    async def mark(self, event_id: str, event_type: str) -> None:
        """Idempotency: remember the event for a week."""
        await self.redis.set(f"processed:{event_id}", event_type, ex=PROCESSED_TTL_SECONDS)
