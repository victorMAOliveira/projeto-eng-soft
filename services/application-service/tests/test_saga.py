from datetime import UTC, date, datetime

from application_service.domain import next_report_due
from application_service.events import SagaHandlers
from conftest import COMPANY, COORDINATOR, STUDENT, approved_application

from eh_events import make_event


def event(kind: str, **payload):
    return make_event(kind, payload, producer="document-service")


async def test_saga_steps_drive_the_state_machine(client, db, publisher):
    approved = await approved_application(client)
    app_id = approved["id"]
    handlers = SagaHandlers(db, publisher)

    await handlers(
        event(
            "agreement.generated",
            agreement_id="tce-1",
            application_id=app_id,
            student_id=1,
            company_id=100,
        )
    )
    pending = (await client.get(f"/applications/{app_id}", headers=STUDENT)).json()
    assert pending["status"] == "agreement_pending"
    assert pending["placement"]["agreement_id"] == "tce-1"
    assert pending["history"][-1]["actor_role"] == "system"

    await handlers(
        event(
            "agreement.approved",
            agreement_id="tce-1",
            application_id=app_id,
            student_id=1,
            company_id=100,
            approved_by=300,
            approved_at=datetime.now(UTC).isoformat(),
        )
    )
    active = (await client.get(f"/applications/{app_id}", headers=COMPANY)).json()
    assert active["status"] == "active"
    start = date.fromisoformat(active["placement"]["start_date"])
    assert (
        active["placement"]["next_report_due"]
        == next_report_due(max(start, date.today())).isoformat()
    )
    statuses = [e.payload["to_status"] for e in publisher.of_type("application.status_changed")]
    assert statuses[-2:] == ["agreement_pending", "active"]

    submitted_at = datetime(2027, 3, 10, 12, tzinfo=UTC)
    await handlers(
        event(
            "report.submitted",
            report_id="r1",
            application_id=app_id,
            student_id=1,
            company_id=100,
            version=1,
            period_start="2026-12-01",
            period_end="2027-03-01",
            submitted_at=submitted_at.isoformat(),
        )
    )
    placements = (await client.get("/placements", headers=COORDINATOR)).json()
    assert placements[0]["reports_count"] == 1
    assert placements[0]["last_report_at"] == "2027-03-10"
    assert placements[0]["next_report_due"] == "2027-09-10"

    completed = await client.post(f"/applications/{app_id}/complete", json={}, headers=COORDINATOR)
    assert completed.json()["status"] == "completed"


async def test_late_or_unknown_events_are_ignored(client, db, publisher):
    handlers = SagaHandlers(db, publisher)
    unknown = event(
        "agreement.generated", agreement_id="x", application_id=999, student_id=1, company_id=1
    )
    await handlers(unknown)
    approved = await approved_application(client)
    before = len(publisher.events)
    approve_again = event(
        "agreement.approved",
        agreement_id="x",
        application_id=approved["id"],
        student_id=1,
        company_id=100,
        approved_by=1,
        approved_at=datetime.now(UTC).isoformat(),
    )
    await handlers(approve_again)  # approved -> active is not a valid transition
    assert len(publisher.events) == before
    report = event(
        "report.submitted",
        report_id="r",
        application_id=999,
        student_id=1,
        company_id=1,
        version=1,
        period_start="2026-01-01",
        period_end="2026-02-01",
        submitted_at=datetime.now(UTC).isoformat(),
    )
    await handlers(report)
    await handlers(event("internship.closed", internship_id=1, company_id=1))  # not handled
