"""FastAPI application factory of the web frontend."""

from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

import eh_ui
from eh_observability import configure_logging, setup_observability
from web_frontend import SERVICE_NAME, __version__
from web_frontend.config import Settings
from web_frontend.gateway import GatewayClient
from web_frontend.routes import (
    applications,
    auth,
    dashboard,
    documents,
    internships,
    notifications,
    profile,
)
from web_frontend.web import LoginRequired, login_redirect, render

STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    settings: Settings | None = None, *, transport: httpx.AsyncBaseTransport | None = None
) -> FastAPI:
    """Build the app (``uvicorn --factory web_frontend.main:create_app``).

    Args:
        settings: Configuration; read from the environment when omitted.
        transport: Optional httpx transport to fake the gateway in tests.
    """
    settings = settings or Settings()
    configure_logging(SERVICE_NAME, settings.log_level)
    client = GatewayClient(
        settings.gateway_url, timeout=settings.gateway_timeout, transport=transport
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await client.aclose()

    app = FastAPI(
        title="EstágioHub — web-frontend",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.gateway = client
    setup_observability(app, SERVICE_NAME, __version__)
    app.mount("/static/eh_ui", StaticFiles(directory=eh_ui.static_dir()), name="eh_ui_static")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.exception_handler(LoginRequired)
    async def _login_required(request: Request, exc: LoginRequired):
        return login_redirect(request, exc)

    @app.exception_handler(404)
    async def _not_found(request: Request, exc: Exception):
        return render(request, "not_found.html", status_code=404, message="Página não encontrada.")

    for module in (auth, dashboard, internships, applications, documents, notifications, profile):
        app.include_router(module.router)
    return app
