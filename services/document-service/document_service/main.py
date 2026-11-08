"""FastAPI application factory of the document-service."""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from pydantic_settings import BaseSettings, SettingsConfigDict

from document_service import SERVICE_NAME, __version__
from document_service.agreements import AgreementGenerator
from document_service.api import router
from document_service.storage import FileStorage, MongoIdempotencyStore, Store
from eh_auth import JWTAuth, install_auth
from eh_events import EventConsumer, EventPublisher, EventType, Publisher
from eh_http import ResilientClient
from eh_observability import (
    CORRELATION_HEADER,
    configure_logging,
    get_correlation_id,
    setup_observability,
)


class Settings(BaseSettings):
    """Values read from environment variables."""

    model_config = SettingsConfigDict(extra="ignore")

    mongo_url: str
    mongo_database: str = "documents"
    files_dir: str = "/data/files"
    rabbitmq_url: str
    jwt_secret: str
    application_service_url: str = "http://application-service:8000"
    log_level: str = "INFO"


def create_app(
    settings: Settings | None = None,
    *,
    store: Store | None = None,
    publisher: Publisher | None = None,
    upstream_transport: httpx.AsyncBaseTransport | None = None,
    start_consumer: bool = True,
) -> FastAPI:
    """Build the app (``uvicorn --factory document_service.main:create_app``)."""
    settings = settings or Settings()
    configure_logging(SERVICE_NAME, settings.log_level)
    store = store or Store.mongo(settings.mongo_url, settings.mongo_database)
    publisher = publisher or EventPublisher(settings.rabbitmq_url, service_name=SERVICE_NAME)
    files = FileStorage(settings.files_dir)
    applications = ResilientClient(
        settings.application_service_url,
        name="application-service",
        timeout=5.0,
        header_provider=lambda: {CORRELATION_HEADER: get_correlation_id()},
        transport=upstream_transport,
    )
    generator = AgreementGenerator(store, files, publisher)
    consumer = EventConsumer(
        settings.rabbitmq_url,
        queue_name=f"{SERVICE_NAME}.events",
        routing_keys=[EventType.APPLICATION_STATUS_CHANGED.value],
        handler=generator,
        idempotency=MongoIdempotencyStore(store.processed),
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
        await applications.aclose()
        await store.close()

    async def broker_ready() -> bool:
        consuming = await consumer.is_connected() if start_consumer else True
        return consuming and await publisher.is_connected()

    app = FastAPI(
        title="EstágioHub — document-service",
        version=__version__,
        description="Geração do TCE em PDF, aprovação pela coordenação e relatórios com versões.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.store = store
    app.state.files = files
    app.state.publisher = publisher
    app.state.applications = applications
    app.state.generator = generator
    install_auth(app, JWTAuth(settings.jwt_secret))
    setup_observability(
        app,
        SERVICE_NAME,
        __version__,
        checks={"database": store.ping, "broker": broker_ready},
        database="MongoDB + volume",
    )
    app.include_router(router)
    return app
