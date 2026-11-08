"""Aggregate ``/health``, ``/ready`` and ``/version`` of every microservice."""

import asyncio
import time
from typing import Any

import httpx

from api_gateway import SERVICE_NAME, __version__


async def probe_service(client: httpx.AsyncClient, name: str, base_url: str) -> dict[str, Any]:
    """Probe one service and classify it as ``up``, ``degraded`` or ``down``.

    * ``up`` — ``/ready`` answered 200 (database and broker reachable);
    * ``degraded`` — the process answers but a dependency is not ready;
    * ``down`` — the service could not be reached at all.
    """
    result: dict[str, Any] = {
        "name": name,
        "status": "down",
        "version": None,
        "latency_ms": None,
        "database": None,
        "uptime_seconds": None,
        "checks": {},
        "error": None,
    }
    started = time.perf_counter()
    try:
        ready = await client.get(f"{base_url}/ready")
        result["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
        body = ready.json()
        result.update(
            status="up" if ready.status_code == 200 else "degraded",
            database=body.get("database"),
            uptime_seconds=body.get("uptime_seconds"),
            checks=body.get("checks", {}),
        )
        version = await client.get(f"{base_url}/version")
        if version.status_code == 200:
            result["version"] = version.json().get("version")
    except (httpx.HTTPError, ValueError) as exc:
        result["error"] = type(exc).__name__
    return result


async def aggregate(
    client: httpx.AsyncClient, upstreams: dict[str, str], gateway_started: float
) -> dict[str, Any]:
    """Probe all upstreams concurrently and summarise the platform state."""
    probes = await asyncio.gather(
        *(probe_service(client, name, url) for name, url in upstreams.items())
    )
    gateway = {
        "name": SERVICE_NAME,
        "status": "up",
        "version": __version__,
        "latency_ms": 0.0,
        "database": None,
        "uptime_seconds": round(time.time() - gateway_started, 1),
        "checks": {},
        "error": None,
    }
    services = [gateway, *probes]
    counts = {s: sum(1 for p in services if p["status"] == s) for s in ("up", "degraded", "down")}
    overall = (
        "up" if counts["up"] == len(services) else ("down" if counts["up"] == 0 else "degraded")
    )
    return {"status": overall, "counts": counts, "services": services}
