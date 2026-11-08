from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from fastapi import Depends, FastAPI

from eh_auth import (
    JWTAuth,
    Principal,
    Role,
    TokenError,
    get_optional_principal,
    hash_password,
    install_auth,
    needs_rehash,
    require_role,
    verify_password,
)

SECRET = "test-secret-with-more-than-32-characters!!"


@pytest.fixture
def auth() -> JWTAuth:
    return JWTAuth(SECRET, expires_minutes=5)


def test_password_hash_roundtrip():
    hashed = hash_password("S3nha!forte")
    assert hashed.startswith("$argon2id$")
    assert verify_password("S3nha!forte", hashed)
    assert not verify_password("errada", hashed)
    assert not verify_password("x", "not-a-hash")
    assert needs_rehash(hashed) is False


def test_token_roundtrip(auth: JWTAuth):
    token = auth.create_token(user_id=7, role=Role.STUDENT, name="Ana", email="ana@ufal.test")
    principal = auth.decode(token)
    assert principal == Principal(id=7, role=Role.STUDENT, name="Ana", email="ana@ufal.test")
    assert not principal.is_service


def test_service_token(auth: JWTAuth):
    principal = auth.decode(auth.create_service_token("agent-service"))
    assert principal.is_service
    assert principal.name == "agent-service"
    assert principal.id == 0


def test_secret_must_be_long_enough():
    with pytest.raises(ValueError):
        JWTAuth("short")


def test_expired_and_tampered_tokens_are_rejected(auth: JWTAuth):
    expired = jwt.encode(
        {
            "sub": "1",
            "role": "student",
            "iss": "estagiohub",
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        SECRET,
        algorithm="HS256",
    )
    with pytest.raises(TokenError):
        auth.decode(expired)
    other = JWTAuth("another-secret-with-more-than-32-chars!!")
    with pytest.raises(TokenError):
        auth.decode(other.create_token(user_id=1, role="student", name="x"))
    with pytest.raises(TokenError):
        auth.decode("garbage")


def test_unknown_role_is_rejected(auth: JWTAuth):
    token = jwt.encode(
        {
            "sub": "1",
            "role": "admin",
            "iss": "estagiohub",
            "exp": datetime.now(UTC) + timedelta(minutes=1),
        },
        SECRET,
        algorithm="HS256",
    )
    with pytest.raises(TokenError):
        auth.decode(token)


def build_app(auth: JWTAuth | None) -> FastAPI:
    app = FastAPI()
    if auth:
        install_auth(app, auth)

    @app.get("/companies-only")
    async def companies_only(p: Principal = Depends(require_role(Role.COMPANY, "coordinator"))):
        return {"id": p.id, "role": p.role}

    @app.get("/optional")
    async def optional(p: Principal | None = Depends(get_optional_principal)):
        return {"who": p.name if p else None}

    return app


async def get(app: FastAPI, path: str, token: str | None = None) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        return await client.get(path, headers=headers)


async def test_require_role_allows_listed_roles(auth: JWTAuth):
    token = auth.create_token(user_id=3, role=Role.COMPANY, name="ACME")
    response = await get(build_app(auth), "/companies-only", token)
    assert response.status_code == 200
    assert response.json() == {"id": 3, "role": "company"}


async def test_require_role_forbids_other_roles(auth: JWTAuth):
    token = auth.create_token(user_id=3, role=Role.STUDENT, name="Ana")
    response = await get(build_app(auth), "/companies-only", token)
    assert response.status_code == 403


async def test_missing_or_invalid_token_is_401(auth: JWTAuth):
    app = build_app(auth)
    assert (await get(app, "/companies-only")).status_code == 401
    assert (await get(app, "/companies-only", "bad.token.value")).status_code == 401


async def test_optional_principal(auth: JWTAuth):
    app = build_app(auth)
    token = auth.create_token(user_id=1, role=Role.STUDENT, name="Ana")
    assert (await get(app, "/optional", token)).json() == {"who": "Ana"}
    assert (await get(app, "/optional")).json() == {"who": None}
    assert (await get(app, "/optional", "bad")).json() == {"who": None}


async def test_missing_install_raises_runtime_error(auth: JWTAuth):
    token = auth.create_token(user_id=1, role=Role.COMPANY, name="x")
    with pytest.raises(RuntimeError):
        await get(build_app(None), "/companies-only", token)
