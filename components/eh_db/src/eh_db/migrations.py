"""Alembic helpers: every service's ``alembic/env.py`` is a two-line call to this module."""

import asyncio
import os

from alembic import context
from sqlalchemy import MetaData
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool


def _configure_and_run(connection: Connection | None, url: str, metadata: MetaData) -> None:
    if connection is None:
        context.configure(url=url, target_metadata=metadata, literal_binds=True)
    else:
        context.configure(connection=connection, target_metadata=metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def _run_online(url: str, metadata: MetaData) -> None:
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(lambda sync_conn: _configure_and_run(sync_conn, url, metadata))
    await engine.dispose()


def run_migrations(target_metadata: MetaData, url: str | None = None) -> None:
    """Run Alembic migrations offline (SQL script) or online (async engine).

    The URL comes from ``url``, the ``DATABASE_URL`` environment variable or the
    ``sqlalchemy.url`` option of ``alembic.ini``, in this order.

    Usage in ``alembic/env.py``::

        from eh_db import run_migrations
        from user_service.models import Base
        run_migrations(Base.metadata)
    """
    resolved = url or os.getenv("DATABASE_URL") or context.config.get_main_option("sqlalchemy.url")
    if not resolved:
        raise RuntimeError("DATABASE_URL is not configured")
    if context.is_offline_mode():
        _configure_and_run(None, resolved, target_metadata)
    else:
        asyncio.run(_run_online(resolved, target_metadata))
