from datetime import date, timedelta

import httpx
import pytest
from application_service.main import Settings, create_app

from eh_auth import JWTAuth, Role
from eh_db import Base, Database
from eh_events import InMemoryPublisher

SECRET = "application-service-test-secret-32-chars!"

INTERNSHIP = {
    "id": 10,
    "company_id": 100,
    "company_name": "ACME Tecnologia",
    "title": "Estágio Backend",
    "course": "Ciência da Computação",
    "min_semester": 4,
    "hours_per_day": 6,
    "hours_per_week": 30,
    "stipend": 1500.0,
    "status": "open",
}
PROFILE = {
    "user_id": 1,
    "course": "Ciência da Computação",
    "semester": 5,
    "weekly_availability_hours": 30,
    "is_pcd": False,
}


class FakeUpstreams:
    """internship-service and user-service doubles."""

    def __init__(self):
        self.internships = {10: dict(INTERNSHIP), 11: {**INTERNSHIP, "id": 11, "status": "closed"}}
        self.profiles = {1: dict(PROFILE), 2: {**PROFILE, "user_id": 2, "course": "Design"}}
        self.down = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("down", request=request)
        kind, _, ident = request.url.path.strip("/").rpartition("/")
        store = self.internships if kind == "internships" else self.profiles
        item = store.get(int(ident))
        return httpx.Response(200, json=item) if item else httpx.Response(404, json={})


@pytest.fixture
async def db():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all(Base.metadata)
    yield database
    await database.dispose()


@pytest.fixture
def publisher():
    return InMemoryPublisher("application-service")


@pytest.fixture
def upstreams():
    return FakeUpstreams()


@pytest.fixture
async def client(db, publisher, upstreams):
    settings = Settings(
        database_url="sqlite+aiosqlite://", rabbitmq_url="amqp://x", jwt_secret=SECRET
    )
    app = create_app(
        settings,
        db=db,
        publisher=publisher,
        upstream_transport=httpx.MockTransport(upstreams.handler),
        start_consumer=False,
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://application-service") as c:
        yield c


def auth(role: Role, user_id: int, name: str = "Usuário") -> dict[str, str]:
    token = JWTAuth(SECRET).create_token(user_id=user_id, role=role, name=name)
    return {"Authorization": f"Bearer {token}"}


STUDENT = auth(Role.STUDENT, 1, "Ana Souza")
OTHER_STUDENT = auth(Role.STUDENT, 2, "Bruno Lima")
COMPANY = auth(Role.COMPANY, 100, "ACME Tecnologia")
OTHER_COMPANY = auth(Role.COMPANY, 200, "Beta")
COORDINATOR = auth(Role.COORDINATOR, 300, "Coordenação")


def placement(**overrides) -> dict:
    start = date.today() + timedelta(days=7)
    terms = {
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=365)).isoformat(),
        "supervisor_name": "Carla Mendes",
        "insurer": "Seguradora Exemplo",
        "insurance_policy": "AP-2026-001",
        "activities": "Desenvolvimento de APIs",
    }
    terms.update(overrides)
    return terms


async def submit(client, internship_id: int = 10, headers=STUDENT):
    return await client.post(
        "/applications",
        json={"internship_id": internship_id, "cover_letter": "Olá!"},
        headers=headers,
    )


async def approved_application(client) -> dict:
    created = (await submit(client)).json()
    await client.post(f"/applications/{created['id']}/review", headers=COMPANY)
    response = await client.post(
        f"/applications/{created['id']}/approve", json=placement(), headers=COMPANY
    )
    assert response.status_code == 200, response.text
    return response.json()
