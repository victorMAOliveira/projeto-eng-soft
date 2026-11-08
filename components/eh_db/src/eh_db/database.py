"""Async engine and session management."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Database:
    """Owns one service's async engine and session factory.

    Each microservice creates exactly one ``Database`` pointing at **its own**
    database (Database per Service pattern).

    Args:
        url: SQLAlchemy async URL, e.g. ``postgresql+asyncpg://...`` or
            ``sqlite+aiosqlite:///:memory:`` in tests.
        echo: Log SQL statements.
    """

    def __init__(self, url: str, *, echo: bool = False) -> None:
        self.url = url
        options: dict[str, object] = {"echo": echo}
        if not url.startswith("sqlite"):
            options.update(pool_size=5, max_overflow=5, pool_pre_ping=True)
        self.engine: AsyncEngine = create_async_engine(url, **options)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield a session that commits on success and rolls back on error."""
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except BaseException:
                await session.rollback()
                raise

    async def get_session(self) -> AsyncIterator[AsyncSession]:
        """FastAPI dependency: ``Depends(db.get_session)``."""
        async with self.session() as session:
            yield session

    async def ping(self) -> bool:
        """Readiness probe: run ``SELECT 1``."""
        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True

    async def create_all(self, metadata: MetaData) -> None:
        """Create every table of ``metadata`` (tests only; services use Alembic)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(metadata.create_all)

    async def dispose(self) -> None:
        """Close all pooled connections."""
        await self.engine.dispose()
