"""Alembic environment: delegates to the shared eh_db helper."""

from agent_service.models import Base

from eh_db import run_migrations

run_migrations(Base.metadata)
