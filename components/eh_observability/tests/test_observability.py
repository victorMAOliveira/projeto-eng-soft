import json
import logging

import httpx
import pytest
from fastapi import FastAPI

from eh_observability import (
    JsonFormatter,
    configure_logging,
    get_correlation_id,
    set_correlation_id,
    setup_observability,
)
from eh_observability.context import reset_correlation_id


def make_app(checks=None) -> FastAPI:
    app = FastAPI()
    setup_observability(app, "demo-service", "1.2.3", checks=checks, database="PostgreSQL")

    @app.get("/echo")
    async def echo() -> dict:
        return {"cid": get_correlation_id()}

    return app


async def call(app: FastAPI, path: str, headers: dict | None = None) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path, headers=headers)


async def test_health_reports_service_and_uptime():
    response = await call(make_app(), "/health")
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ok"
    assert body["service"] == "demo-service"
    assert body["version"] == "1.2.3"
    assert body["uptime_seconds"] >= 0


async def test_ready_ok_when_all_checks_pass():
    async def ok() -> bool:
        return True

    response = await call(make_app({"database": ok}), "/ready")
    assert response.status_code == 200
    assert response.json()["checks"]["database"]["ok"] is True
    assert response.json()["database"] == "PostgreSQL"


async def test_ready_503_when_check_fails_or_raises():
    async def down() -> bool:
        return False

    async def boom() -> bool:
        raise ConnectionError("refused")

    response = await call(make_app({"database": down, "broker": boom}), "/ready")
    body = response.json()
    assert response.status_code == 503
    assert body["status"] == "not_ready"
    assert body["checks"]["database"]["error"] == "check returned false"
    assert "ConnectionError" in body["checks"]["broker"]["error"]


async def test_version_endpoint():
    body = (await call(make_app(), "/version")).json()
    assert body["service"] == "demo-service"
    assert body["version"] == "1.2.3"
    assert body["python"]


async def test_middleware_generates_and_propagates_correlation_id():
    response = await call(make_app(), "/echo")
    generated = response.headers["X-Correlation-ID"]
    assert response.json()["cid"] == generated
    assert response.headers["X-Served-By"] == "demo-service"

    response = await call(make_app(), "/echo", headers={"X-Correlation-ID": "abc-123"})
    assert response.headers["X-Correlation-ID"] == "abc-123"
    assert response.json()["cid"] == "abc-123"


async def test_middleware_preserves_existing_served_by():
    app = make_app()

    @app.get("/proxied")
    async def proxied():
        from fastapi.responses import JSONResponse

        return JSONResponse({}, headers={"X-Served-By": "user-service"})

    response = await call(app, "/proxied")
    assert response.headers["X-Served-By"] == "user-service"


async def test_middleware_ignores_non_http_scopes():
    called = []

    async def inner(scope, receive, send):
        called.append(scope["type"])

    from eh_observability import ObservabilityMiddleware

    middleware = ObservabilityMiddleware(inner, service_name="x")
    await middleware({"type": "lifespan"}, None, None)
    assert called == ["lifespan"]


def test_json_formatter_includes_extra_and_correlation(capsys):
    token = set_correlation_id("cid-1")
    try:
        formatter = JsonFormatter("svc")
        record = logging.makeLogRecord(
            {"msg": "hello %s", "args": ("world",), "levelname": "INFO", "name": "t"}
        )
        record.event_id = "e-1"
        doc = json.loads(formatter.format(record))
    finally:
        reset_correlation_id(token)
    assert doc["message"] == "hello world"
    assert doc["service"] == "svc"
    assert doc["correlation_id"] == "cid-1"
    assert doc["event_id"] == "e-1"


def test_json_formatter_serialises_exceptions():
    formatter = JsonFormatter("svc")
    try:
        raise ValueError("bad")
    except ValueError:
        import sys

        record = logging.makeLogRecord({"msg": "failed", "exc_info": sys.exc_info()})
    doc = json.loads(formatter.format(record))
    assert "ValueError" in doc["exc_info"]


def test_configure_logging_writes_json_to_stdout(capsys):
    logger = configure_logging("svc", "debug")
    logger.info("started", extra={"port": 8000})
    line = capsys.readouterr().out.strip().splitlines()[-1]
    doc = json.loads(line)
    assert doc["message"] == "started"
    assert doc["port"] == 8000
    assert logging.getLogger("uvicorn.access").propagate is True


@pytest.fixture(autouse=True)
def _restore_root_logger():
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
