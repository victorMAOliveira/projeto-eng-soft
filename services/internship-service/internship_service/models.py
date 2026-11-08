"""SQLAlchemy models of the internship-service database (``internships`` DB)."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from eh_db import Base, TimestampMixin


class Internship(TimestampMixin, Base):
    """An internship offer published by a company (concedente)."""

    __tablename__ = "internships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, index=True)
    company_name: Mapped[str] = mapped_column(String(150))
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text)
    requirements: Mapped[list[str]] = mapped_column(JSON, default=list)
    course: Mapped[str] = mapped_column(String(120), index=True)
    min_semester: Mapped[int] = mapped_column(Integer)
    hours_per_day: Mapped[int] = mapped_column(Integer)
    hours_per_week: Mapped[int] = mapped_column(Integer)
    modality: Mapped[str] = mapped_column(String(10))
    city: Mapped[str] = mapped_column(String(80))
    stipend: Mapped[float] = mapped_column(Float)
    positions: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(10), default="open", index=True)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
