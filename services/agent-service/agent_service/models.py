"""Execution history of the agents (``agents`` DB)."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eh_db import Base

__all__ = ["AgentRun", "AgentStep", "AlertSent", "Base"]


class AgentRun(Base):
    """One execution of an agent (LLM or rules mode)."""

    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent: Mapped[str] = mapped_column(String(40), index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    user_role: Mapped[str] = mapped_column(String(20))
    mode: Mapped[str] = mapped_column(String(10))  # llm | rules
    model: Mapped[str | None] = mapped_column(String(60))
    input: Mapped[dict] = mapped_column(JSON, default=dict)
    output: Mapped[str] = mapped_column(Text, default="")
    cover_letter: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="running")  # completed | failed
    steps_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    steps: Mapped[list["AgentStep"]] = relationship(
        lazy="selectin", order_by="AgentStep.position", cascade="all, delete-orphan"
    )

    __mapper_args__ = {"eager_defaults": True}


class AgentStep(Base):
    """One entry of the execution trail (model call or tool call)."""

    __tablename__ = "agent_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))  # llm | tool_call | final
    tool_name: Mapped[str | None] = mapped_column(String(60))
    tool_input: Mapped[dict | None] = mapped_column(JSON)
    tool_output: Mapped[dict | list | None] = mapped_column(JSON)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)


class AlertSent(Base):
    """Deduplication of follow-up alerts (one per application, kind and reference date)."""

    __tablename__ = "alerts_sent"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
