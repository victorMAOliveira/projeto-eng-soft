import httpx
import pytest
from internship_service.config import Settings
from internship_service.main import create_app

from eh_auth import JWTAuth, Role
from eh_db import Base, Database
from eh_events import InMemoryPublisher

SECRET = "internship-service-test-secret-32-chars!!"

VAGA = {
    "title": "Estágio em Desenvolvimento Backend",
    "description": "Desenvolver APIs REST com Python e FastAPI em time ágil.",
    "requirements": ["Python", "SQL", "python", " Git "],
    "course": "Ciência da Computação",
    "min_semester": 4,
    "hours_per_day": 6,
    "hours_per_week": 30,
    "modality": "hybrid",
    "city": "Maceió",
    "stipend": 1200,
}


@pytest.fixture
async def db():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all(Base.metadata)
    yield database
    await database.dispose()


@pytest.fixture
def publisher():
    return InMemoryPublisher("internship-service")


@pytest.fixture
async def client(db, publisher):
    settings = Settings(
        database_url="sqlite+aiosqlite://", rabbitmq_url="amqp://x", jwt_secret=SECRET
    )
    app = create_app(settings, db=db, publisher=publisher)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://internship-service") as c:
        yield c


def headers(role: Role, user_id: int = 1, name: str = "ACME Tecnologia") -> dict[str, str]:
    token = JWTAuth(SECRET).create_token(user_id=user_id, role=role, name=name)
    return {"Authorization": f"Bearer {token}"}
