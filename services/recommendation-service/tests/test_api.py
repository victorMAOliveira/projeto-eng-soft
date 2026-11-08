from datetime import UTC, datetime

import httpx
import pytest
from recommendation_service.main import Settings, create_app

from eh_auth import JWTAuth, Role
from eh_db import Base, Database
from eh_events import EventType, make_event

SECRET = "recommendation-service-test-secret-32ch!!"
NOW = datetime.now(UTC).isoformat()


def auth(role: Role, user_id: int) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {JWTAuth(SECRET).create_token(user_id=user_id, role=role, name='X')}"
    }


def published(internship_id: int, company_id: int = 100, **kw) -> dict:
    data = {
        "internship_id": internship_id,
        "company_id": company_id,
        "company_name": "ACME",
        "title": "Estágio Backend Python",
        "description": "APIs com FastAPI e SQL",
        "requirements": ["Python", "SQL", "Git"],
        "course": "Ciência da Computação",
        "min_semester": 3,
        "hours_per_day": 6,
        "hours_per_week": 30,
        "modality": "hybrid",
        "city": "Maceió",
        "stipend": 1500,
        "published_at": NOW,
    }
    data.update(kw)
    return data


def profile(user_id: int, **kw) -> dict:
    data = {
        "user_id": user_id,
        "name": f"Estudante {user_id}",
        "course": "Ciência da Computação",
        "semester": 5,
        "skills": ["Python", "SQL"],
        "resume_summary": "APIs em Python",
        "weekly_availability_hours": 30,
        "preferred_modality": "hybrid",
        "city": "Maceió",
    }
    data.update(kw)
    return data


class Sources:
    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/users":
            return httpx.Response(200, json=[{"id": 1}, {"id": 2}])
        if path == "/profiles/students":
            return httpx.Response(200, json=[profile(1), profile(2, skills=[])])
        if path == "/internships":
            item = {
                **published(10),
                "id": 10,
                "status": "open",
                "published_at": "2026-11-08T10:00:00Z",
            }
            item.pop("internship_id")
            return httpx.Response(200, json={"items": [item], "total": 1, "page": 1, "size": 100})
        if path == "/applications":
            return httpx.Response(
                200, json=[{"id": 5, "internship_id": 10, "student_id": 1, "status": "submitted"}]
            )
        return httpx.Response(404)


@pytest.fixture
async def app():
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.create_all(Base.metadata)
    settings = Settings(
        database_url="sqlite+aiosqlite://", rabbitmq_url="amqp://x", jwt_secret=SECRET
    )
    application = create_app(
        settings,
        db=db,
        upstream_transport=httpx.MockTransport(Sources().handler),
        start_consumer=False,
    )
    yield application
    await db.dispose()


