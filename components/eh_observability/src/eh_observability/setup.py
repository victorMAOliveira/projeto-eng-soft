"""One-call wiring of logging, middleware and health routes into a FastAPI app."""

from collections.abc import Mapping

from fastapi import FastAPI

from eh_observability.health import Check, create_health_router
from eh_observability.middleware import ObservabilityMiddleware


def setup_observability(
    app: FastAPI,
    service_name: str,
    version: str,
    *,
    checks: Mapping[str, Check] | None = None,
    database: str | None = None,
) -> None:
    """Install :class:`ObservabilityMiddleware` and the health router on ``app``."""
    app.add_middleware(ObservabilityMiddleware, service_name=service_name)
    app.include_router(
        create_health_router(service_name, version, checks=checks, database=database)
    )
