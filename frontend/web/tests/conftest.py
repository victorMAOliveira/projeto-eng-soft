import base64
import json
import time

import httpx
import pytest
from web_frontend.config import Settings
from web_frontend.main import create_app


def fake_jwt(user_id: int = 1, role: str = "student", name: str = "Ana Souza") -> str:
    """Unsigned token with the claims the frontend reads (it never verifies them)."""

    def b64(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    claims = {"sub": str(user_id), "role": role, "name": name, "exp": time.time() + 3600}
    return f"{b64({'alg': 'HS256'})}.{b64(claims)}.sig"


class FakeGateway:
    """Programmable stand-in for the API Gateway."""

    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], tuple[int, object, str]] = {}
        self.calls: list[httpx.Request] = []
        self.down = False

    def add(self, method: str, path: str, data: object, status: int = 200, service: str = "x"):
        self.routes[(method, path)] = (status, data, service)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if self.down:
            raise httpx.ConnectError("down", request=request)
        key = (request.method, request.url.path)
        if key not in self.routes:
            return httpx.Response(404, json={"detail": "not found"})
        status, data, service = self.routes[key]
        return httpx.Response(status, json=data, headers={"X-Served-By": service})


@pytest.fixture
def gw() -> FakeGateway:
    return FakeGateway()


@pytest.fixture
async def client(gw: FakeGateway):
    app = create_app(Settings(gateway_url="http://gw"), transport=httpx.MockTransport(gw.handler))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://web") as c:
        yield c


def login_as(
    client: httpx.AsyncClient, role: str = "student", user_id: int = 1, name: str = "Ana Souza"
):
    client.cookies.set("eh_token", fake_jwt(user_id, role, name))
