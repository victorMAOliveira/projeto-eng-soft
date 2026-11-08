"""Health Check API: ``/health`` (liveness), ``/ready`` (readiness) and ``/version``."""

import asyncio
import os
import platform
import time
from collections.abc import Awaitable, Callable, Mapping

from fastapi import APIRouter
from fastapi.responses import JSONResponse

Check = Callable[[], Awaitable[bool]]
"""A readiness probe: an async callable returning ``True`` when the dependency is usable."""


async def _run_check(check: Check, timeout: float) -> dict[str, object]:
    started = time.perf_counter()
    try:
        ok = bool(await asyncio.wait_for(check(), timeout=timeout))
        error = None if ok else "check returned false"
    except Exception as exc:  # noqa: BLE001 - any failure means "not ready"
        ok, error = False, f"{type(exc).__name__}: {exc}"[:200]
    return {
        "ok": ok,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "error": error,
    }


def create_health_router(
    service_name: str,
    version: str,
    *,
    checks: Mapping[str, Check] | None = None,
    database: str | None = None,
    check_timeout: float = 2.0,
) -> APIRouter:
    """Build the standard health router used by every EstágioHub service.

    Args:
        service_name: Name reported by the endpoints (e.g. ``user-service``).
        version: Semantic version of the running service.
        checks: Named readiness probes (e.g. ``{"database": db.ping}``).
        database: Human readable database technology (e.g. ``PostgreSQL``).
        check_timeout: Seconds allowed for each probe.
    """
    router = APIRouter(tags=["health"])
    started_at = time.time()
    probes = dict(checks or {})

    def _uptime() -> float:
        return round(time.time() - started_at, 1)

    @router.get("/health", summary="Liveness probe")
    async def health() -> dict[str, object]:
        """Report that the process is alive (does not touch dependencies)."""
        return {
            "status": "ok",
            "service": service_name,
            "version": version,
            "uptime_seconds": _uptime(),
        }

    @router.get("/ready", summary="Readiness probe")
    async def ready() -> JSONResponse:
        """Check every dependency; respond 503 if any of them is unavailable."""
        names = list(probes)
        results = await asyncio.gather(*(_run_check(probes[n], check_timeout) for n in names))
        report = dict(zip(names, results, strict=True))
        is_ready = all(r["ok"] for r in results)
        body = {
            "status": "ready" if is_ready else "not_ready",
            "service": service_name,
            "database": database,
            "uptime_seconds": _uptime(),
            "checks": report,
        }
        return JSONResponse(body, status_code=200 if is_ready else 503)

    @router.get("/version", summary="Build information")
    async def version_info() -> dict[str, object]:
        """Return service name, semantic version and runtime information."""
        return {
            "service": service_name,
            "version": version,
            "database": database,
            "python": platform.python_version(),
            "build": os.getenv("BUILD_SHA", "dev"),
        }

    return router
