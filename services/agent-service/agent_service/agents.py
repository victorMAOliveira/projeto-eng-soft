"""The three agents: definitions, prompts and their deterministic rules mode.

Each agent has the same API in both modes. In LLM mode Claude chooses which
tools to call; in rules mode a fixed plan calls the same tools and composes
the answer from templates. Either way every tool call lands in the trail.
"""

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from agent_service.tools import TOOLS, ToolContext, ToolError, preview
from eh_auth import Role


class StepLimitExceededError(Exception):
    """The run tried to go beyond the configured number of steps."""


@dataclass
class Trail:
    """Executes tools for a run and records every step (the "execution trail")."""

    ctx: ToolContext
    allowed: tuple[str, ...]
    max_tool_calls: int
    steps: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: int = 0

    def record(self, kind: str, **data: Any) -> dict[str, Any]:
        """Append a step to the trail."""
        step = {
            "position": len(self.steps) + 1,
            "kind": kind,
            "tool_name": None,
            "tool_input": None,
            "tool_output": None,
            "ok": True,
            "duration_ms": 0.0,
            **data,
        }
        self.steps.append(step)
        return step

    async def call(self, name: str, args: dict[str, Any] | None = None) -> Any:
        """Run tool ``name`` (must be allowed for this agent) and record it."""
        args = dict(args or {})
        if name not in self.allowed:
            self.record(
                "tool_call",
                tool_name=name,
                tool_input=args,
                ok=False,
                tool_output={"error": "ferramenta não permitida para este agente"},
            )
            raise ToolError(f"ferramenta {name} não permitida")
        if self.tool_calls >= self.max_tool_calls:
            raise StepLimitExceededError(f"limite de {self.max_tool_calls} chamadas de ferramenta")
        self.tool_calls += 1
        started = time.perf_counter()
        try:
            result = await TOOLS[name].handler(self.ctx, args)
        except ToolError as exc:
            self.record(
                "tool_call",
                tool_name=name,
                tool_input=args,
                ok=False,
                tool_output={"error": str(exc)},
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
            raise
        self.record(
            "tool_call",
            tool_name=name,
            tool_input=args,
            tool_output=preview(result),
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return result

    async def try_call(self, name: str, args: dict[str, Any] | None = None) -> Any:
        """Like :meth:`call` but returns ``None`` on tool failure (graceful degradation)."""
        try:
            return await self.call(name, args)
        except ToolError:
            return None


@dataclass
class AgentOutput:
    """Final answer of a run."""

    text: str
    cover_letter: str | None = None


@dataclass(frozen=True)
class AgentSpec:
    """Static description of an agent."""

    name: str
    title: str
    roles: frozenset[Role]
    tools: tuple[str, ...]
    system_prompt: str
    build_prompt: Callable[[ToolContext, dict[str, Any]], str]
    rules: Callable[[Trail, dict[str, Any]], Awaitable[AgentOutput]]


# ------------------------------------------------------------ application assistant
def _pick_target(recs: dict | None, internship_id: int | None) -> dict | None:
    if not recs:
        return None
    pool = recs.get("items", []) + recs.get("filtered", [])
    if internship_id is not None:
        return next((r for r in pool if r["internship_id"] == internship_id), None)
    return recs["items"][0] if recs.get("items") else None


def _profile_tips(profile: dict | None, target: dict | None) -> list[str]:
    tips = []
    if target and target.get("missing_skills"):
        tips.append(
            "Para esta vaga, desenvolva ou declare (se já tiver): "
            + ", ".join(target["missing_skills"])
            + "."
        )
    if profile:
        if len(profile.get("skills") or []) < 5:
            tips.append("Liste ao menos 5 habilidades técnicas e comportamentais no perfil.")
        if len(profile.get("resume_summary") or "") < 80:
            tips.append("Escreva um resumo de 2–3 frases com seus interesses e projetos.")
        if not profile.get("preferred_modality"):
            tips.append("Informe a modalidade preferida (presencial, remoto ou híbrido).")
    return tips or ["Seu perfil está completo — mantenha as habilidades atualizadas."]


def cover_letter(profile: dict | None, target: dict) -> str:
    """Draft cover letter the student edits before sending."""
    name = (profile or {}).get("name", "")
    course = (profile or {}).get("course") or "meu curso"
    semester = (profile or {}).get("semester")
    skills = target.get("matched_skills") or (profile or {}).get("skills", [])[:3]
    missing = target.get("missing_skills") or []
    learning = ", ".join(missing[:2]) if missing else "novas tecnologias e práticas do time"
    period = f"do {semester}º período de " if semester else "de "
    return (
        f"Prezada equipe da {target['company_name']},\n\n"
        f"Sou {name}, estudante {period}{course} na Universidade Federal de Alagoas, e gostaria de "
        f"me candidatar à vaga de {target['title']}. "
        + (
            f"Tenho experiência com {', '.join(skills)}, que se alinha aos requisitos da vaga. "
            if skills
            else ""
        )
        + f"Tenho interesse em aprender {learning} durante o estágio e contribuir com o time.\n\n"
        "Fico à disposição para uma conversa.\n\n"
        f"Atenciosamente,\n{name}"
    )


async def assistant_rules(trail: Trail, params: dict[str, Any]) -> AgentOutput:
    """Profile → recommendations → explanation, tips and cover letter draft."""
    profile = await trail.try_call("get_profile", {})
    recs = await trail.try_call("get_recommendations", {"k": 5})
    target = _pick_target(recs, params.get("internship_id"))
    lines = []
    if recs is None:
        lines.append(
            "O serviço de recomendação está indisponível agora; mostrando vagas pela busca."
        )
        found = await trail.try_call(
            "search_internships", {"query": params.get("question") or "", "limit": 3}
        )
        for v in found or []:
            lines.append(
                f"• {v['title']} — {v['company_name']} ({', '.join(v['requirements'][:3])})"
            )
    elif target is None:
        lines.append(
            "Não encontrei uma vaga compatível para analisar. Complete o perfil e tente novamente."
        )
    else:
        lines.append(f"POR QUE “{target['title']}” ({target['company_name']}) COMBINA COM VOCÊ")
        if target.get("eliminated_by"):
            lines.append(
                "Atenção: esta vaga não passa nos filtros — " + " ".join(target["eliminated_by"])
            )
        else:
            lines.append(
                f"Score de compatibilidade: {target['score']:.0%}. {target['explanation']}"
            )
    lines.append("")
    lines.append("COMO MELHORAR SEU PERFIL")
    lines += [f"• {tip}" for tip in _profile_tips(profile, target)]
    letter = cover_letter(profile, target) if target else None
    if letter:
        lines += ["", "RASCUNHO DE CARTA DE MOTIVAÇÃO", "(edite antes de enviar)"]
    return AgentOutput("\n".join(lines), letter)


def assistant_prompt(ctx: ToolContext, params: dict[str, Any]) -> str:
    """User message for the application assistant (LLM mode)."""
    target = (
        f"Analise a vaga de id {params['internship_id']}."
        if params.get("internship_id")
        else "Analise a vaga mais recomendada."
    )
    question = f"\nPergunta do estudante: {params['question']}" if params.get("question") else ""
    return (
        f"Sou o(a) estudante {ctx.principal.name} (id {ctx.principal.id}). {target}{question}\n"
        "Responda em português com três seções: (1) por que a vaga combina comigo, citando "
        "habilidades em comum e faltantes; (2) como melhorar meu perfil; (3) um rascunho curto de "
        "carta de motivação entre as tags <carta> e </carta>."
    )


# --------------------------------------------------------------------- screening
async def screening_rules(trail: Trail, params: dict[str, Any]) -> AgentOutput:
    """Summarise the recommendation-service ranking with justifications."""
    ranking = await trail.call(
        "get_candidate_ranking", {"internship_id": int(params["internship_id"]), "k": 10}
    )
    items = ranking["items"]
    eligible = [i for i in items if not i["eliminated_by"]]
    lines = [
        f"TRIAGEM — {ranking['title']}",
        f"{len(items)} candidatura(s); {len(eligible)} atendem aos filtros.",
        "",
    ]
    for pos, item in enumerate(eligible[:3], start=1):
        lines.append(f"{pos}. {item['name']} — score {item['score']:.0%}. {item['explanation']}")
    for item in [i for i in items if i["eliminated_by"]]:
        lines.append(f"• {item['name']}: não atende — {' '.join(item['eliminated_by'])}")
    if not items:
        lines.append("Ainda não há candidaturas para esta vaga.")
    lines += [
        "",
        "A decisão de aprovar ou rejeitar é sempre da empresa: o agente não altera candidaturas.",
    ]
    return AgentOutput("\n".join(lines))


def screening_prompt(ctx: ToolContext, params: dict[str, Any]) -> str:
    """User message for the screening agent (LLM mode)."""
    return (
        f"Faça a triagem dos candidatos da vaga {params['internship_id']}: resuma o ranking do "
        "recommendation-service com justificativas (habilidades em comum e faltantes), destaque os 3 "
        "melhores e quem não atende aos filtros. Lembre que a decisão é humana."
    )


# --------------------------------------------------------------------- follow-up
async def followup_rules(trail: Trail, params: dict[str, Any]) -> AgentOutput:
    """Active internships → deadlines → notify coordination about limits/workload."""
    placements = await trail.call("list_active_internships", {})
    result = await trail.call("check_deadlines", {})
    alerts = result["alerts"]
    reports = [a for a in alerts if a["kind"].startswith("report_")]
    other = [a for a in alerts if not a["kind"].startswith("report_")]
    lines = [f"ACOMPANHAMENTO — {len(placements)} estágio(s) ativo(s) verificados.", ""]
    if reports:
        lines.append(
            "Relatórios semestrais (evento report.due_soon publicado para os novos alertas):"
        )
        for a in reports:
            when = (
                f"vencido há {-a['days_left']} dia(s)"
                if a["days_left"] < 0
                else f"vence em {a['days_left']} dia(s)"
            )
            lines.append(
                f"• {a['student_name']}: {when} ({a['due_date']}){'' if a['published'] else ' — já alertado'}"
            )
    for a in other:
        if a["kind"] == "two_year_limit":
            lines.append(
                f"• {a['student_name']}: limite de 2 anos na concedente em {a['days_left']} dia(s) ({a['limit_date']})."
            )
        else:
            lines.append(
                f"• {a['student_name']}: jornada acima do permitido ({a['hours_per_day']} h/dia, {a['hours_per_week']} h/sem)."
            )
    if other:
        await trail.try_call(
            "send_notification",
            {
                "role": "coordinator",
                "kind": "warning",
                "title": "Alertas do agente de acompanhamento",
                "message": f"{len(other)} estágio(s) exigem atenção (limite de 2 anos ou jornada).",
            },
        )
    if not alerts:
        lines.append("Nenhum prazo crítico encontrado.")
    return AgentOutput("\n".join(lines))


def followup_prompt(ctx: ToolContext, params: dict[str, Any]) -> str:
    """User message for the follow-up agent (LLM mode)."""
    return (
        "Verifique os estágios ativos: use check_deadlines para detectar relatórios a vencer ou "
        "vencidos, termos perto do limite de 2 anos e jornada acima do permitido. Se houver alertas "
        "de limite ou jornada, envie UMA notificação resumida para a coordenação. Termine com um "
        "relatório curto em português."
    )


SYSTEM_BASE = (
    "Você é um agente do EstágioHub, sistema de gestão de estágios regido pela Lei nº 11.788/2008. "
    "Use apenas as ferramentas fornecidas e os dados que elas retornam; não invente vagas, pessoas "
    "ou números. Você só lê dados, sugere e notifica: nunca altera o status de candidaturas — a "
    "decisão é sempre humana. Responda em português do Brasil, de forma objetiva."
)

AGENTS: dict[str, AgentSpec] = {
    spec.name: spec
    for spec in (
        AgentSpec(
            "application_assistant",
            "Assistente de Candidatura",
            frozenset({Role.STUDENT}),
            ("search_internships", "get_recommendations", "get_profile"),
            SYSTEM_BASE
            + " Você ajuda estudantes a entender por que uma vaga combina com o perfil.",
            assistant_prompt,
            assistant_rules,
        ),
        AgentSpec(
            "follow_up",
            "Agente de Acompanhamento",
            frozenset({Role.COORDINATOR, Role.SERVICE}),
            ("list_active_internships", "list_reports", "check_deadlines", "send_notification"),
            SYSTEM_BASE + " Você apoia a coordenação de estágio no controle de prazos.",
            followup_prompt,
            followup_rules,
        ),
        AgentSpec(
            "screening",
            "Agente de Triagem",
            frozenset({Role.COMPANY}),
            ("get_candidate_ranking",),
            SYSTEM_BASE + " Você resume rankings de candidatos para empresas concedentes.",
            screening_prompt,
            screening_rules,
        ),
    )
}
