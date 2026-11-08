"""Reverse proxy: authenticate, authorise and forward a request to its upstream."""

import logging
import time

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from api_gateway.routes import Route, allowed_roles, upstream_path
from eh_auth import JWTAuth, Principal, Role, TokenError
from eh_http import CircuitOpenError, ResilientClient, UpstreamUnavailableError

logger = logging.getLogger("api-gateway.proxy")

# Hop-by-hop headers (RFC 9110 §7.6.1) and headers httpx recomputes.
_DROP_REQUEST = {
    "host",
    "content-length",
    "connection",
    "keep-alive",
    "transfer-encoding",
    "upgrade",
    "x-correlation-id",  # re-added by the client's header provider from the request context
}
_DROP_RESPONSE = {
    "content-length",
    "content-encoding",
    "transfer-encoding",
    "connection",
    "keep-alive",
}


def _error(status: int, detail: str, **extra: object) -> JSONResponse:
    return JSONResponse({"detail": detail, **extra}, status_code=status)


def authenticate(request: Request, auth: JWTAuth) -> Principal | JSONResponse:
    """Validate the bearer token; return the principal or a 401 response."""
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return _error(401, "Autenticação necessária")
    try:
        return auth.decode(token)
    except TokenError:
        return _error(401, "Token inválido ou expirado")


def authorise(request: Request, principal: Principal) -> JSONResponse | None:
    """Apply the role policy table; return a 403 response when forbidden."""
    roles = allowed_roles(request.method, request.url.path)
    if roles is None or principal.role in roles or principal.role is Role.SERVICE:
        return None
    return _error(403, "Seu papel não tem permissão para esta operação", role=principal.role.value)


async def forward(
    request: Request,
    route: Route,
    client: ResilientClient,
    principal: Principal | None,
) -> Response:
    """Forward ``request`` to ``route.service`` and relay its response.

    Upstream failures become ``503`` responses naming the unavailable service,
    which lets the frontend degrade gracefully instead of failing the page.
    """
    headers = {k: v for k, v in request.headers.items() if k.lower() not in _DROP_REQUEST}
    headers["x-forwarded-for"] = request.client.host if request.client else ""
    if principal is not None:
        headers["x-user-id"] = str(principal.id)
        headers["x-user-role"] = principal.role.value

    started = time.perf_counter()
    try:
        upstream = await client.request(
            request.method,
            upstream_path(request.url.path),
            params=list(request.query_params.multi_items()),
            content=await request.body(),
            headers=headers,
        )
    except CircuitOpenError:
        return _error(
            503,
            f"Serviço {route.service} temporariamente indisponível",
            service=route.service,
            reason="circuit_open",
        )
    except UpstreamUnavailableError as exc:
        logger.warning("upstream unavailable", extra={"service": route.service, "cause": str(exc)})
        return _error(
            503,
            f"Serviço {route.service} indisponível",
            service=route.service,
            reason="unavailable",
        )

    response_headers = {
        k: v for k, v in upstream.headers.items() if k.lower() not in _DROP_RESPONSE
    }
    response_headers.setdefault("x-served-by", route.service)
    response_headers["x-upstream-latency-ms"] = f"{(time.perf_counter() - started) * 1000:.1f}"
    return Response(
        content=upstream.content, status_code=upstream.status_code, headers=response_headers
    )
