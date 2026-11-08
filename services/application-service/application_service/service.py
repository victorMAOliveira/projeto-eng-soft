"""Application use cases shared by the HTTP API and the event handlers."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from application_service.domain import TRANSITIONS, Status, ensure_transition, max_end_date
from application_service.domain import report_deadline as classify_deadline
from application_service.models import Application, Placement, StatusChange
from application_service.schemas import ApplicationOut, PlacementSummary
from eh_events import ApplicationStatusChanged, PlacementTerms


def transition(
    application: Application,
    target: str,
    *,
    actor_id: int,
    actor_role: str,
    reason: str | None = None,
) -> str:
    """Move ``application`` to ``target`` (validated) and record the audit entry.

    Returns the previous status. Raises ``InvalidTransitionError`` (→ 409).
    """
    previous = application.status
    ensure_transition(previous, target)
    application.status = target
    application.status_reason = reason
    application.history.append(
        StatusChange(
            from_status=previous,
            to_status=target,
            actor_id=actor_id,
            actor_role=actor_role,
            reason=reason,
        )
    )
    return previous


def status_changed_event(
    application: Application, previous: str | None
) -> ApplicationStatusChanged:
    """Payload of ``application.status_changed`` (carries the TCE terms when present)."""
    placement = application.placement
    terms = None
    if placement is not None:
        terms = PlacementTerms(
            start_date=placement.start_date,
            end_date=placement.end_date,
            hours_per_day=placement.hours_per_day,
            hours_per_week=placement.hours_per_week,
            stipend=placement.stipend,
            insurer=placement.insurer,
            insurance_policy=placement.insurance_policy,
            supervisor_name=placement.supervisor_name,
            activities=placement.activities,
            is_pcd=application.student_is_pcd,
            student_course=application.student_course,
            company_name=application.company_name,
        )
    return ApplicationStatusChanged(
        application_id=application.id,
        internship_id=application.internship_id,
        student_id=application.student_id,
        company_id=application.company_id,
        student_name=application.student_name,
        internship_title=application.internship_title,
        from_status=previous,
        to_status=application.status,
        reason=application.status_reason,
        placement=terms,
    )


def to_out(application: Application) -> ApplicationOut:
    """API representation including the transitions allowed from the current state."""
    out = ApplicationOut.model_validate(application)
    out.allowed_transitions = sorted(TRANSITIONS[Status(application.status)])
    return out


async def previous_days_at_company(
    session: AsyncSession, *, student_id: int, company_id: int, exclude_application: int
) -> int:
    """Days of earlier internships of ``student_id`` at ``company_id`` (art. 11 limit)."""
    rows = await session.execute(
        select(Placement.start_date, Placement.end_date)
        .join(Application, Application.id == Placement.application_id)
        .where(
            Application.student_id == student_id,
            Application.company_id == company_id,
            Application.id != exclude_application,
            Application.status.in_(
                [Status.ACTIVE, Status.COMPLETED, Status.TERMINATED, Status.AGREEMENT_PENDING]
            ),
        )
    )
    return sum((end - start).days + 1 for start, end in rows.all())


def placement_summary(application: Application, today: date) -> PlacementSummary:
    """Flatten an application with placement for monitoring (follow-up agent)."""
    placement = application.placement
    assert placement is not None
    due = placement.next_report_due
    deadline = classify_deadline(due, today) if due else None
    return PlacementSummary(
        application_id=application.id,
        student_id=application.student_id,
        student_name=application.student_name,
        company_id=application.company_id,
        company_name=application.company_name,
        internship_title=application.internship_title,
        status=application.status,
        is_pcd=application.student_is_pcd,
        start_date=placement.start_date,
        end_date=placement.end_date,
        hours_per_day=placement.hours_per_day,
        hours_per_week=placement.hours_per_week,
        agreement_id=placement.agreement_id,
        last_report_at=placement.last_report_at,
        next_report_due=due,
        reports_count=placement.reports_count,
        report_state=deadline.state if deadline else "n/a",
        days_to_report=deadline.days_left if deadline else None,
        max_end_date=None if application.student_is_pcd else max_end_date(placement.start_date),
    )
