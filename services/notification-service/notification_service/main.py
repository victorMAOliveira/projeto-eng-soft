"""FastAPI application factory of the notification-service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic_settings import BaseSettings, SettingsConfigDict
from redis.asyncio import Redis

from eh_auth import JWTAuth, install_auth
from eh_events import Event, EventConsumer
from eh_observability import configure_logging, setup_observability
from notification_service import SERVICE_NAME, __version__
from notification_service.api import router
from notification_service.inbox import Inbox
from notification_service.rules import notices_for


class Settings(BaseSettings):
    """Values read from environment variables."""

    model_config = SettingsConfigDict(extra="ignore")

    redis_url: str
    rabbitmq_url: str
    jwt_secret: str
    log_level: str = "INFO"


class NotificationHandler:
    """Consumes **every** event (``#`` binding) and fills the inboxes."""

    def __init__(self, inbox: Inbox) -> None:
        self.inbox = inbox

    async def __call__(self, event: Event) -> None:
        """Deliver the notices produced by :func:`notices_for`."""
        for notice in notices_for(event):
            await self.inbox.deliver(notice, event.event_type.value)


def create_app(
    settings: Settings | None = None,
    *,
    redis: Redis | None = None,
    start_consumer: bool = True,
) -> FastAPI:
    """Build the app (``uvicorn --factory notification_service.main:create_app``)."""
    settings = settings or Settings()
    configure_logging(SERVICE_NAME, settings.log_level)
    redis = redis or Redis.from_url(settings.redis_url, decode_responses=True)
    inbox = Inbox(redis)
    consumer = EventConsumer(
        settings.rabbitmq_url,
        queue_name=f"{SERVICE_NAME}.events",
        routing_keys=["#"],
        handler=NotificationHandler(inbox),
        idempotency=inbox,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if start_consumer:
            await consumer.start()
        yield
        if start_consumer:
            await consumer.stop()
        await redis.aclose()

    async def redis_ready() -> bool:
        return bool(await redis.ping())

    async def broker_ready() -> bool:
        return await consumer.is_connected() if start_consumer else True

    app = FastAPI(
        title="EstágioHub — notification-service",
        version=__version__,
        description="Consome todos os eventos e mantém a caixa de notificações de cada usuário.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.inbox = inbox
    app.state.handler = NotificationHandler(inbox)
    install_auth(app, JWTAuth(settings.jwt_secret))
    setup_observability(
        app,
        SERVICE_NAME,
        __version__,
        checks={"database": redis_ready, "broker": broker_ready},
        database="Redis",
    )
    app.include_router(router)
    return app
