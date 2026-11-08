import httpx
import pytest
from user_service.config import Settings
from user_service.main import create_app

from eh_auth import JWTAuth
from eh_db import Base, Database
from eh_events import InMemoryPublisher

SECRET = "user-service-test-secret-with-32-chars!!"


@pytest.fixture
async def db():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all(Base.metadata)
    yield database
    await database.dispose()


@pytest.fixture
def publisher():
    return InMemoryPublisher("user-service")


@pytest.fixture
def auth():
    return JWTAuth(SECRET)


@pytest.fixture
async def client(db, publisher):
    settings = Settings(
        database_url="sqlite+aiosqlite://", rabbitmq_url="amqp://x", jwt_secret=SECRET
    )
    app = create_app(settings, db=db, publisher=publisher)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://user-service") as c:
        yield c


async def register(
    client, email, role="student", name="Ana Souza", password="SenhaForte1", headers=None
):
    return await client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": name, "role": role},
        headers=headers or {},
    )


async def login(client, email, password="SenhaForte1"):
    response = await client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
