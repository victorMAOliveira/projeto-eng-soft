import httpx
import pytest
from api_gateway.config import Settings
from api_gateway.main import create_app
from api_gateway.routes import allowed_roles, resolve_route, upstream_path

from eh_auth import JWTAuth, Role

SECRET = "gateway-test-secret-with-32-plus-characters"


class Upstreams:
    """Fake upstream services served through httpx.MockTransport."""

    def __init__(self):
        self.down: set[str] = set()
        self.not_ready: set[str] = set()
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        service = request.url.host
        if service in self.down:
            raise httpx.ConnectError("refused", request=request)
        if request.url.path == "/ready":
            ok = service not in self.not_ready
            return httpx.Response(
                200 if ok else 503,
                json={
                    "status": "ready" if ok else "not_ready",
                    "database": "PostgreSQL",
                    "uptime_seconds": 12.5,
                    "checks": {"database": {"ok": ok}},
                },
            )
        if request.url.path == "/version":
            return httpx.Response(200, json={"version": "1.0.0"})
        self.requests.append(request)
        return httpx.Response(
            200,
            json={"path": request.url.path, "query": str(request.url.query, "ascii")},
            headers={"X-Served-By": service, "Content-Encoding": "identity"},
        )


@pytest.fixture
def upstreams() -> Upstreams:
    return Upstreams()


@pytest.fixture
def client(upstreams: Upstreams):
    settings = Settings(jwt_secret=SECRET, upstream_retries=0, breaker_failure_threshold=2)
    app = create_app(settings, transport=httpx.MockTransport(upstreams.handler))
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://gateway")


def token(role: Role, user_id: int = 1) -> dict[str, str]:
    jwt = JWTAuth(SECRET).create_token(user_id=user_id, role=role, name="Teste")
    return {"Authorization": f"Bearer {jwt}"}


def test_resolve_route_and_upstream_path():
    assert resolve_route("/api/internships/3").service == "internship-service"
    assert resolve_route("/api/auth/login").public is True
    assert resolve_route("/api/unknown") is None
    assert resolve_route("/api/internshipsX") is None
    assert upstream_path("/api/internships/3") == "/internships/3"
    assert upstream_path("/api") == "/"


def test_policy_table():
    assert allowed_roles("POST", "/api/internships") == {Role.COMPANY}
    assert allowed_roles("GET", "/api/internships") is None
    assert allowed_roles("POST", "/api/agreements/abc-1/approve") == {Role.COORDINATOR}
    assert allowed_roles("GET", "/api/agents/follow-up/runs") == {Role.COORDINATOR}
    assert allowed_roles("POST", "/api/reports/r1/review") == {Role.COORDINATOR}
    assert allowed_roles("POST", "/api/reports") == {Role.STUDENT}


async def test_public_route_is_forwarded_without_token(client, upstreams):
    response = await client.post("/api/auth/login", json={"email": "a", "password": "b"})
    assert response.status_code == 200
    assert response.json()["path"] == "/auth/login"
    assert response.headers["X-Served-By"] == "user-service"
    assert "content-encoding" not in response.headers
    assert upstreams.requests[0].headers.get("x-user-id") is None


async def test_protected_route_requires_valid_token(client):
    assert (await client.get("/api/internships")).status_code == 401
    bad = {"Authorization": "Bearer nope"}
    assert (await client.get("/api/internships", headers=bad)).status_code == 401
    assert (
        await client.get("/api/internships", headers={"Authorization": "Basic x"})
    ).status_code == 401


async def test_role_policy_is_enforced(client, upstreams):
    forbidden = await client.post("/api/internships", json={}, headers=token(Role.STUDENT))
    assert forbidden.status_code == 403
    allowed = await client.post("/api/internships", json={}, headers=token(Role.COMPANY, 9))
    assert allowed.status_code == 200
    assert allowed.headers["X-Served-By"] == "internship-service"
    forwarded = upstreams.requests[-1]
    assert forwarded.headers["x-user-id"] == "9"
    assert forwarded.headers["x-user-role"] == "company"
    assert forwarded.headers["authorization"].startswith("Bearer ")


async def test_service_tokens_bypass_role_policy(client):
    service = {"Authorization": f"Bearer {JWTAuth(SECRET).create_service_token('seed')}"}
    response = await client.post("/api/internships", json={}, headers=service)
    assert response.status_code == 200


async def test_query_string_and_correlation_id_are_propagated(client, upstreams):
    response = await client.get(
        "/api/internships?course=CC&course=SI",
        headers={**token(Role.STUDENT), "X-Correlation-ID": "cid-9"},
    )
    assert response.json()["query"] == "course=CC&course=SI"
    assert response.headers["X-Correlation-ID"] == "cid-9"
    assert upstreams.requests[-1].headers["x-correlation-id"] == "cid-9"


async def test_unknown_route_returns_404(client):
    response = await client.get("/api/nothing", headers=token(Role.STUDENT))
    assert response.status_code == 404


async def test_unavailable_upstream_degrades_to_503_then_opens_circuit(client, upstreams):
    upstreams.down.add("recommendation-service")
    headers = token(Role.STUDENT)
    first = await client.get("/api/recommendations/students/1/internships", headers=headers)
    assert first.status_code == 503
    assert first.json()["service"] == "recommendation-service"
    assert first.json()["reason"] == "unavailable"
    await client.get("/api/recommendations/students/1/internships", headers=headers)
    third = await client.get("/api/recommendations/students/1/internships", headers=headers)
    assert third.json()["reason"] == "circuit_open"


async def test_services_endpoint_aggregates_health(client, upstreams):
    upstreams.down.add("agent-service")
    upstreams.not_ready.add("document-service")
    body = (await client.get("/services")).json()
    by_name = {s["name"]: s for s in body["services"]}
    assert len(by_name) == 8
    assert by_name["api-gateway"]["status"] == "up"
    assert by_name["user-service"]["status"] == "up"
    assert by_name["user-service"]["version"] == "1.0.0"
    assert by_name["user-service"]["database"] == "PostgreSQL"
    assert by_name["user-service"]["latency_ms"] is not None
    assert by_name["document-service"]["status"] == "degraded"
    assert by_name["agent-service"]["status"] == "down"
    assert body["status"] == "degraded"
    assert body["counts"] == {"up": 6, "degraded": 1, "down": 1}


async def test_routes_and_health_endpoints(client):
    routes = (await client.get("/routes")).json()
    assert {"prefix": "/api/auth", "service": "user-service", "public": True} in routes
    health = await client.get("/health")
    assert health.json()["service"] == "api-gateway"
    assert health.headers["X-Served-By"] == "api-gateway"
