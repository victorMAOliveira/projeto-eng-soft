"""SQLAlchemy models of the application-service database (``applications`` DB)."""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eh_db import Base, ProcessedEvent, TimestampMixin

__all__ = ["Application", "Base", "Placement", "ProcessedEvent", "StatusChange"]


class Application(TimestampMixin, Base):
    """A student's application; after approval it carries the internship lifecycle."""

    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("internship_id", "student_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    internship_id: Mapped[int] = mapped_column(Integer, index=True)
    student_id: Mapped[int] = mapped_column(Integer, index=True)
    company_id: Mapped[int] = mapped_column(Integer, index=True)
    student_name: Mapped[str] = mapped_column(String(150))
    company_name: Mapped[str] = mapped_column(String(150))
    internship_title: Mapped[str] = mapped_column(String(150))
    student_course: Mapped[str | None] = mapped_column(String(120))
    student_is_pcd: Mapped[bool] = mapped_column(Boolean, default=False)
    internship_hours_per_day: Mapped[int] = mapped_column(Integer)
    internship_hours_per_week: Mapped[int] = mapped_column(Integer)
    internship_stipend: Mapped[float] = mapped_column(Float)
    cover_letter: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), index=True)
    status_reason: Mapped[str | None] = mapped_column(Text)

    placement: Mapped["Placement | None"] = relationship(
        back_populates="application", uselist=False, lazy="selectin"
    )
    history: Mapped[list["StatusChange"]] = relationship(
        lazy="selectin", order_by="StatusChange.id", cascade="all, delete-orphan"
    )


class Placement(TimestampMixin, Base):
    """Terms of the internship (estágio) agreed at approval time."""

    __tablename__ = "placements"

    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), primary_key=True
    )
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    hours_per_day: Mapped[int] = mapped_column(Integer)
    hours_per_week: Mapped[int] = mapped_column(Integer)
    stipend: Mapped[float] = mapped_column(Float)
    insurer: Mapped[str] = mapped_column(String(120))
    insurance_policy: Mapped[str] = mapped_column(String(60))
    supervisor_name: Mapped[str] = mapped_column(String(150))
    activities: Mapped[str] = mapped_column(Text, default="")
    agreement_id: Mapped[str | None] = mapped_column(String(64))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_report_at: Mapped[date | None] = mapped_column(Date)
    next_report_due: Mapped[date | None] = mapped_column(Date)
    reports_count: Mapped[int] = mapped_column(Integer, default=0)

    application: Mapped[Application] = relationship(back_populates="placement")


class StatusChange(Base):
    """Audit trail of every state machine transition."""

    __tablename__ = "status_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[int] = mapped_column(Integer)
    actor_role: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __mapper_args__ = {"eager_defaults": True}
