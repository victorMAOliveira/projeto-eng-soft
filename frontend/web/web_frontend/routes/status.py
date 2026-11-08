"""Microservices status page (public): aggregated health from the gateway."""

from fastapi import APIRouter, Request
from fastapi.responses import Response

from web_frontend.web import gateway, render

router = APIRouter()


@router.get("/status")
async def status_page(request: Request) -> Response:
    """Status of every microservice with auto-refresh (HTMX polls the panel)."""
    api = gateway(request)
    services = await api.get("/services")
    routes = await api.get("/routes")
    return render(request, "status/page.html", services=services, routes=routes)


@router.get("/status/painel")
async def status_panel(request: Request) -> Response:
    """Partial re-rendered every 5 s by HTMX."""
    services = await gateway(request).get("/services")
    return render(request, "status/_panel.html", services=services)
