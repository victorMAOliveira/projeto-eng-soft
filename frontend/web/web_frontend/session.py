"""Browser session: the JWT lives in an HttpOnly cookie.

The frontend never validates the token itself (it does not know the secret);
it only reads the claims to render the right menu. Every data access goes
through the gateway, which validates the token on each call.
"""

import base64
import json
import time
from dataclasses import dataclass

from fastapi import Request

TOKEN_COOKIE = "eh_token"
SHOW_SERVICES_COOKIE = "eh_show_services"
FLASH_COOKIE = "eh_flash"

ROLE_LABELS = {"student": "Estudante", "company": "Empresa", "coordinator": "Coordenação"}


@dataclass(frozen=True, slots=True)
class SessionUser:
    """The logged-in user as described by the token claims."""

    id: int
    role: str
    name: str
    email: str | None
    token: str

    @property
    def role_label(self) -> str:
        """Portuguese label of the role."""
        return ROLE_LABELS.get(self.role, self.role)

    @property
    def first_name(self) -> str:
        """First word of the name, for greetings."""
        return self.name.split(" ")[0] if self.name else ""


def decode_claims(token: str) -> dict | None:
    """Decode (without verifying) the JWT payload; ``None`` if malformed or expired."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError):
        return None
    if claims.get("exp", 0) < time.time():
        return None
    return claims


def current_user(request: Request) -> SessionUser | None:
    """Return the user stored in the session cookie, if any."""
    token = request.cookies.get(TOKEN_COOKIE)
    claims = decode_claims(token) if token else None
    if not claims:
        return None
    return SessionUser(
        id=int(claims["sub"]),
        role=claims.get("role", ""),
        name=claims.get("name", ""),
        email=claims.get("email"),
        token=token,
    )
