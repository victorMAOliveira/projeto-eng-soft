from datetime import UTC, date, datetime

import httpx
import pytest
from fakeredis import FakeAsyncRedis
from notification_service.main import Settings, create_app
from notification_service.rules import notices_for

from eh_auth import JWTAuth, Role
from eh_events import EventType, make_event

SECRET = "notification-service-test-secret-32chars!"

SAMPLES = {
    EventType.USER_REGISTERED: {"user_id": 1, "email": "a@b.co", "name": "Ana", "role": "student"},
    EventType.PROFILE_UPDATED: {"user_id": 1, "name": "Ana"},
    EventType.INTERNSHIP_PUBLISHED: {
        "internship_id": 5,
        "company_id": 100,
        "company_name": "ACME",
        "title": "Backend",
        "description": "d",
        "requirements": ["Python"],
        "course": "CC",
        "min_semester": 1,
        "hours_per_day": 6,
        "hours_per_week": 30,
        "modality": "remote",
        "city": "Maceió",
        "stipend": 1000,
        "published_at": datetime.now(UTC).isoformat(),
    },
    EventType.INTERNSHIP_CLOSED: {"internship_id": 5, "company_id": 100},
    EventType.APPLICATION_SUBMITTED: {
        "application_id": 7,
        "internship_id": 5,
        "student_id": 1,
        "company_id": 100,
        "student_name": "Ana",
        "internship_title": "Backend",
    },
    EventType.APPLICATION_STATUS_CHANGED: {
        "application_id": 7,
        "internship_id": 5,
        "student_id": 1,
        "company_id": 100,
        "student_name": "Ana",
        "internship_title": "Backend",
        "from_status": "agreement_pending",
        "to_status": "active",
    },
    EventType.AGREEMENT_GENERATED: {
        "agreement_id": "tce-1",
        "application_id": 7,
        "student_id": 1,
        "company_id": 100,
    },
    EventType.AGREEMENT_APPROVED: {
        "agreement_id": "tce-1",
        "application_id": 7,
        "student_id": 1,
        "company_id": 100,
        "approved_by": 300,
        "approved_at": datetime.now(UTC).isoformat(),
    },
    EventType.REPORT_SUBMITTED: {
        "report_id": "r",
        "application_id": 7,
        "student_id": 1,
        "company_id": 100,
        "version": 1,
        "period_start": "2026-12-01",
        "period_end": "2027-05-31",
        "submitted_at": datetime.now(UTC).isoformat(),
    },
    EventType.REPORT_DUE_SOON: {
        "application_id": 7,
        "student_id": 1,
        "due_date": date(2026, 12, 1).isoformat(),
        "days_left": 5,
    },
}


def auth(role: Role, user_id: int) -> dict[str, str]:
    token = JWTAuth(SECRET).create_token(user_id=user_id, role=role, name="X")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def app():
    settings = Settings(redis_url="redis://unused", rabbitmq_url="amqp://x", jwt_secret=SECRET)
    return create_app(settings, redis=FakeAsyncRedis(decode_responses=True), start_consumer=False)


@pytest.fixture
async def client(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://n") as c:
        yield c


@pytest.mark.parametrize("event_type", list(EventType))
def test_every_event_produces_notifications(event_type):
    notices = notices_for(make_event(event_type, SAMPLES[event_type], producer="test"))
    assert notices
    assert all(n.recipient.startswith(("user:", "role:")) for n in notices)


def test_status_change_recipients_and_overdue_text():
    changed = make_event(
        EventType.APPLICATION_STATUS_CHANGED,
        SAMPLES[EventType.APPLICATION_STATUS_CHANGED],
        producer="t",
    )
    assert {n.recipient for n in notices_for(changed)} == {"user:1", "user:100"}
    review = {**SAMPLES[EventType.APPLICATION_STATUS_CHANGED], "to_status": "under_review"}
    assert [
        n.recipient
        for n in notices_for(make_event(EventType.APPLICATION_STATUS_CHANGED, review, producer="t"))
    ] == ["user:1"]
    overdue = {**SAMPLES[EventType.REPORT_DUE_SOON], "days_left": -3, "overdue": True}
    assert (
        "vencido há 3"
        in notices_for(make_event(EventType.REPORT_DUE_SOON, overdue, producer="t"))[0].message
    )


async def test_consumed_events_fill_inboxes(app, client):
    handler = app.state.handler
    for event_type in (EventType.APPLICATION_SUBMITTED, EventType.AGREEMENT_GENERATED):
        await handler(make_event(event_type, SAMPLES[event_type], producer="t"))
    student = (await client.get("/notifications", headers=auth(Role.STUDENT, 1))).json()
    assert student["unread"] == 2
    assert {i["title"] for i in student["items"]} == {"Candidatura enviada", "TCE gerado"}
    coordinator = (await client.get("/notifications", headers=auth(Role.COORDINATOR, 300))).json()
    assert coordinator["items"][0]["title"] == "TCE aguardando aprovação"
    other_coordinator = await client.get(
        "/notifications/unread-count", headers=auth(Role.COORDINATOR, 301)
    )
    assert other_coordinator.json() == {"unread": 1}


async def test_read_state_is_per_user(app, client):
    await app.state.handler(
        make_event(
            EventType.AGREEMENT_GENERATED, SAMPLES[EventType.AGREEMENT_GENERATED], producer="t"
        )
    )
    first = auth(Role.COORDINATOR, 300)
    item = (await client.get("/notifications", headers=first)).json()["items"][0]
    marked = await client.post("/notifications/read", json={"ids": [item["id"]]}, headers=first)
    assert marked.json() == {"unread": 0}
    second = await client.get("/notifications/unread-count", headers=auth(Role.COORDINATOR, 301))
    assert second.json() == {"unread": 1}
    student = auth(Role.STUDENT, 1)
    assert (await client.post("/notifications/read-all", headers=student)).json() == {"unread": 0}


async def test_direct_notifications(client):
    service = {"Authorization": f"Bearer {JWTAuth(SECRET).create_service_token('agent-service')}"}
    body = {"user_id": 1, "title": "Aviso", "message": "Prazo próximo", "kind": "warning"}
    assert (await client.post("/notifications", json=body, headers=service)).status_code == 201
    role_body = {"role": "coordinator", "title": "Aviso", "message": "Estágio perto de 2 anos"}
    assert (await client.post("/notifications", json=role_body, headers=service)).status_code == 201
    both = {**body, "role": "student"}
    assert (await client.post("/notifications", json=both, headers=service)).status_code == 422
    assert (
        await client.post("/notifications", json=body, headers=auth(Role.STUDENT, 1))
    ).status_code == 403
    items = (await client.get("/notifications", headers=auth(Role.STUDENT, 1))).json()["items"]
    assert items[0]["kind"] == "warning"


async def test_idempotency_markers(app):
    inbox = app.state.inbox
    assert not await inbox.seen("e1")
    await inbox.mark("e1", "user.registered")
    assert await inbox.seen("e1")
