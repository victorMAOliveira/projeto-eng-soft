"""Generic repository with the CRUD operations every aggregate needs."""

from collections.abc import Sequence
from typing import Any, ClassVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement


class BaseRepository[ModelT]:
    """CRUD repository bound to one mapped class.

    Subclasses only declare ``model`` and add domain specific queries::

        class InternshipRepository(BaseRepository[Internship]):
            model = Internship
    """

    model: ClassVar[type[Any]]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _where(self, filters: dict[str, Any]) -> list[ColumnElement[bool]]:
        return [getattr(self.model, key) == value for key, value in filters.items()]

    async def get(self, entity_id: Any) -> ModelT | None:
        """Return the entity with primary key ``entity_id`` or ``None``."""
        return await self.session.get(self.model, entity_id)

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        order_by: Sequence[Any] | None = None,
        **filters: Any,
    ) -> list[ModelT]:
        """Return entities matching equality ``filters`` with pagination."""
        stmt = select(self.model).where(*self._where(filters)).offset(offset).limit(limit)
        if order_by:
            stmt = stmt.order_by(*order_by)
        return list((await self.session.scalars(stmt)).all())

    async def count(self, **filters: Any) -> int:
        """Count entities matching equality ``filters``."""
        stmt = select(func.count()).select_from(self.model).where(*self._where(filters))
        return int(await self.session.scalar(stmt) or 0)

    async def add(self, entity: ModelT) -> ModelT:
        """Persist ``entity`` and flush so generated keys become available."""
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def delete(self, entity: ModelT) -> None:
        """Delete ``entity``."""
        await self.session.delete(entity)
        await self.session.flush()
