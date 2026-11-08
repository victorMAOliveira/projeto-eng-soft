"""eh_auth — authentication and authorisation shared by EstágioHub services.

Public interface:

* :class:`JWTAuth` — issue and validate HS256 JWTs (user and service tokens).
* :class:`Principal` / :class:`Role` — the authenticated caller.
* :func:`hash_password` / :func:`verify_password` — argon2id password hashing.
* :func:`install_auth`, :func:`get_current_principal`, :func:`require_role` —
  FastAPI dependencies enforcing authentication and role-based access.
* :class:`TokenError` — raised for missing, expired or tampered tokens.
"""

from eh_auth.dependencies import (
    get_current_principal,
    get_optional_principal,
    install_auth,
    require_role,
)
from eh_auth.passwords import hash_password, needs_rehash, verify_password
from eh_auth.tokens import JWTAuth, Principal, Role, TokenError

__version__ = "0.1.0"

__all__ = [
    "JWTAuth",
    "Principal",
    "Role",
    "TokenError",
    "get_current_principal",
    "get_optional_principal",
    "hash_password",
    "install_auth",
    "needs_rehash",
    "require_role",
    "verify_password",
]
