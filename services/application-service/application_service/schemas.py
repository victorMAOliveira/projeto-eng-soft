"""Request/response models of the application-service API."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ApplicationIn(BaseModel):
    """A student applies to an internship."""

    internship_id: int
    cover_letter: str = Field(default="", max_length=4000)


class PlacementIn(BaseModel):
    """Terms the company informs when approving a candidate (become the TCE)."""

    start_date: date
    end_date: date
    supervisor_name: str = Field(min_length=3, max_length=150)
    insurer: str | None = Field(default=None, max_length=120)
    insurance_policy: str | None = Field(default=None, max_length=60)
    activities: str = Field(default="", max_length=3000)
    hours_per_day: int | None = Field(default=None, ge=1, le=12)
    hours_per_week: int | None = Field(default=None, ge=1, le=60)
    stipend: float | None = Field(default=None, ge=0)


class ReasonIn(BaseModel):
    """Optional justification of a transition."""

    reason: str | None = Field(default=None, max_length=1000)


class StatusChangeOut(BaseModel):
    """One entry of the audit trail."""

    model_config = ConfigDict(from_attributes=True)

    from_status: str | None
    to_status: str
    actor_role: str
    reason: str | None
    created_at: datetime


class PlacementOut(BaseModel):
    """Internship terms and report schedule."""

    model_config = ConfigDict(from_attributes=True)

    start_date: date
    end_date: date
    hours_per_day: int
    hours_per_week: int
    stipend: float
    insurer: str
    insurance_policy: str
    supervisor_name: str
    activities: str
    agreement_id: str | None
    activated_at: datetime | None
    last_report_at: date | None
    next_report_due: date | None
    reports_count: int


class ApplicationOut(BaseModel):
    """An application with its placement (if any) and history."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    internship_id: int
    student_id: int
    company_id: int
    student_name: str
    company_name: str
    internship_title: str
    student_course: str | None
    student_is_pcd: bool
    cover_letter: str
    status: str
    status_reason: str | None
    allowed_transitions: list[str] = Field(default_factory=list)
    placement: PlacementOut | None = None
    history: list[StatusChangeOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class Board(BaseModel):
    """Applications grouped by status (kanban)."""

    columns: dict[str, list[ApplicationOut]]
    total: int


class PlacementSummary(BaseModel):
    """Active-internship view used by the follow-up agent and dashboards."""

    application_id: int
    student_id: int
    student_name: str
    company_id: int
    company_name: str
    internship_title: str
    status: str
    is_pcd: bool
    start_date: date
    end_date: date
    hours_per_day: int
    hours_per_week: int
    agreement_id: str | None
    last_report_at: date | None
    next_report_due: date | None
    reports_count: int
    report_state: str
    days_to_report: int | None
    max_end_date: date | None
