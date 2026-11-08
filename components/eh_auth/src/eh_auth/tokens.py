"""JWT issuing/validation and the :class:`Principal` model."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import jwt

MIN_SECRET_LENGTH = 32


class Role(StrEnum):
    """Roles recognised by EstágioHub. ``service`` is used for internal calls."""

    STUDENT = "student"
    COMPANY = "company"
    COORDINATOR = "coordinator"
    SERVICE = "service"


class TokenError(Exception):
    """The token is missing, malformed, expired or signed with another key."""


@dataclass(frozen=True, slots=True)
class Principal:
    """The authenticated caller extracted from a validated JWT."""

    id: int
    role: Role
    name: str
    email: str | None = None

    @property
    def is_service(self) -> bool:
        """``True`` for internal service-to-service tokens."""
        return self.role is Role.SERVICE


class JWTAuth:
    """Create and validate HS256 JSON Web Tokens.

    Args:
        secret: Shared signing key (at least 32 characters).
        algorithm: JWS algorithm, ``HS256`` by default.
        expires_minutes: Default lifetime of user tokens.
        issuer: Value of the ``iss`` claim, verified on decode.
    """

    def __init__(
        self,
        secret: str,
        *,
        algorithm: str = "HS256",
        expires_minutes: int = 120,
        issuer: str = "estagiohub",
    ) -> None:
        if not secret or len(secret) < MIN_SECRET_LENGTH:
            raise ValueError(f"JWT secret must have at least {MIN_SECRET_LENGTH} characters")
        self._secret = secret
        self.algorithm = algorithm
        self.expires_minutes = expires_minutes
        self.issuer = issuer

    def create_token(
        self,
        *,
        user_id: int,
        role: Role | str,
        name: str,
        email: str | None = None,
        expires_minutes: int | None = None,
    ) -> str:
        """Return a signed token for ``user_id`` with the given role."""
        now = datetime.now(UTC)
        lifetime = timedelta(minutes=expires_minutes or self.expires_minutes)
        claims = {
            "sub": str(user_id),
            "role": Role(role).value,
            "name": name,
            "email": email,
            "iss": self.issuer,
            "iat": now,
            "exp": now + lifetime,
        }
        return jwt.encode(claims, self._secret, algorithm=self.algorithm)

    def create_service_token(self, service_name: str, expires_minutes: int = 10) -> str:
        """Return a short-lived token identifying an internal service."""
        return self.create_token(
            user_id=0, role=Role.SERVICE, name=service_name, expires_minutes=expires_minutes
        )

    def decode(self, token: str) -> Principal:
        """Validate ``token`` and return its :class:`Principal`.

        Raises:
            TokenError: if the signature, expiry, issuer or claims are invalid.
        """
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[self.algorithm],
                issuer=self.issuer,
                options={"require": ["sub", "role", "exp", "iss"]},
            )
            return Principal(
                id=int(claims["sub"]),
                role=Role(claims["role"]),
                name=claims.get("name") or "",
                email=claims.get("email"),
            )
        except (jwt.PyJWTError, ValueError, KeyError) as exc:
            raise TokenError(str(exc)) from exc
