"""Versioned event contracts shared by producers and consumers.

Every event is an envelope (:class:`Event`) with ``event_id``, ``event_type``,
``occurred_at``, ``schema_version``, ``producer``, ``correlation_id`` and a
``payload`` validated by the payload model registered for its type.
Payloads carry the state consumers need (event-carried state transfer), so a
consumer never has to call the producer back.
"""

import uuid
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1


class EventType(StrEnum):
    """Routing keys published on the ``estagiohub.events`` topic exchange."""

    USER_REGISTERED = "user.registered"
    PROFILE_UPDATED = "profile.updated"
    INTERNSHIP_PUBLISHED = "internship.published"
    INTERNSHIP_CLOSED = "internship.closed"
    APPLICATION_SUBMITTED = "application.submitted"
    APPLICATION_STATUS_CHANGED = "application.status_changed"
    AGREEMENT_GENERATED = "agreement.generated"
    AGREEMENT_APPROVED = "agreement.approved"
    REPORT_SUBMITTED = "report.submitted"
    REPORT_DUE_SOON = "report.due_soon"


class _Payload(BaseModel):
    model_config = ConfigDict(extra="ignore")


class UserRegistered(_Payload):
    """A new account was created (``user-service``)."""

    user_id: int
    email: str
    name: str
    role: str


class ProfileUpdated(_Payload):
    """A student's academic profile changed (``user-service``)."""

    user_id: int
    name: str
    course: str | None = None
    semester: int | None = None
    skills: list[str] = Field(default_factory=list)
    resume_summary: str = ""
    weekly_availability_hours: int | None = None
    preferred_modality: str | None = None
    city: str | None = None
    is_pcd: bool = False


class InternshipPublished(_Payload):
    """A company published an internship offer (``internship-service``)."""

    internship_id: int
    company_id: int
    company_name: str
    title: str
    description: str
    requirements: list[str]
    course: str
    min_semester: int
    hours_per_day: int
    hours_per_week: int
    modality: str
    city: str
    stipend: float
    published_at: datetime


class InternshipClosed(_Payload):
    """An internship offer stopped accepting applications (``internship-service``)."""

    internship_id: int
    company_id: int


class ApplicationSubmitted(_Payload):
    """A student applied to an internship (``application-service``)."""

    application_id: int
    internship_id: int
    student_id: int
    company_id: int
    student_name: str
    internship_title: str


class PlacementTerms(_Payload):
    """Terms agreed when a company approves a candidate; needed to issue the TCE."""

    start_date: date
    end_date: date
    hours_per_day: int
    hours_per_week: int
    stipend: float
    insurer: str | None = None
    insurance_policy: str | None = None
    supervisor_name: str
    activities: str = ""
    is_pcd: bool = False
    student_course: str | None = None
    company_name: str = ""


class ApplicationStatusChanged(_Payload):
    """The application/internship state machine moved (``application-service``)."""

    application_id: int
    internship_id: int
    student_id: int
    company_id: int
    student_name: str
    internship_title: str
    from_status: str | None
    to_status: str
    reason: str | None = None
    placement: PlacementTerms | None = None


class AgreementGenerated(_Payload):
    """The TCE PDF was generated and awaits coordination approval (``document-service``)."""

    agreement_id: str
    application_id: int
    student_id: int
    company_id: int
    version: int = 1


class AgreementApproved(_Payload):
    """The coordination approved the TCE (``document-service``)."""

    agreement_id: str
    application_id: int
    student_id: int
    company_id: int
    approved_by: int
    approved_at: datetime


class ReportSubmitted(_Payload):
    """A student uploaded an activity report version (``document-service``)."""

    report_id: str
    application_id: int
    student_id: int
    company_id: int
    version: int
    period_start: date
    period_end: date
    submitted_at: datetime


class ReportDueSoon(_Payload):
    """An activity report is due soon or overdue (``agent-service``)."""

    application_id: int
    student_id: int
    company_id: int | None = None
    student_name: str = ""
    due_date: date
    days_left: int
    overdue: bool = False


PAYLOAD_MODELS: dict[EventType, type[BaseModel]] = {
    EventType.USER_REGISTERED: UserRegistered,
    EventType.PROFILE_UPDATED: ProfileUpdated,
    EventType.INTERNSHIP_PUBLISHED: InternshipPublished,
    EventType.INTERNSHIP_CLOSED: InternshipClosed,
    EventType.APPLICATION_SUBMITTED: ApplicationSubmitted,
    EventType.APPLICATION_STATUS_CHANGED: ApplicationStatusChanged,
    EventType.AGREEMENT_GENERATED: AgreementGenerated,
    EventType.AGREEMENT_APPROVED: AgreementApproved,
    EventType.REPORT_SUBMITTED: ReportSubmitted,
    EventType.REPORT_DUE_SOON: ReportDueSoon,
}


class Event(BaseModel):
    """Envelope common to every event."""

    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    event_type: EventType
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    schema_version: int = SCHEMA_VERSION
    producer: str
    correlation_id: str | None = None
    payload: dict[str, Any]


def make_event(
    event_type: EventType | str,
    payload: BaseModel | dict[str, Any],
    *,
    producer: str,
    correlation_id: str | None = None,
) -> Event:
    """Validate ``payload`` against its contract and wrap it in an :class:`Event`."""
    kind = EventType(event_type)
    model = PAYLOAD_MODELS[kind]
    data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    validated = model.model_validate(data)
    return Event(
        event_type=kind,
        producer=producer,
        correlation_id=correlation_id,
        payload=validated.model_dump(mode="json"),
    )


def parse_event(body: bytes | str) -> Event:
    """Deserialize and validate an event envelope and its payload."""
    event = Event.model_validate_json(body)
    typed_payload(event)
    return event


def typed_payload(event: Event) -> Any:
    """Return the payload of ``event`` as its typed pydantic model."""
    return PAYLOAD_MODELS[event.event_type].model_validate(event.payload)
