"""Tools available to the agents.

Guardrail: every tool **reads** data, **suggests** or **notifies**. There is
no tool (and no HTTP client method) able to change an application's status —
decisions are always human. ``MUTATING_TOOLS`` lists the only side effects.
"""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import httpx

from eh_auth import JWTAuth, Principal, Role
from eh_db import Database
from eh_events import EventType, Publisher, ReportDueSoon
from eh_http import CircuitOpenError, ResilientClient, UpstreamUnavailableError
from eh_observability import CORRELATION_HEADER, get_correlation_id

LIMIT_WARNING_DAYS = 60
MUTATING_TOOLS = frozenset({"send_notification", "check_deadlines"})  # notify only


class ToolError(Exception):
    """A tool could not complete (returned to the model as ``is_error``)."""


@dataclass
class Services:
    """Resilient clients for the services the tools read from."""

    urls: dict[str, str]
    transport: httpx.AsyncBaseTransport | None = None
    clients: dict[str, ResilientClient] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, url in self.urls.items():
            self.clients[name] = ResilientClient(
                url,
                name=name,
                timeout=8.0,
                retries=1,
                header_provider=lambda: {CORRELATION_HEADER: get_correlation_id()},
                transport=self.transport,
            )

    async def call(self, service: str, method: str, path: str, token: str, **kwargs: Any) -> Any:
        """Call ``service`` and return the JSON body (raises :class:`ToolError`)."""
        try:
            response = await self.clients[service].request(
                method, path, headers={"Authorization": f"Bearer {token}"}, **kwargs
            )
        except (CircuitOpenError, UpstreamUnavailableError) as exc:
            raise ToolError(f"{service} indisponível") from exc
        if response.status_code >= 400:
            raise ToolError(f"{service} respondeu {response.status_code}: {response.text[:200]}")
        return response.json()

    async def aclose(self) -> None:
        """Close all clients."""
        for client in self.clients.values():
            await client.aclose()


@dataclass
class ToolContext:
    """Who is running the agent and how to reach the platform."""

    principal: Principal
    user_token: str
    auth: JWTAuth
    services: Services
    db: Database
    publisher: Publisher
    today: date = field(default_factory=date.today)

    @property
    def service_token(self) -> str:
        """Short-lived internal token (used by the follow-up agent)."""
        return self.auth.create_service_token("agent-service")

    def own_student_id(self, requested: int | None) -> int:
        """Students may only look at themselves."""
        if self.principal.role == Role.STUDENT:
            return self.principal.id
        if requested is None:
            raise ToolError("student_id é obrigatório")
        return int(requested)


Handler = Callable[[ToolContext, dict[str, Any]], Awaitable[Any]]


@dataclass(frozen=True)
class Tool:
    """Tool definition shared by LLM mode (JSON schema) and rules mode (handler)."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Handler

    def to_anthropic(self) -> dict[str, Any]:
        """Definition in the Messages API ``tools`` format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


async def search_internships(ctx: ToolContext, args: dict[str, Any]) -> Any:
    """Search open offers (internship-service)."""
    params = {
        k: v
        for k, v in {
            "q": args.get("query"),
            "course": args.get("course"),
            "modality": args.get("modality"),
        }.items()
        if v
    }
    params["size"] = int(args.get("limit", 5))
    data = await ctx.services.call(
        "internship-service", "GET", "/internships", ctx.user_token, params=params
    )
    return [
        {
            k: v[k]
            for k in ("id", "title", "company_name", "course", "modality", "city", "requirements")
        }
        for v in data["items"]
    ]


async def get_recommendations(ctx: ToolContext, args: dict[str, Any]) -> Any:
    """Explainable recommendations (recommendation-service)."""
    student_id = ctx.own_student_id(args.get("student_id"))
    data = await ctx.services.call(
        "recommendation-service",
        "GET",
        f"/recommendations/students/{student_id}/internships",
        ctx.user_token,
        params={"k": int(args.get("k", 5)), "include_filtered": "true"},
    )
    keep = (
        "internship_id",
        "title",
        "company_name",
        "score",
        "matched_skills",
        "missing_skills",
        "explanation",
        "eliminated_by",
    )
    return {
        "strategy": data["strategy"],
        "items": [{k: i[k] for k in keep} for i in data["items"]],
        "filtered": [{k: i[k] for k in keep} for i in data["filtered"][:5]],
    }


async def get_profile(ctx: ToolContext, args: dict[str, Any]) -> Any:
    """Academic profile (user-service)."""
    student_id = ctx.own_student_id(args.get("student_id"))
    return await ctx.services.call(
        "user-service", "GET", f"/profiles/students/{student_id}", ctx.user_token
    )


async def get_candidate_ranking(ctx: ToolContext, args: dict[str, Any]) -> Any:
    """Ranking of an offer's applicants (recommendation-service)."""
    data = await ctx.services.call(
        "recommendation-service",
        "GET",
        f"/recommendations/internships/{int(args['internship_id'])}/candidates",
        ctx.user_token,
        params={"k": int(args.get("k", 10))},
    )
    keep = (
        "student_id",
        "name",
        "score",
        "matched_skills",
        "missing_skills",
        "explanation",
        "eliminated_by",
        "application_status",
    )
    return {
        "title": data["title"],
        "requirements": data["requirements"],
        "items": [{k: i[k] for k in keep} for i in data["items"]],
    }


async def list_active_internships(ctx: ToolContext, args: dict[str, Any]) -> Any:
    """Active internships with report deadlines (application-service, service token)."""
    return await ctx.services.call(
        "application-service", "GET", "/placements", ctx.service_token, params={"status": "active"}
    )


