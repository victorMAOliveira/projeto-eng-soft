"""Pure-ASGI middleware for correlation ids, ``X-Served-By`` and access logs."""

import logging
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from eh_observability.context import (
    CORRELATION_HEADER,
    SERVED_BY_HEADER,
    reset_correlation_id,
    set_correlation_id,
)

_QUIET_PATHS = frozenset({"/health", "/ready", "/version", "/favicon.ico"})


class ObservabilityMiddleware:
    """Attach a correlation id to every request and identify the serving service.

    * Reuses the incoming ``X-Correlation-ID`` header or generates a new id.
    * Exposes the id through :func:`eh_observability.get_correlation_id`.
    * Adds ``X-Correlation-ID`` and ``X-Served-By`` to the response. An existing
      ``X-Served-By`` (e.g. proxied by the gateway) is preserved.
    * Emits one structured access-log line per request (health probes excluded).
    """

    def __init__(self, app: ASGIApp, service_name: str, logger: logging.Logger | None = None):
        self.app = app
        self.service_name = service_name
        self.logger = logger or logging.getLogger(f"{service_name}.access")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process one ASGI call."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope.get("headers") or [])
        correlation_id = (
            incoming.get(b"x-correlation-id", b"").decode("latin-1") or uuid.uuid4().hex
        )
        token = set_correlation_id(correlation_id)
        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers[CORRELATION_HEADER] = correlation_id
                if SERVED_BY_HEADER.lower() not in headers:
                    headers[SERVED_BY_HEADER] = self.service_name
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            path = scope.get("path", "")
            if path not in _QUIET_PATHS:
                self.logger.info(
                    "%s %s -> %s",
                    scope.get("method"),
                    path,
                    status_code,
                    extra={
                        "http_method": scope.get("method"),
                        "path": path,
                        "status": status_code,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    },
                )
            reset_correlation_id(token)
