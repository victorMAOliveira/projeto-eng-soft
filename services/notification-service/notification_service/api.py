"""HTTP API of the notification-service."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from eh_auth import Principal, Role, get_current_principal, require_role
from notification_service.inbox import Inbox
from notification_service.rules import Notice

router = APIRouter(tags=["notifications"])


class NoticeIn(BaseModel):
    """Direct notification (used by the follow-up agent's ``send_notification`` tool)."""

    user_id: int | None = None
    role: Literal["student", "company", "coordinator"] | None = None
    title: str = Field(min_length=2, max_length=120)
    message: str = Field(min_length=2, max_length=1000)
    kind: Literal["info", "success", "warning"] = "info"
    link: str | None = Field(default=None, max_length=200)


class ReadIn(BaseModel):
    """Notification ids to mark as read."""

    ids: list[str] = Field(min_length=1, max_length=200)


def inbox_dep(request: Request) -> Inbox:
    """Inbox configured at startup."""
    return request.app.state.inbox


@router.get("/notifications", summary="Minhas notificações (pessoais + do meu papel)")
async def list_notifications(
    limit: int = Query(30, ge=1, le=200),
    principal: Principal = Depends(get_current_principal),
    inbox: Inbox = Depends(inbox_dep),
) -> dict[str, Any]:
    """Newest notifications with unread counter."""
    items = await inbox.list_for(principal.id, principal.role, 200)
    return {"items": items[:limit], "unread": sum(1 for i in items if not i["read"])}


@router.get("/notifications/unread-count", summary="Quantidade de não lidas")
async def unread(
    principal: Principal = Depends(get_current_principal), inbox: Inbox = Depends(inbox_dep)
) -> dict[str, int]:
    """Badge counter for the top bar."""
    return {"unread": await inbox.unread_count(principal.id, principal.role)}


@router.post("/notifications/read", summary="Marcar como lidas")
async def mark_read(
    body: ReadIn,
    principal: Principal = Depends(get_current_principal),
    inbox: Inbox = Depends(inbox_dep),
) -> dict[str, int]:
    """Mark the given notifications as read."""
    await inbox.mark_read(principal.id, body.ids)
    return {"unread": await inbox.unread_count(principal.id, principal.role)}


@router.post("/notifications/read-all", summary="Marcar todas como lidas")
async def mark_all_read(
    principal: Principal = Depends(get_current_principal), inbox: Inbox = Depends(inbox_dep)
) -> dict[str, int]:
    """Mark every visible notification as read."""
    items = await inbox.list_for(principal.id, principal.role, 200)
    await inbox.mark_read(principal.id, [i["id"] for i in items])
    return {"unread": 0}


@router.post(
    "/notifications",
    status_code=status.HTTP_201_CREATED,
    summary="Enviar notificação direta (serviços internos e coordenação)",
)
async def send(
    body: NoticeIn,
    _: Principal = Depends(require_role(Role.SERVICE, Role.COORDINATOR)),
    inbox: Inbox = Depends(inbox_dep),
) -> dict[str, Any]:
    """Deliver a notification to one user or to a whole role."""
    if (body.user_id is None) == (body.role is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Informe user_id ou role")
    recipient = f"user:{body.user_id}" if body.user_id is not None else f"role:{body.role}"
    return await inbox.deliver(Notice(recipient, body.title, body.message, body.kind, body.link))