async def list_reports(ctx: ToolContext, args: dict[str, Any]) -> Any:
    """Submitted activity reports (document-service, service token)."""
    params = {"application_id": int(args["application_id"])} if args.get("application_id") else {}
    data = await ctx.services.call(
        "document-service", "GET", "/reports", ctx.service_token, params=params
    )
    return [
        {
            "id": r["id"],
            "application_id": r["application_id"],
            "title": r["title"],
            "status": r["status"],
            "versions": len(r["versions"]),
        }
        for r in data
    ]


async def _first_alert(ctx: ToolContext, key: str) -> bool:
    """Record an alert key; ``False`` if it was already sent (deduplication)."""
    from agent_service.models import AlertSent

    async with ctx.db.session() as session:
        if await session.get(AlertSent, key) is not None:
            return False
        session.add(AlertSent(key=key))
    return True


async def check_deadlines(ctx: ToolContext, args: dict[str, Any]) -> Any:
    """Detect reports due/overdue, 2-year limit and workload issues; publish ``report.due_soon``."""
    placements = await list_active_internships(ctx, {})
    alerts = []
    for p in placements:
        due = p.get("next_report_due")
        if due and p["report_state"] in ("due_soon", "overdue"):
            days = int(p["days_to_report"])
            alert = {
                "kind": "report_overdue" if days < 0 else "report_due_soon",
                "application_id": p["application_id"],
                "student_id": p["student_id"],
                "student_name": p["student_name"],
                "due_date": due,
                "days_left": days,
            }
            alert["published"] = await _first_alert(ctx, f"report:{p['application_id']}:{due}")
            if alert["published"]:
                await ctx.publisher.publish(
                    EventType.REPORT_DUE_SOON,
                    ReportDueSoon(
                        application_id=p["application_id"],
                        student_id=p["student_id"],
                        company_id=p["company_id"],
                        student_name=p["student_name"],
                        due_date=due,
                        days_left=days,
                        overdue=days < 0,
                    ),
                )
            alerts.append(alert)
        if p.get("max_end_date"):
            days_to_limit = (date.fromisoformat(p["max_end_date"]) - ctx.today).days
            if days_to_limit <= LIMIT_WARNING_DAYS:
                alerts.append(
                    {
                        "kind": "two_year_limit",
                        "application_id": p["application_id"],
                        "student_id": p["student_id"],
                        "student_name": p["student_name"],
                        "limit_date": p["max_end_date"],
                        "days_left": days_to_limit,
                    }
                )
        if p["hours_per_day"] > 6 or p["hours_per_week"] > 30:
            alerts.append(
                {
                    "kind": "workload",
                    "application_id": p["application_id"],
                    "student_id": p["student_id"],
                    "student_name": p["student_name"],
                    "hours_per_day": p["hours_per_day"],
                    "hours_per_week": p["hours_per_week"],
                }
            )
    return {"checked": len(placements), "alerts": alerts}


async def send_notification(ctx: ToolContext, args: dict[str, Any]) -> Any:
    """Notify a user or a role (notification-service). Allowed side effect."""
    body = {
        k: args[k]
        for k in ("user_id", "role", "title", "message", "kind", "link")
        if args.get(k) is not None
    }
    return await ctx.services.call(
        "notification-service", "POST", "/notifications", ctx.service_token, json=body
    )


TOOLS: dict[str, Tool] = {
    t.name: t
    for t in (
        Tool(
            "search_internships",
            "Busca vagas abertas por texto, curso ou modalidade.",
            _schema(
                {
                    "query": {"type": "string"},
                    "course": {"type": "string"},
                    "modality": {"type": "string", "enum": ["onsite", "remote", "hybrid"]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 10},
                }
            ),
            search_internships,
        ),
        Tool(
            "get_recommendations",
            "Recomendações explicáveis de vagas para o estudante (habilidades em comum, faltantes e filtros).",
            _schema(
                {
                    "student_id": {"type": "integer"},
                    "k": {"type": "integer", "minimum": 1, "maximum": 10},
                }
            ),
            get_recommendations,
        ),
        Tool(
            "get_profile",
            "Perfil acadêmico do estudante (curso, período, habilidades, resumo).",
            _schema({"student_id": {"type": "integer"}}),
            get_profile,
        ),
        Tool(
            "get_candidate_ranking",
            "Ranking dos candidatos de uma vaga calculado pelo recommendation-service, com justificativas.",
            _schema(
                {"internship_id": {"type": "integer"}, "k": {"type": "integer"}}, ["internship_id"]
            ),
            get_candidate_ranking,
        ),
        Tool(
            "list_active_internships",
            "Lista estágios ativos com prazos do relatório semestral.",
            _schema({}),
            list_active_internships,
        ),
        Tool(
            "list_reports",
            "Lista relatórios de atividades enviados (opcionalmente de um estágio).",
            _schema({"application_id": {"type": "integer"}}),
            list_reports,
        ),
        Tool(
            "check_deadlines",
            "Verifica relatórios a vencer/vencidos, limite de 2 anos e jornada; publica report.due_soon.",
            _schema({}),
            check_deadlines,
        ),
        Tool(
            "send_notification",
            "Envia uma notificação a um usuário (user_id) ou a um papel (role).",
            _schema(
                {
                    "user_id": {"type": "integer"},
                    "role": {"type": "string", "enum": ["student", "company", "coordinator"]},
                    "title": {"type": "string"},
                    "message": {"type": "string"},
                    "kind": {"type": "string", "enum": ["info", "success", "warning"]},
                },
                ["title", "message"],
            ),
            send_notification,
        ),
    )
}


def preview(value: Any, limit: int = 2000) -> Any:
    """Truncate large tool outputs before storing them in the trail."""
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= limit:
        return value
    return {"truncated": True, "preview": text[:limit]}
