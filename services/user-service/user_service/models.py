"""SQLAlchemy models of the user-service database (``users`` DB)."""

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eh_db import Base, TimestampMixin


class User(TimestampMixin, Base):
    """An account. ``role`` is one of student, company or coordinator."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(150))
    role: Mapped[str] = mapped_column(String(20), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    student_profile: Mapped["StudentProfile | None"] = relationship(
        back_populates="user", uselist=False, lazy="selectin"
    )
    company_profile: Mapped["CompanyProfile | None"] = relationship(
        back_populates="user", uselist=False, lazy="selectin"
    )


class StudentProfile(TimestampMixin, Base):
    """Academic profile used by applications and the recommender."""

    __tablename__ = "student_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    course: Mapped[str | None] = mapped_column(String(120))
    semester: Mapped[int | None] = mapped_column(Integer)
    enrollment: Mapped[str | None] = mapped_column(String(30))
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    resume_summary: Mapped[str] = mapped_column(Text, default="")
    weekly_availability_hours: Mapped[int | None] = mapped_column(Integer)
    preferred_modality: Mapped[str | None] = mapped_column(String(10))
    city: Mapped[str | None] = mapped_column(String(80))
    is_pcd: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="student_profile")


class CompanyProfile(TimestampMixin, Base):
    """Host company (concedente) profile."""

    __tablename__ = "company_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    trade_name: Mapped[str] = mapped_column(String(150))
    cnpj: Mapped[str | None] = mapped_column(String(18))
    sector: Mapped[str | None] = mapped_column(String(80))
    city: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    website: Mapped[str | None] = mapped_column(String(200))

    user: Mapped[User] = relationship(back_populates="company_profile")
