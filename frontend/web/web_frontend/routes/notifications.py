"""Notification inbox and the top-bar counter (polled by HTMX)."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from web_frontend.session import current_user
from web_frontend.web import gateway, redirect, render, require_user

router = APIRouter()


@router.get("/notificacoes")
async def inbox(request: Request) -> Response:
    """Personal and role notifications, newest first."""
    user = require_user(request)
    result = await gateway(request).get(
        "/api/notifications", token=user.token, params={"limit": 50}
    )
    return render(request, "notifications.html", result=result)


@router.post("/notificacoes/ler-todas")
async def read_all(request: Request) -> Response:
    """Mark everything as read."""
    user = require_user(request)
    await gateway(request).post("/api/notifications/read-all", token=user.token)
    return redirect("/notificacoes", flash="Notificações marcadas como lidas.", kind="info")


@router.get("/notificacoes/contador")
async def counter(request: Request) -> Response:
    """Tiny HTML fragment with the unread badge (empty if unavailable)."""
    user = current_user(request)
    if user is None:
        return HTMLResponse("")
    result = await gateway(request).get("/api/notifications/unread-count", token=user.token)
    unread = result.data.get("unread", 0) if result.ok else 0
    badge = f'<span class="dot" data-testid="unread">{unread}</span>' if unread else ""
    return HTMLResponse(badge, headers={"Cache-Control": "no-store"})
