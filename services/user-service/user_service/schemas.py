"""Request/response models (pydantic) of the user-service API."""

import re
import unicodedata
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
Modality = Literal["onsite", "remote", "hybrid"]
RegisterRole = Literal["student", "company", "coordinator"]


def _normalize_email(value: str) -> str:
    value = value.strip().lower()
    if not EMAIL_RE.match(value):
        raise ValueError("e-mail inválido")
    return value


class RegisterRequest(BaseModel):
    """Account creation."""

    email: str
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=150)
    role: RegisterRole

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        return _normalize_email(value)


class LoginRequest(BaseModel):
    """Credentials."""

    email: str
    password: str

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return value.strip().lower()


class UserOut(BaseModel):
    """Public view of an account."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: str
    created_at: datetime


class TokenResponse(BaseModel):
    """Login result with the bearer token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


def normalize_skill(skill: str) -> str:
    """Trim and collapse whitespace, keeping the user's capitalisation."""
    return " ".join(unicodedata.normalize("NFC", skill).split())


class StudentProfileIn(BaseModel):
    """Editable fields of the student profile."""

    course: str = Field(min_length=2, max_length=120)
    semester: int = Field(ge=1, le=12)
    enrollment: str | None = Field(default=None, max_length=30)
    skills: list[str] = Field(default_factory=list, max_length=30)
    resume_summary: str = Field(default="", max_length=2000)
    weekly_availability_hours: int = Field(
        ge=4, le=30, description="Lei 11.788/2008, art. 10: no máximo 30 h semanais"
    )
    preferred_modality: Modality | None = None
    city: str | None = Field(default=None, max_length=80)
    is_pcd: bool = False

    @field_validator("skills")
    @classmethod
    def dedupe_skills(cls, skills: list[str]) -> list[str]:
        seen, result = set(), []
        for raw in skills:
            skill = normalize_skill(raw)[:40]
            if skill and skill.lower() not in seen:
                seen.add(skill.lower())
                result.append(skill)
        return result


class StudentProfileOut(BaseModel):
    """Student profile with account data and a completeness indicator."""

    user_id: int
    name: str
    email: str
    course: str | None = None
    semester: int | None = None
    enrollment: str | None = None
    skills: list[str] = Field(default_factory=list)
    resume_summary: str = ""
    weekly_availability_hours: int | None = None
    preferred_modality: str | None = None
    city: str | None = None
    is_pcd: bool = False
    completeness: float = 0.0
    updated_at: datetime | None = None


class CompanyProfileIn(BaseModel):
    """Editable fields of the company profile."""

    trade_name: str = Field(min_length=2, max_length=150)
    cnpj: str | None = Field(default=None, max_length=18)
    sector: str | None = Field(default=None, max_length=80)
    city: str | None = Field(default=None, max_length=80)
    description: str = Field(default="", max_length=2000)
    website: str | None = Field(default=None, max_length=200)


class CompanyProfileOut(CompanyProfileIn):
    """Company profile with account data."""

    user_id: int
    email: str
