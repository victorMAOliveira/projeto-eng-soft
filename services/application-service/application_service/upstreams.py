"""Synchronous (REST) calls to other services through :mod:`eh_http`."""

from typing import Any

import httpx
from fastapi import HTTPException, status

from eh_http import CircuitOpenError, ResilientClient, UpstreamUnavailableError
from eh_observability import CORRELATION_HEADER, get_correlation_id


def _correlation() -> dict[str, str | None]:
    return {CORRELATION_HEADER: get_correlation_id()}


class Upstreams:
    """Resilient clients for internship-service and user-service.

    Calls forward the caller's bearer token, so the upstream applies its own
    authorisation rules (defence in depth).
    """

    def __init__(
        self,
        internship_url: str,
        user_url: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        options = {"timeout": 5.0, "retries": 2, "header_provider": _correlation}
        self.internships = ResilientClient(
            internship_url, name="internship-service", transport=transport, **options
        )
        self.users = ResilientClient(user_url, name="user-service", transport=transport, **options)

    async def _get(self, client: ResilientClient, path: str, token: str) -> dict[str, Any] | None:
        try:
            response = await client.get(path, headers={"Authorization": f"Bearer {token}"})
        except (CircuitOpenError, UpstreamUnavailableError) as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                f"Serviço {client.name} indisponível; tente novamente.",
            ) from exc
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, f"{client.name} respondeu {response.status_code}"
            )
        return response.json()

    async def internship(self, internship_id: int, token: str) -> dict[str, Any] | None:
        """``GET /internships/{id}`` on internship-service."""
        return await self._get(self.internships, f"/internships/{internship_id}", token)

    async def student_profile(self, student_id: int, token: str) -> dict[str, Any] | None:
        """``GET /profiles/students/{id}`` on user-service."""
        return await self._get(self.users, f"/profiles/students/{student_id}", token)

    async def aclose(self) -> None:
        """Close both connection pools."""
        await self.internships.aclose()
        await self.users.aclose()
