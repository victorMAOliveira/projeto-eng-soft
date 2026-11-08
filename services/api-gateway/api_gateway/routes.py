"""Routing table and coarse-grained role policy enforced at the edge.

Services enforce fine-grained authorisation again (defence in depth); the
gateway rejects obviously forbidden calls before they reach the network.
"""

import re
from dataclasses import dataclass, field

from eh_auth import Role

API_PREFIX = "/api"


@dataclass(frozen=True, slots=True)
class Route:
    """Requests under ``prefix`` go to ``service`` (with ``/api`` stripped)."""

    prefix: str
    service: str
    public: bool = False


@dataclass(frozen=True, slots=True)
class Policy:
    """Only ``roles`` may call ``method`` on paths fully matching ``pattern``."""

    method: str
    pattern: str
    roles: frozenset[Role] = field(default_factory=frozenset)

    def matches(self, method: str, path: str) -> bool:
        """``True`` when this policy applies to the request."""
        return self.method in ("*", method) and re.fullmatch(self.pattern, path) is not None


ROUTES: tuple[Route, ...] = (
    Route("/api/auth", "user-service", public=True),
    Route("/api/users", "user-service"),
    Route("/api/profiles", "user-service"),
    Route("/api/internships", "internship-service"),
    Route("/api/applications", "application-service"),
    Route("/api/placements", "application-service"),
    Route("/api/agreements", "document-service"),
    Route("/api/reports", "document-service"),
    Route("/api/notifications", "notification-service"),
    Route("/api/recommendations", "recommendation-service"),
    Route("/api/agents", "agent-service"),
)

S, C, K = Role.STUDENT, Role.COMPANY, Role.COORDINATOR

POLICIES: tuple[Policy, ...] = (
    Policy("POST", r"/api/internships", frozenset({C})),
    Policy("GET", r"/api/internships/mine", frozenset({C})),
    Policy("POST", r"/api/internships/\d+/close", frozenset({C, K})),
    Policy("PUT", r"/api/profiles/students/me", frozenset({S})),
    Policy("PUT", r"/api/profiles/companies/me", frozenset({C})),
    Policy("POST", r"/api/applications", frozenset({S})),
    Policy("POST", r"/api/applications/\d+/(review|approve|reject)", frozenset({C})),
    Policy("POST", r"/api/applications/\d+/withdraw", frozenset({S})),
    Policy("POST", r"/api/applications/\d+/(complete|terminate)", frozenset({C, K})),
    Policy("POST", r"/api/agreements/[\w-]+/approve", frozenset({K})),
    Policy("POST", r"/api/reports(/[\w-]+/versions)?", frozenset({S})),
    Policy("POST", r"/api/reports/[\w-]+/review", frozenset({K})),
    Policy("GET", r"/api/recommendations/students/\d+/internships", frozenset({S, K})),
    Policy("GET", r"/api/recommendations/internships/\d+/candidates", frozenset({C, K})),
    Policy("POST", r"/api/recommendations/rebuild", frozenset({K})),
    Policy("*", r"/api/agents/application-assistant(/.*)?", frozenset({S})),
    Policy("*", r"/api/agents/screening(/.*)?", frozenset({C})),
    Policy("*", r"/api/agents/follow-up(/.*)?", frozenset({K})),
)


def resolve_route(path: str) -> Route | None:
    """Return the route serving ``path`` (longest prefix wins) or ``None``."""
    candidates = [r for r in ROUTES if path == r.prefix or path.startswith(r.prefix + "/")]
    return max(candidates, key=lambda r: len(r.prefix), default=None)


def allowed_roles(method: str, path: str) -> frozenset[Role] | None:
    """Roles allowed by the first matching policy; ``None`` = any authenticated user."""
    for policy in POLICIES:
        if policy.matches(method, path):
            return policy.roles
    return None


def upstream_path(path: str) -> str:
    """Strip the public ``/api`` prefix: ``/api/internships/1`` -> ``/internships/1``."""
    return path[len(API_PREFIX) :] or "/"
