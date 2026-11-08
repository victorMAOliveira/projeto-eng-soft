"""FastAPI application factory of the agent-service (with the follow-up scheduler)."""

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from pydantic_settings import BaseSettings, SettingsConfigDict

from agent_service import SERVICE_NAME, __version__
from agent_service.api import router
from agent_service.runner import AgentRunner, AnthropicLlm, LlmClient
from agent_service.tools import Services, ToolContext
from eh_auth import JWTAuth, Principal, Role, install_auth
from eh_db import Database
from eh_events import EventPublisher, Publisher
from eh_observability import configure_logging, setup_observability

logger = logging.getLogger("agent-service")


class Settings(BaseSettings):
    """Values read from environment variables."""

    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    rabbitmq_url: str
    jwt_secret: str
    anthropic_api_key: str | None = None
    llm_model: str = "claude-haiku-5-5"
    agent_max_steps: int = 6
    agent_timeout_seconds: float = 45.0
    followup_interval_minutes: int = 60
    user_service_url: str = "http://user-service:8000"
    internship_service_url: str = "http://internship-service:8000"
    application_service_url: str = "http://application-service:8000"
    document_service_url: str = "http://document-service:8000"
    notification_service_url: str = "http://notification-service:8000"
    recommendation_service_url: str = "http://recommendation-service:8000"
    log_level: str = "INFO"


def create_app(
    settings: Settings | None = None,
    *,
    db: Database | None = None,
    publisher: Publisher | None = None,
    llm: LlmClient | None = None,
    upstream_transport: httpx.AsyncBaseTransport | None = None,
    start_scheduler: bool = True,
) -> FastAPI:
    """Build the app (``uvicorn --factory agent_service.main:create_app``).

    Without ``ANTHROPIC_API_KEY`` (and no injected ``llm``) the agents run in
    deterministic rules mode with the same API.
    """
    settings = settings or Settings()
    configure_logging(SERVICE_NAME, settings.log_level)
    db = db or Database(settings.database_url)
    publisher = publisher or EventPublisher(settings.rabbitmq_url, service_name=SERVICE_NAME)
    if llm is None and settings.anthropic_api_key:
        llm = AnthropicLlm(settings.anthropic_api_key)
    auth = JWTAuth(settings.jwt_secret)
    services = Services(
        {
            "user-service": settings.user_service_url,
            "internship-service": settings.internship_service_url,
            "application-service": settings.application_service_url,
            "document-service": settings.document_service_url,
            "notification-service": settings.notification_service_url,
            "recommendation-service": settings.recommendation_service_url,
        },
        transport=upstream_transport,
    )
    runner = AgentRunner(
        llm=llm,
        model=settings.llm_model,
        max_steps=settings.agent_max_steps,
        timeout_seconds=settings.agent_timeout_seconds,
    )
    scheduler = AsyncIOScheduler(timezone="UTC")

    async def scheduled_follow_up() -> None:
        """Periodic run of the follow-up agent as an internal service."""
        principal = Principal(id=0, role=Role.SERVICE, name="agendador")
        ctx = ToolContext(
            principal, auth.create_service_token(SERVICE_NAME), auth, services, db, publisher
        )
        try:
            await runner.run("follow_up", ctx, {"trigger": "scheduled"})
        except Exception:  # never let the scheduler die
            logger.exception("scheduled follow-up failed")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await publisher.connect()
        if start_scheduler and settings.followup_interval_minutes > 0:
            app.state.scheduler_job = scheduler.add_job(
                scheduled_follow_up,
                "interval",
                minutes=settings.followup_interval_minutes,
                next_run_time=datetime.now(UTC) + timedelta(seconds=60),
                id="follow-up",
            )
            scheduler.start()
        yield
        if scheduler.running:
            scheduler.shutdown(wait=False)
        await services.aclose()
        await publisher.close()
        await db.dispose()

    app = FastAPI(
        title="EstágioHub — agent-service",
        version=__version__,
        description="Agentes de IA (Claude, tool use) com fallback determinístico em modo regras.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = db
    app.state.publisher = publisher
    app.state.auth = auth
    app.state.services = services
    app.state.runner = runner
    app.state.scheduler_job = None
    app.state.scheduled_follow_up = scheduled_follow_up
    install_auth(app, auth)
    setup_observability(
        app,
        SERVICE_NAME,
        __version__,
        checks={"database": db.ping, "broker": publisher.is_connected},
        database="PostgreSQL",
    )
    app.include_router(router)
    return app
