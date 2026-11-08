import httpx
import pytest

from eh_http import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    ResilientClient,
    UpstreamUnavailableError,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def make_client(handler, **kwargs) -> ResilientClient:
    kwargs.setdefault("backoff", 0)
    return ResilientClient(
        "http://upstream", name="upstream", transport=httpx.MockTransport(handler), **kwargs
    )


def test_breaker_opens_after_threshold_and_half_opens_after_timeout():
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=10, clock=clock)
    assert breaker.state is CircuitState.CLOSED
    breaker.record_failure()
    assert breaker.allow_request()
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN
    assert not breaker.allow_request()
    clock.now = 10
    assert breaker.state is CircuitState.HALF_OPEN
    breaker.record_failure()  # trial failed -> open again
    assert breaker.state is CircuitState.OPEN
    clock.now = 25
    breaker.record_success()
    assert breaker.state is CircuitState.CLOSED
    assert breaker.failures == 0


def test_breaker_rejects_invalid_threshold():
    with pytest.raises(ValueError):
        CircuitBreaker(failure_threshold=0)


async def test_successful_get_adds_provider_headers():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, json={"ok": True})

    client = make_client(
        handler, header_provider=lambda: {"X-Correlation-ID": "c1", "X-Empty": None}
    )
    response = await client.get("/items", headers={"Authorization": "Bearer t"})
    await client.aclose()
    assert response.json() == {"ok": True}
    assert seen["x-correlation-id"] == "c1"
    assert seen["authorization"] == "Bearer t"
    assert "x-empty" not in seen


async def test_get_retries_on_503_then_succeeds():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200)

    client = make_client(handler, retries=2)
    response = await client.get("/")
    assert response.status_code == 200
    assert len(calls) == 3


async def test_get_returns_last_5xx_and_counts_failure():
    breaker = CircuitBreaker(failure_threshold=1)
    client = make_client(lambda r: httpx.Response(503), retries=1, breaker=breaker)
    response = await client.get("/")
    assert response.status_code == 503
    assert breaker.state is CircuitState.OPEN
    with pytest.raises(CircuitOpenError):
        await client.get("/")


async def test_post_is_not_retried_on_5xx():
    calls = []

    def handler(request):
        calls.append(request.method)
        return httpx.Response(503)

    client = make_client(handler, retries=3)
    response = await client.post("/", json={})
    assert response.status_code == 503
    assert calls == ["POST"]


async def test_connect_error_is_retried_even_for_post_then_raises():
    calls = []

    def handler(request):
        calls.append(1)
        raise httpx.ConnectError("refused", request=request)

    client = make_client(handler, retries=2)
    with pytest.raises(UpstreamUnavailableError) as info:
        await client.post("/", json={})
    assert len(calls) == 3
    assert info.value.upstream == "upstream"


async def test_read_timeout_retried_for_get_but_not_for_post():
    calls = []

    def handler(request):
        calls.append(request.method)
        raise httpx.ReadTimeout("slow", request=request)

    client = make_client(handler, retries=1)
    with pytest.raises(UpstreamUnavailableError):
        await client.get("/")
    assert calls == ["GET", "GET"]
    calls.clear()
    with pytest.raises(UpstreamUnavailableError):
        await client.post("/")
    assert calls == ["POST"]


async def test_put_shortcut_and_4xx_counts_as_success():
    breaker = CircuitBreaker(failure_threshold=1)
    client = make_client(lambda r: httpx.Response(404), breaker=breaker)
    response = await client.put("/x", json={})
    assert response.status_code == 404
    assert breaker.state is CircuitState.CLOSED