@pytest.fixture
async def client(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://r") as c:
        yield c


async def feed(app, event_type, payload):
    await app.state.projection(make_event(event_type, payload, producer="test"))


async def test_projection_feeds_recommendations(app, client):
    await feed(app, EventType.INTERNSHIP_PUBLISHED, published(10))
    await feed(
        app,
        EventType.INTERNSHIP_PUBLISHED,
        published(11, title="Frontend", requirements=["React"], description="Interfaces React"),
    )
    await feed(app, EventType.INTERNSHIP_PUBLISHED, published(12, course="Design"))
    await feed(
        app,
        EventType.USER_REGISTERED,
        {"user_id": 1, "email": "a@b.co", "name": "Ana", "role": "student"},
    )
    await feed(app, EventType.PROFILE_UPDATED, profile(1))
    response = await client.get(
        "/recommendations/students/1/internships?include_filtered=true",
        headers=auth(Role.STUDENT, 1),
    )
    body = response.json()
    assert response.status_code == 200
    assert body["strategy"] == "hybrid"
    assert body["items"][0]["internship_id"] == 10
    assert body["items"][0]["matched_skills"] == ["Python", "SQL"]
    assert body["items"][0]["missing_skills"] == ["Git"]
    assert body["filtered"][0]["internship_id"] == 12
    assert "Curso incompatível" in body["filtered"][0]["explanation"]
    assert body["weights"]["content"] == 0.5


async def test_closed_and_applied_offers_are_not_recommended(app, client):
    await feed(app, EventType.INTERNSHIP_PUBLISHED, published(10))
    await feed(app, EventType.INTERNSHIP_PUBLISHED, published(11))
    await feed(app, EventType.PROFILE_UPDATED, profile(1))
    await feed(app, EventType.INTERNSHIP_CLOSED, {"internship_id": 11, "company_id": 100})
    submitted = {
        "application_id": 5,
        "internship_id": 10,
        "student_id": 1,
        "company_id": 100,
        "student_name": "A",
        "internship_title": "T",
    }
    await feed(app, EventType.APPLICATION_SUBMITTED, submitted)
    await feed(app, EventType.APPLICATION_SUBMITTED, submitted)  # duplicate-safe
    body = (
        await client.get("/recommendations/students/1/internships", headers=auth(Role.STUDENT, 1))
    ).json()
    assert body["items"] == []
    assert body["already_applied"] == [10]
    stats = (await client.get("/recommendations/stats", headers=auth(Role.COORDINATOR, 9))).json()
    assert stats == {**stats, "students": 1, "internships_open": 1, "applications": 1}


async def test_cold_start_for_unknown_student_and_access_control(app, client):
    await feed(app, EventType.INTERNSHIP_PUBLISHED, published(10))
    body = (
        await client.get("/recommendations/students/7/internships", headers=auth(Role.STUDENT, 7))
    ).json()
    assert body["strategy"] == "cold_start"
    assert body["items"][0]["strategy"] == "cold_start"
    assert (
        await client.get("/recommendations/students/7/internships", headers=auth(Role.STUDENT, 8))
    ).status_code == 403
    assert (
        await client.get("/recommendations/students/7/internships", headers=auth(Role.COMPANY, 100))
    ).status_code == 403


async def test_candidate_ranking(app, client):
    await feed(app, EventType.INTERNSHIP_PUBLISHED, published(10))
    await feed(app, EventType.PROFILE_UPDATED, profile(1, skills=["Python", "SQL", "Git"]))
    await feed(app, EventType.PROFILE_UPDATED, profile(2, skills=["Python"]))
    await feed(
        app, EventType.PROFILE_UPDATED, profile(3, skills=["Python", "SQL", "Git"], course="Design")
    )
    for app_id, student in ((1, 1), (2, 2)):
        await feed(
            app,
            EventType.APPLICATION_SUBMITTED,
            {
                "application_id": app_id,
                "internship_id": 10,
                "student_id": student,
                "company_id": 100,
                "student_name": "x",
                "internship_title": "t",
            },
        )
    await feed(
        app,
        EventType.APPLICATION_STATUS_CHANGED,
        {
            "application_id": 1,
            "internship_id": 10,
            "student_id": 1,
            "company_id": 100,
            "student_name": "x",
            "internship_title": "t",
            "from_status": "submitted",
            "to_status": "under_review",
        },
    )
    url = "/recommendations/internships/10/candidates"
    ranking = (await client.get(url, headers=auth(Role.COMPANY, 100))).json()
    assert [i["student_id"] for i in ranking["items"]] == [1, 2]
    assert ranking["items"][0]["application_status"] == "under_review"
    everyone = (await client.get(f"{url}?scope=all", headers=auth(Role.COORDINATOR, 9))).json()
    assert [i["student_id"] for i in everyone["items"]][-1] == 3
    assert everyone["items"][-1]["eliminated_by"]
    assert (await client.get(url, headers=auth(Role.COMPANY, 200))).status_code == 403
    assert (
        await client.get(
            "/recommendations/internships/99/candidates", headers=auth(Role.COMPANY, 100)
        )
    ).status_code == 404


async def test_rebuild_from_source_services(client):
    response = await client.post("/recommendations/rebuild", headers=auth(Role.COORDINATOR, 9))
    assert response.json() == {"students": 2, "internships": 1, "applications": 1}
    body = (
        await client.get("/recommendations/students/2/internships", headers=auth(Role.STUDENT, 2))
    ).json()
    assert body["items"][0]["internship_id"] == 10
    assert (
        await client.post("/recommendations/rebuild", headers=auth(Role.STUDENT, 1))
    ).status_code == 403
