"""Resilient async HTTP client used for every synchronous call between services."""

import asyncio
import logging
from collections.abc import Callable, Mapping
from typing import Any

import httpx

from eh_http.breaker import CircuitBreaker

logger = logging.getLogger(__name__)

IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})
RETRYABLE_STATUS = frozenset({502, 503, 504})


class CircuitOpenError(RuntimeError):
    """Raised without touching the network because the upstream circuit is open."""

    def __init__(self, upstream: str) -> None:
        super().__init__(f"circuit open for {upstream}")
        self.upstream = upstream


class UpstreamUnavailableError(RuntimeError):
    """Raised when every attempt to reach the upstream failed at transport level."""

    def __init__(self, upstream: str, cause: Exception) -> None:
        super().__init__(f"{upstream} unavailable: {type(cause).__name__}")
        self.upstream = upstream
        self.cause = cause


class ResilientClient:
    """``httpx.AsyncClient`` with timeout, retry + exponential backoff and circuit breaker.

    Retry policy:

    * idempotent methods are retried on transport errors and on 502/503/504;
    * non-idempotent methods (POST/PATCH) are retried only when the connection
      could not be established, so a request is never applied twice.

    Args:
        base_url: Upstream root URL, e.g. ``http://user-service:8000``.
        name: Logical upstream name used in errors and logs.
        timeout: Total timeout (seconds) for each attempt.
        retries: Extra attempts after the first one.
        backoff: Base delay; attempt *n* waits ``backoff * 2**n`` seconds.
        breaker: Circuit breaker shared by all calls to this upstream.
        header_provider: Callable returning headers added to every request
            (used to propagate the correlation id without a hard dependency).
        transport: Optional custom transport (tests use ``httpx.MockTransport``).
    """

    def __init__(
        self,
        base_url: str,
        *,
        name: str,
        timeout: float = 5.0,
        retries: int = 2,
        backoff: float = 0.2,
        breaker: CircuitBreaker | None = None,
        header_provider: Callable[[], Mapping[str, str | None]] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.name = name
        self.retries = retries
        self.backoff = backoff
        self.breaker = breaker or CircuitBreaker()
        self._header_provider = header_provider
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(timeout), transport=transport
        )

    def _extra_headers(self) -> dict[str, str]:
        if self._header_provider is None:
            return {}
        return {k: v for k, v in self._header_provider().items() if v}

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send a request applying the breaker and retry policy.

        Raises:
            CircuitOpenError: the breaker is open; nothing was sent.
            UpstreamUnavailableError: all attempts failed at transport level.
        """
        method = method.upper()
        if not self.breaker.allow_request():
            raise CircuitOpenError(self.name)
        headers = httpx.Headers(self._extra_headers())
        headers.update(kwargs.pop("headers", None) or {})  # case-insensitive override
        idempotent = method in IDEMPOTENT_METHODS
        last_error: Exception | None = None

        for attempt in range(self.retries + 1):
            if attempt:
                await asyncio.sleep(self.backoff * 2 ** (attempt - 1))
            try:
                response = await self._client.request(method, url, headers=headers, **kwargs)
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                last_error = exc  # nothing reached the upstream: always safe to retry
                continue
            except httpx.TransportError as exc:
                last_error = exc
                if idempotent:
                    continue
                break
            if response.status_code in RETRYABLE_STATUS and idempotent and attempt < self.retries:
                logger.warning("retrying %s %s after %s", method, url, response.status_code)
                continue
            if response.status_code >= 500:
                self.breaker.record_failure()
            else:
                self.breaker.record_success()
            return response

        self.breaker.record_failure()
        assert last_error is not None
        raise UpstreamUnavailableError(self.name, last_error)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Shortcut for ``request("GET", ...)``."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """Shortcut for ``request("POST", ...)``."""
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> httpx.Response:
        """Shortcut for ``request("PUT", ...)``."""
        return await self.request("PUT", url, **kwargs)

    async def aclose(self) -> None:
        """Close the underlying connection pool."""
        await self._client.aclose()
