"""Business rules of applications and internships (pure functions, no I/O).

State machine::

    submitted → under_review → approved | rejected | withdrawn
    submitted → withdrawn
    approved → agreement_pending → active → completed | terminated

Legal rules (Lei nº 11.788/2008):

* art. 10, II — higher education workload: up to 6 h/day and 30 h/week;
* art. 11 — at most 2 years at the same host company, except for interns
  with disabilities (PcD);
* art. 9, VII — activity reports at most every 6 months;
* art. 9, IV — the agreement (TCE) requires personal accident insurance.
"""

import calendar
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

MAX_HOURS_PER_DAY = 6
MAX_HOURS_PER_WEEK = 30
MAX_YEARS_SAME_COMPANY = 2
REPORT_PERIOD_MONTHS = 6
REPORT_DUE_SOON_DAYS = 30


class Status(StrEnum):
    """Lifecycle of an application that may become an internship."""

    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    AGREEMENT_PENDING = "agreement_pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    TERMINATED = "terminated"


TRANSITIONS: dict[Status, frozenset[Status]] = {
    Status.SUBMITTED: frozenset({Status.UNDER_REVIEW, Status.WITHDRAWN}),
    Status.UNDER_REVIEW: frozenset({Status.APPROVED, Status.REJECTED, Status.WITHDRAWN}),
    Status.APPROVED: frozenset({Status.AGREEMENT_PENDING}),
    Status.AGREEMENT_PENDING: frozenset({Status.ACTIVE}),
    Status.ACTIVE: frozenset({Status.COMPLETED, Status.TERMINATED}),
    Status.REJECTED: frozenset(),
    Status.WITHDRAWN: frozenset(),
    Status.COMPLETED: frozenset(),
    Status.TERMINATED: frozenset(),
}

FINAL_STATUSES = frozenset(s for s, targets in TRANSITIONS.items() if not targets)
PLACEMENT_STATUSES = frozenset(
    {Status.ACTIVE, Status.COMPLETED, Status.TERMINATED, Status.AGREEMENT_PENDING, Status.APPROVED}
)


class InvalidTransitionError(Exception):
    """Raised when a transition is not allowed by the state machine (HTTP 409)."""

    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"Transição inválida: {current} → {target}")
        self.current = current
        self.target = target


class LegalRuleViolationError(Exception):
    """Raised when a rule of Lei 11.788/2008 is violated (HTTP 422)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def can_transition(current: str, target: str) -> bool:
    """``True`` if the state machine allows ``current → target``."""
    return Status(target) in TRANSITIONS[Status(current)]


def ensure_transition(current: str, target: str) -> Status:
    """Validate ``current → target`` and return the target status.

    Raises:
        InvalidTransitionError: the transition is not in :data:`TRANSITIONS`.
    """
    if not can_transition(current, target):
        raise InvalidTransitionError(current, target)
    return Status(target)


def add_months(day: date, months: int) -> date:
    """Add calendar months, clamping the day (31/08 + 6 months = 28/02 or 29/02)."""
    month_index = day.month - 1 + months
    year, month = day.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def validate_workload(hours_per_day: int, hours_per_week: int) -> None:
    """Art. 10, II: up to 6 h/day and 30 h/week for higher education."""
    if hours_per_day <= 0 or hours_per_week <= 0:
        raise LegalRuleViolationError("workload_invalid", "A jornada deve ser positiva.")
    if hours_per_day > MAX_HOURS_PER_DAY:
        raise LegalRuleViolationError(
            "workload_daily",
            f"Jornada diária de {hours_per_day} h excede o limite legal de {MAX_HOURS_PER_DAY} h.",
        )
    if hours_per_week > MAX_HOURS_PER_WEEK:
        raise LegalRuleViolationError(
            "workload_weekly",
            f"Jornada semanal de {hours_per_week} h excede o limite legal de "
            f"{MAX_HOURS_PER_WEEK} h.",
        )


def max_end_date(start: date, previous_days: int = 0) -> date:
    """Last allowed day at the same company, discounting previous internships there.

    Two years starting on 01/12/2026 end on 30/11/2028.
    """
    anniversary = add_months(start, 12 * MAX_YEARS_SAME_COMPANY)
    return date.fromordinal(anniversary.toordinal() - 1 - previous_days)


def validate_duration(start: date, end: date, *, is_pcd: bool, previous_days: int = 0) -> None:
    """Art. 11: at most 2 years at the same company (cumulative), except for PcD interns.

    Args:
        start: First day of the internship.
        end: Last day of the internship.
        is_pcd: Intern is a person with disabilities (exempt from the limit).
        previous_days: Days already spent in earlier internships at the same company.
    """
    if end <= start:
        raise LegalRuleViolationError(
            "dates_invalid", "A data de término deve ser posterior à de início."
        )
    if is_pcd:
        return
    if end > max_end_date(start, previous_days):
        raise LegalRuleViolationError(
            "duration_exceeded",
            "A duração ultrapassa 2 anos na mesma concedente (art. 11 da Lei 11.788/2008)"
            + (
                f", considerando {previous_days} dias de estágios anteriores."
                if previous_days
                else "."
            ),
        )


def validate_insurance(insurer: str | None, policy: str | None) -> None:
    """Art. 9, IV: the TCE requires personal accident insurance."""
    if not (insurer and insurer.strip()) or not (policy and policy.strip()):
        raise LegalRuleViolationError(
            "insurance_missing",
            "O TCE exige seguro contra acidentes pessoais (seguradora e apólice).",
        )


def next_report_due(reference: date) -> date:
    """Art. 9, VII: next activity report at most 6 months after ``reference``."""
    return add_months(reference, REPORT_PERIOD_MONTHS)


@dataclass(frozen=True, slots=True)
class ReportDeadline:
    """Classification of an activity report deadline."""

    due_date: date
    days_left: int
    state: str  # "ok" | "due_soon" | "overdue"


def report_deadline(due: date, today: date) -> ReportDeadline:
    """Classify ``due`` as ok, due soon (≤ 30 days) or overdue."""
    days_left = (due - today).days
    if days_left < 0:
        state = "overdue"
    elif days_left <= REPORT_DUE_SOON_DAYS:
        state = "due_soon"
    else:
        state = "ok"
    return ReportDeadline(due, days_left, state)


def eligibility_problems(
    *,
    student_course: str | None,
    student_semester: int | None,
    weekly_availability: int | None,
    internship_course: str,
    min_semester: int,
    hours_per_week: int,
) -> list[str]:
    """Reasons why a student cannot apply (empty list = eligible)."""
    problems = []
    if not student_course or not student_semester:
        problems.append("Complete seu perfil acadêmico (curso e período) antes de se candidatar.")
        return problems
    if student_course != internship_course:
        problems.append(f"A vaga é para o curso {internship_course}.")
    if student_semester < min_semester:
        problems.append(f"A vaga exige no mínimo o {min_semester}º período.")
    if weekly_availability is not None and weekly_availability < hours_per_week:
        problems.append(
            f"A vaga exige {hours_per_week} h/semana e sua disponibilidade é "
            f"{weekly_availability} h."
        )
    return problems
