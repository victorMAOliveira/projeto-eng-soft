"""FastAPI application factory of the internship-service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from eh_auth import JWTAuth, install_auth
from eh_db import Database
from eh_events import EventPublisher, Publisher
from eh_observability import configure_logging, setup_observability
from internship_service import SERVICE_NAME, __version__
from internship_service.api import router
from internship_service.config import Settings


def create_app(
    settings: Settings | None = None,
    *,
    db: Database | None = None,
    publisher: Publisher | None = None,
) -> FastAPI:
    """Build the app (``uvicorn --factory internship_service.main:create_app``)."""
    settings = settings or Settings()
    configure_logging(SERVICE_NAME, settings.log_level)
    db = db or Database(settings.database_url)
    publisher = publisher or EventPublisher(settings.rabbitmq_url, service_name=SERVICE_NAME)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await publisher.connect()
        yield
        await publisher.close()
        await db.dispose()

    app = FastAPI(
        title="EstágioHub — internship-service",
        version=__version__,
        description="Publicação, busca e encerramento de vagas de estágio.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = db
    app.state.publisher = publisher
    install_auth(app, JWTAuth(settings.jwt_secret))
    setup_observability(
        app,
        SERVICE_NAME,
        __version__,
        checks={"database": db.ping, "broker": publisher.is_connected},
        database="PostgreSQL",
    )
    app.include_router(router)
    return app
