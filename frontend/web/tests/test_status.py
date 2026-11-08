from conftest import login_as

SERVICES = {
    "status": "degraded",
    "counts": {"up": 2, "degraded": 0, "down": 1},
    "services": [
        {
            "name": "api-gateway",
            "status": "up",
            "version": "1.0.0",
            "latency_ms": 0.0,
            "database": None,
            "uptime_seconds": 3725.0,
            "checks": {},
            "error": None,
        },
        {
            "name": "user-service",
            "status": "up",
            "version": "1.0.0",
            "latency_ms": 4.2,
            "database": "PostgreSQL",
            "uptime_seconds": 60.0,
            "checks": {"database": {"ok": True}, "broker": {"ok": True}},
            "error": None,
        },
        {
            "name": "agent-service",
            "status": "down",
            "version": None,
            "latency_ms": None,
            "database": None,
            "uptime_seconds": None,
            "checks": {},
            "error": "ConnectError",
        },
    ],
}
ROUTES = [
    {"prefix": "/api/auth", "service": "user-service", "public": True},
    {"prefix": "/api/agents", "service": "agent-service", "public": False},
]


async def test_status_page_is_public_and_complete(client, gw):
    gw.add("GET", "/services", SERVICES, service="api-gateway")
    gw.add("GET", "/routes", ROUTES, service="api-gateway")
    page = await client.get("/status")
    assert page.status_code == 200
    for text in (
        "Operação degradada",
        "1h 2min 5s",
        "4.2 ms",
        "PostgreSQL",
        "Fora do ar",
        "/api/agents/*",
    ):
        assert text in page.text
    assert 'hx-trigger="every 5s"' in page.text
    partial = await client.get("/status/painel")
    assert "<html" not in partial.text and "user-service" in partial.text


async def test_status_page_when_gateway_is_down(client, gw):
    gw.down = True
    page = await client.get("/status")
    assert "Gateway indisponível" in page.text


async def test_dashboard_shows_services_legend(client, gw):
    gw.add("GET", "/services", SERVICES, service="api-gateway")
    gw.add("GET", "/api/internships/mine", [])
    login_as(client, "company", 5, "ACME")
    page = await client.get("/")
    assert "Microsserviços desta tela" in page.text
    assert "eh-dot--down" in page.text and "Agentes IA" in page.text
