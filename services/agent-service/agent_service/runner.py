"""Runs agents in LLM mode (Claude tool use) or rules mode and persists the trail."""

import asyncio
import json
import logging
import re
import time
from datetime import UTC, datetime
from typing import Any, Protocol

import anthropic

from agent_service.agents import AGENTS, AgentOutput, AgentSpec, StepLimitExceededError, Trail
from agent_service.models import AgentRun, AgentStep
from agent_service.tools import TOOLS, ToolContext, ToolError

logger = logging.getLogger("agent-service.runner")
LETTER_RE = re.compile(r"<carta>(.*?)</carta>", re.DOTALL)


class LlmClient(Protocol):
    """What the runner needs from an LLM client (mocked in tests)."""

    async def create(self, **kwargs: Any) -> Any:
        """Call the Messages API and return the response."""
        ...


class AnthropicLlm:
    """:class:`LlmClient` backed by the official Anthropic SDK (async)."""

    def __init__(self, api_key: str, timeout: float = 30.0) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout, max_retries=2)

    async def create(self, **kwargs: Any) -> Any:
        """``client.messages.create`` passthrough."""
        return await self.client.messages.create(**kwargs)


class LlmUnavailableError(Exception):
    """The model could not produce an answer (refusal, API error...)."""


async def run_llm(
    spec: AgentSpec,
    trail: Trail,
    prompt: str,
    llm: LlmClient,
    model: str,
    max_steps: int,
) -> AgentOutput:
    """Manual tool-use loop limited to ``max_steps`` model calls.

    Every model call and tool call is recorded in ``trail``. Thinking/tool_use
    blocks are sent back unchanged (``response.content``).
    """
    tools = [TOOLS[name].to_anthropic() for name in spec.tools]
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    for _ in range(max_steps):
        started = time.perf_counter()
        response = await llm.create(
            model=model,
            max_tokens=8000,
            system=spec.system_prompt,
            tools=tools,
            output_config={"effort": "medium"},
            messages=messages,
        )
        trail.record(
            "llm",
            tool_output={"stop_reason": response.stop_reason, "model": model},
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        if response.stop_reason == "refusal":
            raise LlmUnavailableError("o modelo recusou a solicitação")
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if response.stop_reason != "tool_use" or not tool_uses:
            text = "".join(b.text for b in response.content if b.type == "text").strip()
            match = LETTER_RE.search(text)
            letter = match.group(1).strip() if match else None
            return AgentOutput(LETTER_RE.sub("", text).strip(), letter)
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in tool_uses:
            try:
                output = await trail.call(block.name, dict(block.input))
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(output, ensure_ascii=False, default=str),
                    }
                )
            except ToolError as exc:
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Erro: {exc}",
                        "is_error": True,
                    }
                )
        messages.append({"role": "user", "content": results})
    raise StepLimitExceededError(f"limite de {max_steps} passos atingido")


class AgentRunner:
    """Chooses the mode, applies guardrails (steps, timeout) and stores the run."""

    def __init__(
        self,
        *,
        llm: LlmClient | None,
        model: str,
        max_steps: int = 6,
        timeout_seconds: float = 45.0,
    ) -> None:
        self.llm = llm
        self.model = model
        self.max_steps = max_steps
        self.timeout_seconds = timeout_seconds

    @property
    def mode(self) -> str:
        """``llm`` with an API key configured, otherwise ``rules``."""
        return "llm" if self.llm is not None else "rules"

    async def run(self, agent: str, ctx: ToolContext, params: dict[str, Any]) -> AgentRun:
        """Execute ``agent`` and persist the run with its trail."""
        spec = AGENTS[agent]
        trail = Trail(
            ctx, spec.tools, max_tool_calls=self.max_steps * 2 if self.llm else self.max_steps
        )
        mode, error, status = self.mode, None, "completed"
        output = AgentOutput("")
        try:
            if self.llm is not None:
                try:
                    output = await asyncio.wait_for(
                        run_llm(
                            spec,
                            trail,
                            spec.build_prompt(ctx, params),
                            self.llm,
                            self.model,
                            self.max_steps,
                        ),
                        timeout=self.timeout_seconds,
                    )
                except (
                    LlmUnavailableError,
                    StepLimitExceededError,
                    TimeoutError,
                    anthropic.APIError,
                ) as exc:
                    logger.warning(
                        "LLM mode failed, falling back to rules", extra={"error": str(exc)}
                    )
                    error = f"IA indisponível ({type(exc).__name__}: {exc}); resposta gerada em modo regras."
                    mode = "rules"
                    trail.tool_calls = 0
                    trail.max_tool_calls = self.max_steps
                    output = await spec.rules(trail, params)
            else:
                output = await spec.rules(trail, params)
        except (ToolError, StepLimitExceededError) as exc:
            status, error = "failed", str(exc)
            output = AgentOutput(f"Não foi possível concluir a execução: {exc}")
        trail.record("final", tool_output={"status": status, "mode": mode})
        run = AgentRun(
            agent=agent,
            user_id=ctx.principal.id,
            user_role=ctx.principal.role.value,
            mode=mode,
            model=self.model if mode == "llm" else None,
            input=params,
            output=output.text,
            cover_letter=output.cover_letter,
            status=status,
            steps_count=sum(1 for s in trail.steps if s["kind"] != "final"),
            error=error,
            finished_at=datetime.now(UTC),
            steps=[AgentStep(**step) for step in trail.steps],
        )
        async with ctx.db.session() as session:
            session.add(run)
        return run


def run_to_dict(run: AgentRun) -> dict[str, Any]:
    """API representation of a run, with its execution trail."""
    return {
        "id": run.id,
        "agent": run.agent,
        "title": AGENTS[run.agent].title,
        "user_id": run.user_id,
        "mode": run.mode,
        "model": run.model,
        "status": run.status,
        "input": run.input,
        "output": run.output,
        "cover_letter": run.cover_letter,
        "error": run.error,
        "steps_count": run.steps_count,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "steps": [
            {
                "position": s.position,
                "kind": s.kind,
                "tool_name": s.tool_name,
                "tool_input": s.tool_input,
                "tool_output": s.tool_output,
                "ok": s.ok,
                "duration_ms": s.duration_ms,
            }
            for s in run.steps
        ],
    }
