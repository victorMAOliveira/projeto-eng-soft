"""FastAPI application of the API Gateway."""

import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api_gateway import SERVICE_NAME, __version__
from api_gateway.config import Settings
from api_gateway.health_aggregator import aggregate
from api_gateway.proxy import authenticate, authorise, forward
from api_gateway.routes import ROUTES, resolve_route
from eh_auth import JWTAuth
from eh_http import CircuitBreaker, ResilientClient
from eh_observability import (
    CORRELATION_HEADER,
    configure_logging,
    get_correlation_id,
    setup_observability,
)

PROXY_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]


def build_clients(
    settings: Settings, transport: httpx.AsyncBaseTransport | None = None
) -> dict[str, ResilientClient]:
    """One resilient client (and circuit breaker) per upstream service."""
    return {
        name: ResilientClient(
            url,
            name=name,
            timeout=settings.upstream_timeout,
            retries=settings.upstream_retries,
            breaker=CircuitBreaker(
                settings.breaker_failure_threshold, settings.breaker_recovery_seconds
            ),
            header_provider=lambda: {CORRELATION_HEADER: get_correlation_id()},
            transport=transport,
        )
        for name, url in settings.upstreams().items()
    }


def create_app(
    settings: Settings | None = None, *, transport: httpx.AsyncBaseTransport | None = None
) -> FastAPI:
    """Application factory (``uvicorn --factory api_gateway.main:create_app``).

    Args:
        settings: Configuration; read from the environment when omitted.
        transport: Optional httpx transport shared by upstream and probe
            clients (tests inject ``httpx.MockTransport``).
    """
    settings = settings or Settings()
    configure_logging(SERVICE_NAME, settings.log_level)
    auth = JWTAuth(settings.jwt_secret)
    clients = build_clients(settings, transport)
    probe_client = httpx.AsyncClient(timeout=settings.probe_timeout, transport=transport)
    started_at = time.time()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        for client in clients.values():
            await client.aclose()
        await probe_client.aclose()

    app = FastAPI(
        title="EstágioHub — API Gateway",
        version=__version__,
        description="Ponto único de entrada: roteamento, JWT/papéis, resiliência e saúde agregada.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=PROXY_METHODS,
        allow_headers=["Authorization", "Content-Type", CORRELATION_HEADER],
        expose_headers=["X-Served-By", CORRELATION_HEADER],
    )
    setup_observability(app, SERVICE_NAME, __version__)
    app.state.settings = settings
    app.state.clients = clients

    @app.get("/services", tags=["gateway"], summary="Aggregated health of all microservices")
    async def services() -> dict:
        """Probe every service (status, version, latency, database, uptime)."""
        return await aggregate(probe_client, settings.upstreams(), started_at)

    @app.get("/routes", tags=["gateway"], summary="Routing table")
    async def routes() -> list[dict]:
        """Expose the routing table (documentation and the status page)."""
        return [{"prefix": r.prefix, "service": r.service, "public": r.public} for r in ROUTES]

    @app.api_route("/api/{path:path}", methods=PROXY_METHODS, include_in_schema=False)
    async def proxy(request: Request, path: str) -> Response:
        """Authenticate, authorise and forward any ``/api/*`` request."""
        route = resolve_route(request.url.path)
        if route is None:
            return JSONResponse({"detail": "Rota não encontrada"}, status_code=404)
        principal = None
        if not route.public:
            principal = authenticate(request, auth)
            if isinstance(principal, JSONResponse):
                return principal
            if (denied := authorise(request, principal)) is not None:
                return denied
        return await forward(request, route, clients[route.service], principal)

    return app
