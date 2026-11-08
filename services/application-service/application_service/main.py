"""FastAPI application factory of the application-service."""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from pydantic_settings import BaseSettings, SettingsConfigDict

from application_service import SERVICE_NAME, __version__
from application_service.api import router
from application_service.events import ROUTING_KEYS, SagaHandlers
from application_service.upstreams import Upstreams
from eh_auth import JWTAuth, install_auth
from eh_db import Database, SqlIdempotencyStore
from eh_events import EventConsumer, EventPublisher, Publisher
from eh_observability import configure_logging, setup_observability


class Settings(BaseSettings):
    """Values read from environment variables."""

    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    rabbitmq_url: str
    jwt_secret: str
    user_service_url: str = "http://user-service:8000"
    internship_service_url: str = "http://internship-service:8000"
    log_level: str = "INFO"


def create_app(
    settings: Settings | None = None,
    *,
    db: Database | None = None,
    publisher: Publisher | None = None,
    upstream_transport: httpx.AsyncBaseTransport | None = None,
    start_consumer: bool = True,
) -> FastAPI:
    """Build the app (``uvicorn --factory application_service.main:create_app``)."""
    settings = settings or Settings()
    configure_logging(SERVICE_NAME, settings.log_level)
    db = db or Database(settings.database_url)
    publisher = publisher or EventPublisher(settings.rabbitmq_url, service_name=SERVICE_NAME)
    upstreams = Upstreams(
        settings.internship_service_url, settings.user_service_url, transport=upstream_transport
    )
    consumer = EventConsumer(
        settings.rabbitmq_url,
        queue_name=f"{SERVICE_NAME}.events",
        routing_keys=ROUTING_KEYS,
        handler=SagaHandlers(db, publisher),
        idempotency=SqlIdempotencyStore(db),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await publisher.connect()
        if start_consumer:
            await consumer.start()
        yield
        if start_consumer:
            await consumer.stop()
        await publisher.close()
        await upstreams.aclose()
        await db.dispose()

    async def broker_ready() -> bool:
        consuming = await consumer.is_connected() if start_consumer else True
        return consuming and await publisher.is_connected()

    app = FastAPI(
        title="EstágioHub — application-service",
        version=__version__,
        description="Candidaturas, máquina de estados do estágio e regras da Lei 11.788/2008.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = db
    app.state.publisher = publisher
    app.state.upstreams = upstreams
    install_auth(app, JWTAuth(settings.jwt_secret))
    setup_observability(
        app,
        SERVICE_NAME,
        __version__,
        checks={"database": db.ping, "broker": broker_ready},
        database="PostgreSQL",
    )
    app.include_router(router)
    return app
