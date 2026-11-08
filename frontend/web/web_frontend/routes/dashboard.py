"""Role-based dashboard. Each panel calls the gateway independently, so one
unavailable microservice only blanks its own panel (graceful degradation)."""

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import Response

from web_frontend.gateway import ApiResult
from web_frontend.web import gateway, render, require_user

router = APIRouter()


async def _panels(request: Request, calls: dict[str, tuple[str, dict]]) -> dict[str, ApiResult]:
    """Run gateway GETs concurrently; returns ``{panel: ApiResult}``."""
    user = require_user(request)
    api = gateway(request)
    names = list(calls)
    results = await asyncio.gather(
        *(api.get(path, token=user.token, params=params) for path, params in calls.values())
    )
    return dict(zip(names, results, strict=True))


@router.get("/")
async def dashboard(request: Request) -> Response:
    """Dashboard adapted to the user's role."""
    user = require_user(request)
    if user.role == "student":
        calls = {
            "profile": ("/api/profiles/students/me", {}),
            "latest": ("/api/internships", {"size": 5}),
            "stats": ("/api/internships/stats", {}),
            "apps": ("/api/applications/stats", {}),
            "placements": ("/api/placements", {"status": "active"}),
            "notices": ("/api/notifications", {"limit": 5}),
            "recs": (f"/api/recommendations/students/{user.id}/internships", {"k": 3}),
        }
    elif user.role == "company":
        calls = {
            "mine": ("/api/internships/mine", {}),
            "stats": ("/api/internships/stats", {}),
            "apps": ("/api/applications/stats", {}),
            "notices": ("/api/notifications", {"limit": 5}),
        }
    else:
        calls = {
            "stats": ("/api/internships/stats", {}),
            "latest": ("/api/internships", {"size": 5}),
            "apps": ("/api/applications/stats", {}),
            "pending": ("/api/agreements", {"status": "pending_approval"}),
            "placements": ("/api/placements", {"status": "active"}),
            "notices": ("/api/notifications", {"limit": 5}),
        }
    panels = await _panels(request, calls)
    unavailable = sorted({p.unavailable_service for p in panels.values() if p.unavailable_service})
    return render(request, "dashboard.html", panels=panels, unavailable=unavailable)
