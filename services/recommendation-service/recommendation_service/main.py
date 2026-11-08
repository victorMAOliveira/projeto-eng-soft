"""FastAPI application factory of the recommendation-service."""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from pydantic_settings import BaseSettings, SettingsConfigDict

from eh_auth import JWTAuth, install_auth
from eh_db import Database, SqlIdempotencyStore
from eh_events import EventConsumer
from eh_http import ResilientClient
from eh_observability import (
    CORRELATION_HEADER,
    configure_logging,
    get_correlation_id,
    setup_observability,
)
from recommendation_service import SERVICE_NAME, __version__
from recommendation_service.api import router
from recommendation_service.projection import ROUTING_KEYS, Projection
from recommendation_service.rebuild import Rebuilder
from recommendation_service.recommender import Weights


class Settings(BaseSettings):
    """Values read from environment variables (weights documented in the report)."""

    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    rabbitmq_url: str
    jwt_secret: str
    rec_weight_content: float = 0.5
    rec_weight_attributes: float = 0.35
    rec_weight_preference: float = 0.15
    user_service_url: str = "http://user-service:8000"
    internship_service_url: str = "http://internship-service:8000"
    application_service_url: str = "http://application-service:8000"
    log_level: str = "INFO"


def create_app(
    settings: Settings | None = None,
    *,
    db: Database | None = None,
    upstream_transport: httpx.AsyncBaseTransport | None = None,
    start_consumer: bool = True,
) -> FastAPI:
    """Build the app (``uvicorn --factory recommendation_service.main:create_app``)."""
    settings = settings or Settings()
    configure_logging(SERVICE_NAME, settings.log_level)
    db = db or Database(settings.database_url)
    auth = JWTAuth(settings.jwt_secret)
    consumer = EventConsumer(
        settings.rabbitmq_url,
        queue_name=f"{SERVICE_NAME}.events",
        routing_keys=ROUTING_KEYS,
        handler=Projection(db),
        idempotency=SqlIdempotencyStore(db),
    )

    def client(url: str, name: str) -> ResilientClient:
        return ResilientClient(
            url,
            name=name,
            timeout=10.0,
            header_provider=lambda: {CORRELATION_HEADER: get_correlation_id()},
            transport=upstream_transport,
        )

    clients = [
        client(settings.user_service_url, "user-service"),
        client(settings.internship_service_url, "internship-service"),
        client(settings.application_service_url, "application-service"),
    ]

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if start_consumer:
            await consumer.start()
        yield
        if start_consumer:
            await consumer.stop()
        for c in clients:
            await c.aclose()
        await db.dispose()

    async def broker_ready() -> bool:
        return await consumer.is_connected() if start_consumer else True

    app = FastAPI(
        title="EstágioHub — recommendation-service",
        version=__version__,
        description=(
            "Recomendação híbrida e explicável (filtros + TF-IDF/cosseno + Jaccard + preferências) "
            "sobre um modelo de leitura alimentado por eventos."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = db
    app.state.weights = Weights(
        settings.rec_weight_content, settings.rec_weight_attributes, settings.rec_weight_preference
    )
    app.state.projection = Projection(db)
    app.state.rebuilder = Rebuilder(db, auth, *clients)
    install_auth(app, auth)
    setup_observability(
        app,
        SERVICE_NAME,
        __version__,
        checks={"database": db.ping, "broker": broker_ready},
        database="PostgreSQL (read model)",
    )
    app.include_router(router)
    return app
