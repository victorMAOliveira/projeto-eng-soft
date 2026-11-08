from datetime import date

import pytest
from application_service.domain import (
    TRANSITIONS,
    InvalidTransitionError,
    LegalRuleViolationError,
    Status,
    add_months,
    can_transition,
    eligibility_problems,
    ensure_transition,
    max_end_date,
    next_report_due,
    report_deadline,
    validate_duration,
    validate_insurance,
    validate_workload,
)

VALID = [
    ("submitted", "under_review"),
    ("submitted", "withdrawn"),
    ("under_review", "approved"),
    ("under_review", "rejected"),
    ("under_review", "withdrawn"),
    ("approved", "agreement_pending"),
    ("agreement_pending", "active"),
    ("active", "completed"),
    ("active", "terminated"),
]


@pytest.mark.parametrize(("current", "target"), VALID)
def test_valid_transitions(current, target):
    assert can_transition(current, target)
    assert ensure_transition(current, target) == Status(target)


@pytest.mark.parametrize(
    ("current", "target"),
    [(c.value, t.value) for c in Status for t in Status if (c.value, t.value) not in VALID],
)
def test_every_other_transition_is_invalid(current, target):
    assert not can_transition(current, target)
    with pytest.raises(InvalidTransitionError) as info:
        ensure_transition(current, target)
    assert info.value.current == current and info.value.target == target


def test_final_states_have_no_exit():
    for final in ("rejected", "withdrawn", "completed", "terminated"):
        assert TRANSITIONS[Status(final)] == frozenset()


@pytest.mark.parametrize(("day", "week"), [(6, 30), (4, 20), (1, 1)])
def test_workload_within_limits(day, week):
    validate_workload(day, week)


@pytest.mark.parametrize(
    ("day", "week", "code"),
    [(7, 30, "workload_daily"), (6, 31, "workload_weekly"), (0, 10, "workload_invalid")],
)
def test_workload_violations(day, week, code):
    with pytest.raises(LegalRuleViolationError) as info:
        validate_workload(day, week)
    assert info.value.code == code


def test_add_months_clamps_end_of_month():
    assert add_months(date(2026, 8, 31), 6) == date(2027, 2, 28)
    assert add_months(date(2027, 8, 31), 6) == date(2028, 2, 29)
    assert add_months(date(2026, 11, 15), 2) == date(2027, 1, 15)


def test_two_year_limit_boundary():
    start = date(2026, 12, 1)
    assert max_end_date(start) == date(2028, 11, 30)
    validate_duration(start, date(2028, 11, 30), is_pcd=False)
    with pytest.raises(LegalRuleViolationError) as info:
        validate_duration(start, date(2028, 12, 1), is_pcd=False)
    assert info.value.code == "duration_exceeded"


def test_pcd_intern_is_exempt_from_two_year_limit():
    validate_duration(date(2026, 1, 1), date(2029, 1, 1), is_pcd=True)


def test_previous_internships_at_same_company_count():
    start = date(2026, 1, 1)
    validate_duration(start, date(2027, 1, 1), is_pcd=False, previous_days=300)
    with pytest.raises(LegalRuleViolationError) as info:
        validate_duration(start, date(2027, 6, 1), is_pcd=False, previous_days=400)
    assert "400 dias" in info.value.message


def test_end_must_be_after_start():
    with pytest.raises(LegalRuleViolationError) as info:
        validate_duration(date(2026, 5, 1), date(2026, 5, 1), is_pcd=True)
    assert info.value.code == "dates_invalid"


@pytest.mark.parametrize(
    ("insurer", "policy"), [(None, "AP-1"), ("Seg", None), ("  ", "AP"), ("Seg", "")]
)
def test_insurance_is_required(insurer, policy):
    with pytest.raises(LegalRuleViolationError) as info:
        validate_insurance(insurer, policy)
    assert info.value.code == "insurance_missing"


def test_insurance_ok():
    validate_insurance("Seguradora Exemplo", "AP-2026-001")


def test_report_every_six_months():
    assert next_report_due(date(2026, 11, 8)) == date(2027, 5, 8)


@pytest.mark.parametrize(
    ("due", "state", "days"),
    [
        (date(2026, 11, 1), "overdue", -7),
        (date(2026, 11, 8), "due_soon", 0),
        (date(2026, 12, 8), "due_soon", 30),
        (date(2026, 12, 9), "ok", 31),
    ],
)
def test_report_deadline_classification(due, state, days):
    deadline = report_deadline(due, date(2026, 11, 8))
    assert deadline.state == state
    assert deadline.days_left == days


def test_eligibility():
    base = dict(internship_course="CC", min_semester=4, hours_per_week=30)
    assert (
        eligibility_problems(
            student_course="CC", student_semester=5, weekly_availability=30, **base
        )
        == []
    )
    problems = eligibility_problems(
        student_course="SI", student_semester=2, weekly_availability=20, **base
    )
    assert len(problems) == 3
    incomplete = eligibility_problems(
        student_course=None, student_semester=None, weekly_availability=None, **base
    )
    assert "Complete seu perfil" in incomplete[0]
