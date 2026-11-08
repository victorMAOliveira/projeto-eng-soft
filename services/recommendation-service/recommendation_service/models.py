"""Read model (CQRS-light): denormalised copies fed by events from other services."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from eh_db import Base, ProcessedEvent

__all__ = ["Base", "ProcessedEvent", "RmApplication", "RmInternship", "RmStudent"]


class RmStudent(Base):
    """Student profile as last seen in ``profile.updated`` / ``user.registered``."""

    __tablename__ = "rm_students"

    student_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(150), default="")
    course: Mapped[str | None] = mapped_column(String(120))
    semester: Mapped[int | None] = mapped_column(Integer)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    resume_summary: Mapped[str] = mapped_column(Text, default="")
    weekly_availability_hours: Mapped[int | None] = mapped_column(Integer)
    preferred_modality: Mapped[str | None] = mapped_column(String(10))
    city: Mapped[str | None] = mapped_column(String(80))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __mapper_args__ = {"eager_defaults": True}


class RmInternship(Base):
    """Offer as published in ``internship.published`` (status from ``internship.closed``)."""

    __tablename__ = "rm_internships"

    internship_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    company_id: Mapped[int] = mapped_column(Integer, index=True)
    company_name: Mapped[str] = mapped_column(String(150))
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text)
    requirements: Mapped[list[str]] = mapped_column(JSON, default=list)
    course: Mapped[str] = mapped_column(String(120))
    min_semester: Mapped[int] = mapped_column(Integer)
    hours_per_day: Mapped[int] = mapped_column(Integer)
    hours_per_week: Mapped[int] = mapped_column(Integer)
    modality: Mapped[str] = mapped_column(String(10))
    city: Mapped[str] = mapped_column(String(80))
    stipend: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(10), default="open", index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    popularity: Mapped[int] = mapped_column(Integer, default=0)


class RmApplication(Base):
    """Who applied to what (popularity and the applicants ranking)."""

    __tablename__ = "rm_applications"
    __table_args__ = (UniqueConstraint("internship_id", "student_id"),)

    application_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    internship_id: Mapped[int] = mapped_column(Integer, index=True)
    student_id: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(20), default="submitted")
