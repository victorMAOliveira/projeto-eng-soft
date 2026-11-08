from datetime import date, timedelta
from types import SimpleNamespace

import httpx
import pytest
from agent_service.main import Settings, create_app

from eh_auth import JWTAuth, Role
from eh_db import Base, Database
from eh_events import InMemoryPublisher

SECRET = "agent-service-test-secret-with-32-chars!!"
TODAY = date.today()

REC = {
    "internship_id": 10,
    "title": "Estágio Backend",
    "company_name": "ACME",
    "score": 0.72,
    "matched_skills": ["Python", "SQL"],
    "missing_skills": ["Docker"],
    "explanation": "Você tem 2 de 3 habilidades exigidas (Python, SQL). Faltam: Docker.",
    "eliminated_by": [],
}
PLACEMENTS = [
    {
        "application_id": 1,
        "student_id": 1,
        "student_name": "Ana",
        "company_id": 100,
        "status": "active",
        "next_report_due": (TODAY + timedelta(days=5)).isoformat(),
        "report_state": "due_soon",
        "days_to_report": 5,
        "max_end_date": (TODAY + timedelta(days=400)).isoformat(),
        "hours_per_day": 6,
        "hours_per_week": 30,
    },
    {
        "application_id": 2,
        "student_id": 2,
        "student_name": "Bruno",
        "company_id": 100,
        "status": "active",
        "next_report_due": (TODAY - timedelta(days=3)).isoformat(),
        "report_state": "overdue",
        "days_to_report": -3,
        "max_end_date": (TODAY + timedelta(days=20)).isoformat(),
        "hours_per_day": 7,
        "hours_per_week": 35,
    },
    {
        "application_id": 3,
        "student_id": 3,
        "student_name": "Carla",
        "company_id": 100,
        "status": "active",
        "next_report_due": (TODAY + timedelta(days=120)).isoformat(),
        "report_state": "ok",
        "days_to_report": 120,
        "max_end_date": None,
        "hours_per_day": 6,
        "hours_per_week": 30,
    },
]


class Platform:
    """Fake upstream services reached by the tools."""

    def __init__(self):
        self.down: set[str] = set()
        self.notifications: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        if host in self.down:
            raise httpx.ConnectError("down", request=request)
        if path == "/profiles/students/1":
            return httpx.Response(
                200,
                json={
                    "user_id": 1,
                    "name": "Ana Souza",
                    "course": "Ciência da Computação",
                    "semester": 5,
                    "skills": ["Python", "SQL"],
                    "resume_summary": "curto",
                    "preferred_modality": None,
                },
            )
        if path == "/recommendations/students/1/internships":
            return httpx.Response(
                200,
                json={
                    "strategy": "hybrid",
                    "items": [REC],
                    "filtered": [
                        {
                            **REC,
                            "internship_id": 11,
                            "title": "Estágio Design",
                            "eliminated_by": ["Curso incompatível."],
                        }
                    ],
                },
            )
        if path == "/internships":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": 10,
                            "title": "Estágio Backend",
                            "company_name": "ACME",
                            "course": "CC",
                            "modality": "remote",
                            "city": "Maceió",
                            "requirements": ["Python"],
                        }
                    ]
                },
            )
        if path == "/recommendations/internships/10/candidates":
            return httpx.Response(
                200,
                json={
                    "title": "Estágio Backend",
                    "requirements": ["Python", "SQL"],
                    "items": [
                        {
                            "student_id": 1,
                            "name": "Ana",
                            "score": 0.8,
                            "matched_skills": ["Python", "SQL"],
                            "missing_skills": [],
                            "explanation": "Atende 2 de 2 requisitos.",
                            "eliminated_by": [],
                            "application_status": "submitted",
                        },
                        {
                            "student_id": 4,
                            "name": "Davi",
                            "score": 0.0,
                            "matched_skills": [],
                            "missing_skills": ["Python"],
                            "explanation": "Curso incompatível.",
                            "eliminated_by": ["Curso incompatível."],
                            "application_status": "submitted",
                        },
                    ],
                },
            )
        if path == "/placements":
            return httpx.Response(200, json=PLACEMENTS)
        if path == "/reports":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "r1",
                        "application_id": 1,
                        "title": "R1",
                        "status": "submitted",
                        "versions": [{}],
                    }
                ],
            )
        if path == "/notifications" and request.method == "POST":
            import json

            self.notifications.append(json.loads(request.content))
            return httpx.Response(201, json={"id": "n1"})
        return httpx.Response(404, json={"detail": "not found"})


def block(kind: str, **data):
    return SimpleNamespace(type=kind, **data)


class ScriptedLlm:
    """Returns pre-programmed Messages API responses and records the requests."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        item = self.responses.pop(0) if self.responses else self.responses_default()
        if isinstance(item, Exception):
            raise item
        return item

    @staticmethod
    def responses_default():
        return SimpleNamespace(
            stop_reason="tool_use",
            content=[block("tool_use", id="t", name="get_profile", input={})],
        )


@pytest.fixture
def platform():
    return Platform()


@pytest.fixture
def publisher():
    return InMemoryPublisher("agent-service")


@pytest.fixture
async def db():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all(Base.metadata)
    yield database
    await database.dispose()


def make_app(db, publisher, platform, llm=None, **overrides):
    settings = Settings(
        database_url="sqlite+aiosqlite://", rabbitmq_url="amqp://x", jwt_secret=SECRET, **overrides
    )
    return create_app(
        settings,
        db=db,
        publisher=publisher,
        llm=llm,
        upstream_transport=httpx.MockTransport(platform.handler),
        start_scheduler=False,
    )


@pytest.fixture
async def client(db, publisher, platform):
    app = make_app(db, publisher, platform)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://a") as c:
        yield c


def auth(role: Role, user_id: int, name: str = "Usuário") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {JWTAuth(SECRET).create_token(user_id=user_id, role=role, name=name)}"
    }


STUDENT = auth(Role.STUDENT, 1, "Ana Souza")
COMPANY = auth(Role.COMPANY, 100, "ACME")
COORDINATOR = auth(Role.COORDINATOR, 300, "Coordenação")
