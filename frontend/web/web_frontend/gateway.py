"""Client for the API Gateway — the only backend the frontend talks to."""

from dataclasses import dataclass
from typing import Any

import httpx

from eh_http import CircuitOpenError, ResilientClient, UpstreamUnavailableError
from eh_observability import CORRELATION_HEADER, get_correlation_id


@dataclass(slots=True)
class ApiResult:
    """Outcome of a gateway call, including which microservice served it."""

    status: int
    data: Any = None
    served_by: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        """``True`` for 2xx responses."""
        return 200 <= self.status < 300

    @property
    def unavailable(self) -> bool:
        """``True`` when the gateway reported the upstream (or itself) as unavailable."""
        return self.status == 503

    @property
    def unavailable_service(self) -> str | None:
        """Name of the unavailable microservice, when reported by the gateway."""
        if self.unavailable and isinstance(self.data, dict):
            return self.data.get("service")
        return None


def error_message(data: Any, status: int) -> str:
    """Turn a FastAPI error body (string or validation list) into a readable message."""
    detail = data.get("detail") if isinstance(data, dict) else None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        parts = []
        for item in detail:
            field = ".".join(str(p) for p in item.get("loc", [])[1:]) or "dados"
            parts.append(f"{field}: {item.get('msg', 'inválido')}")
        return "; ".join(parts)
    return f"Erro {status}"


class GatewayClient:
    """Thin wrapper over :class:`eh_http.ResilientClient` returning :class:`ApiResult`."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._http = ResilientClient(
            base_url,
            name="api-gateway",
            timeout=timeout,
            retries=1,
            header_provider=lambda: {CORRELATION_HEADER: get_correlation_id()},
            transport=transport,
        )

    async def raw(
        self, method: str, path: str, *, token: str | None = None, **kwargs: Any
    ) -> httpx.Response | None:
        """Send a request and return the raw response (``None`` if unreachable)."""
        headers = dict(kwargs.pop("headers", None) or {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            return await self._http.request(method, path, headers=headers, **kwargs)
        except (CircuitOpenError, UpstreamUnavailableError):
            return None

    async def request(
        self, method: str, path: str, *, token: str | None = None, **kwargs: Any
    ) -> ApiResult:
        """Send a request and decode the JSON body into an :class:`ApiResult`."""
        response = await self.raw(method, path, token=token, **kwargs)
        if response is None:
            return ApiResult(
                503,
                {"service": "api-gateway"},
                error="API Gateway indisponível",
            )
        try:
            data = response.json()
        except ValueError:
            data = None
        result = ApiResult(response.status_code, data, response.headers.get("x-served-by"))
        if not result.ok:
            result.error = error_message(data, response.status_code)
        return result

    async def get(self, path: str, *, token: str | None = None, **kwargs: Any) -> ApiResult:
        """GET shortcut."""
        return await self.request("GET", path, token=token, **kwargs)

    async def post(self, path: str, *, token: str | None = None, **kwargs: Any) -> ApiResult:
        """POST shortcut."""
        return await self.request("POST", path, token=token, **kwargs)

    async def put(self, path: str, *, token: str | None = None, **kwargs: Any) -> ApiResult:
        """PUT shortcut."""
        return await self.request("PUT", path, token=token, **kwargs)

    async def aclose(self) -> None:
        """Close connections."""
        await self._http.aclose()
