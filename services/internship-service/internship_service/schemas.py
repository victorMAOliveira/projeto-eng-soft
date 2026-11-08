"""Request/response models of the internship-service API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Lei nº 11.788/2008, art. 10, II — higher education: up to 6 h/day and 30 h/week.
MAX_HOURS_PER_DAY = 6
MAX_HOURS_PER_WEEK = 30


class InternshipIn(BaseModel):
    """Data required to publish an internship offer."""

    title: str = Field(min_length=3, max_length=150)
    description: str = Field(min_length=10, max_length=5000)
    requirements: list[str] = Field(min_length=1, max_length=20)
    course: str = Field(min_length=2, max_length=120)
    min_semester: int = Field(ge=1, le=12)
    hours_per_day: int = Field(ge=1, le=MAX_HOURS_PER_DAY)
    hours_per_week: int = Field(ge=1, le=MAX_HOURS_PER_WEEK)
    modality: Literal["onsite", "remote", "hybrid"]
    city: str = Field(min_length=2, max_length=80)
    stipend: float = Field(ge=0, le=20000)
    positions: int = Field(default=1, ge=1, le=50)

    @field_validator("requirements")
    @classmethod
    def clean_requirements(cls, items: list[str]) -> list[str]:
        """Trim, drop blanks and duplicates (case-insensitive)."""
        seen, result = set(), []
        for raw in items:
            item = " ".join(raw.split())[:60]
            if item and item.lower() not in seen:
                seen.add(item.lower())
                result.append(item)
        if not result:
            raise ValueError("informe ao menos um requisito")
        return result

    @model_validator(mode="after")
    def check_workload(self) -> "InternshipIn":
        """Weekly hours cannot exceed what the daily limit allows in a 6-day week."""
        if self.hours_per_week > self.hours_per_day * 6:
            raise ValueError("carga semanal incompatível com a carga diária")
        return self


class InternshipOut(InternshipIn):
    """An internship offer as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    company_name: str
    status: str
    published_at: datetime
    closed_at: datetime | None = None


class InternshipPage(BaseModel):
    """Paginated search result."""

    items: list[InternshipOut]
    total: int
    page: int
    size: int


class InternshipStats(BaseModel):
    """Counters for dashboards."""

    open: int
    closed: int
    by_course: dict[str, int]
    by_modality: dict[str, int]
