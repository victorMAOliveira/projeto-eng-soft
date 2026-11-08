"""HTTP API of the agent-service."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from agent_service.agents import AGENTS
from agent_service.models import AgentRun
from agent_service.runner import AgentRunner, run_to_dict
from agent_service.tools import ToolContext
from eh_auth import Principal, Role, get_current_principal, require_role

router = APIRouter(tags=["agents"])


class AssistantIn(BaseModel):
    """Input of the application assistant."""

    internship_id: int | None = None
    question: str | None = Field(default=None, max_length=500)


class ScreeningIn(BaseModel):
    """Input of the screening agent."""

    internship_id: int


def context(request: Request, principal: Principal) -> ToolContext:
    """Tool context for the caller (their token is forwarded to the services)."""
    state = request.app.state
    token = request.headers.get("authorization", "").partition(" ")[2]
    return ToolContext(principal, token, state.auth, state.services, state.db, state.publisher)


def runner_dep(request: Request) -> AgentRunner:
    """Agent runner configured at startup."""
    return request.app.state.runner


@router.get("/agents/status", summary="Modo dos agentes (IA ou regras), modelo e agendamento")
async def agents_status(
    request: Request, _: Principal = Depends(get_current_principal)
) -> dict[str, Any]:
    """Tells the UI whether to show the "IA em modo regras" badge."""
    runner: AgentRunner = request.app.state.runner
    job = request.app.state.scheduler_job
    return {
        "mode": runner.mode,
        "model": runner.model,
        "max_steps": runner.max_steps,
        "timeout_seconds": runner.timeout_seconds,
        "agents": {
            name: {"title": spec.title, "tools": list(spec.tools)} for name, spec in AGENTS.items()
        },
        "follow_up_schedule": {
            "interval_minutes": request.app.state.settings.followup_interval_minutes,
            "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
        },
    }


@router.post(
    "/agents/application-assistant/run",
    summary="Assistente de Candidatura (estudante)",
)
async def run_assistant(
    body: AssistantIn,
    request: Request,
    principal: Principal = Depends(require_role(Role.STUDENT)),
    runner: AgentRunner = Depends(runner_dep),
) -> dict[str, Any]:
    """Explain the match, suggest profile improvements and draft a cover letter."""
    run = await runner.run("application_assistant", context(request, principal), body.model_dump())
    return run_to_dict(run)


@router.post("/agents/screening/run", summary="Agente de Triagem (empresa)")
async def run_screening(
    body: ScreeningIn,
    request: Request,
    principal: Principal = Depends(require_role(Role.COMPANY)),
    runner: AgentRunner = Depends(runner_dep),
) -> dict[str, Any]:
    """Summarise the candidate ranking of one offer."""
    run = await runner.run("screening", context(request, principal), body.model_dump())
    return run_to_dict(run)


@router.post("/agents/follow-up/run", summary="Agente de Acompanhamento sob demanda (coordenação)")
async def run_follow_up(
    request: Request,
    principal: Principal = Depends(require_role(Role.COORDINATOR)),
    runner: AgentRunner = Depends(runner_dep),
) -> dict[str, Any]:
    """Check deadlines now (the same agent also runs on a schedule)."""
    run = await runner.run("follow_up", context(request, principal), {"trigger": "on_demand"})
    return run_to_dict(run)


@router.get("/agents/runs", summary="Histórico de execuções")
async def list_runs(
    request: Request,
    agent: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    principal: Principal = Depends(get_current_principal),
) -> list[dict[str, Any]]:
    """The caller's runs (coordination also sees scheduled follow-up runs)."""
    stmt = select(AgentRun).order_by(AgentRun.id.desc()).limit(limit)
    if principal.role == Role.COORDINATOR:
        stmt = stmt.where((AgentRun.user_id == principal.id) | (AgentRun.agent == "follow_up"))
    elif principal.role != Role.SERVICE:
        stmt = stmt.where(
            AgentRun.user_id == principal.id, AgentRun.user_role == principal.role.value
        )
    if agent:
        stmt = stmt.where(AgentRun.agent == agent)
    async with request.app.state.db.session() as session:
        return [run_to_dict(r) for r in (await session.scalars(stmt)).all()]


@router.get("/agents/runs/{run_id}", summary="Execução com a trilha de ferramentas")
async def get_run(
    run_id: int, request: Request, principal: Principal = Depends(get_current_principal)
) -> dict[str, Any]:
    """One run and its execution trail."""
    async with request.app.state.db.session() as session:
        run = await session.get(AgentRun, run_id)
        if run is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Execução não encontrada")
        visible = (
            run.user_id == principal.id
            or principal.role in (Role.SERVICE,)
            or (principal.role == Role.COORDINATOR and run.agent == "follow_up")
        )
        if not visible:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Execução de outro usuário")
        return run_to_dict(run)
