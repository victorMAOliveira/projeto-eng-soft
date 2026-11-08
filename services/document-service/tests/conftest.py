from datetime import date

import httpx
import pytest
from document_service.main import Settings, create_app
from document_service.storage import Store

from eh_auth import JWTAuth, Role
from eh_events import ApplicationStatusChanged, InMemoryPublisher, PlacementTerms

SECRET = "document-service-test-secret-32-chars!!!"


def auth(role: Role, user_id: int) -> dict[str, str]:
    token = JWTAuth(SECRET).create_token(user_id=user_id, role=role, name="X")
    return {"Authorization": f"Bearer {token}"}


STUDENT = auth(Role.STUDENT, 1)
OTHER_STUDENT = auth(Role.STUDENT, 2)
COMPANY = auth(Role.COMPANY, 100)
OTHER_COMPANY = auth(Role.COMPANY, 200)
COORDINATOR = auth(Role.COORDINATOR, 300)

PDF = b"%PDF-1.4\n% fake report\n"


def approved_payload(**placement_overrides) -> ApplicationStatusChanged:
    terms = {
        "start_date": date(2026, 12, 1),
        "end_date": date(2027, 11, 30),
        "hours_per_day": 6,
        "hours_per_week": 30,
        "stipend": 1500.0,
        "insurer": "Seguradora Exemplo",
        "insurance_policy": "AP-2026-001",
        "supervisor_name": "Carla Mendes",
        "activities": "Desenvolvimento de APIs REST",
        "is_pcd": False,
        "student_course": "Ciência da Computação",
        "company_name": "ACME Tecnologia",
        **placement_overrides,
    }
    return ApplicationStatusChanged(
        application_id=7,
        internship_id=10,
        student_id=1,
        company_id=100,
        student_name="Ana Souza",
        internship_title="Estágio Backend",
        from_status="under_review",
        to_status="approved",
        placement=PlacementTerms(**terms),
    )


class FakeApplications:
    def __init__(self):
        self.status = "active"
        self.down = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("down", request=request)
        app_id = int(request.url.path.rsplit("/", 1)[1])
        if app_id != 7:
            return httpx.Response(404, json={})
        return httpx.Response(
            200,
            json={
                "id": 7,
                "student_id": 1,
                "company_id": 100,
                "student_name": "Ana Souza",
                "internship_title": "Estágio Backend",
                "status": self.status,
            },
        )


@pytest.fixture
def store():
    return Store.in_memory()


@pytest.fixture
def publisher():
    return InMemoryPublisher("document-service")


@pytest.fixture
def applications():
    return FakeApplications()


@pytest.fixture
def app(store, publisher, applications, tmp_path):
    settings = Settings(
        mongo_url="mongodb://unused",
        files_dir=str(tmp_path),
        rabbitmq_url="amqp://x",
        jwt_secret=SECRET,
    )
    return create_app(
        settings,
        store=store,
        publisher=publisher,
        upstream_transport=httpx.MockTransport(applications.handler),
        start_consumer=False,
    )


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://document-service") as c:
        yield c


@pytest.fixture
async def agreement(app):
    return await app.state.generator.generate(approved_payload())
