"""FastAPI integration: authentication dependency and role guard."""

from collections.abc import Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from eh_auth.tokens import JWTAuth, Principal, Role, TokenError

_bearer = HTTPBearer(auto_error=False)


def install_auth(app: FastAPI, auth: JWTAuth) -> None:
    """Make ``auth`` available to the dependencies of ``app``."""
    app.state.auth = auth


def _auth_from(request: Request) -> JWTAuth:
    auth = getattr(request.app.state, "auth", None)
    if auth is None:
        raise RuntimeError("eh_auth.install_auth(app, auth) was not called")
    return auth


async def get_optional_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal | None:
    """Return the caller if a valid bearer token is present, otherwise ``None``."""
    if credentials is None:
        return None
    try:
        return _auth_from(request).decode(credentials.credentials)
    except TokenError:
        return None


async def get_current_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    """Return the authenticated caller or respond ``401 Unauthorized``."""
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Autenticação necessária",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return _auth_from(request).decode(credentials.credentials)
    except TokenError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_role(*roles: Role | str) -> Callable[..., Awaitable[Principal]]:
    """Build a dependency that only lets callers with one of ``roles`` through.

    Example::

        @router.post("/internships")
        async def create(principal: Principal = Depends(require_role(Role.COMPANY))): ...

    Responds ``401`` without a valid token and ``403`` for other roles.
    """
    allowed = frozenset(Role(r) for r in roles)

    async def dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Seu papel não tem permissão para esta operação",
            )
        return principal

    return dependency
