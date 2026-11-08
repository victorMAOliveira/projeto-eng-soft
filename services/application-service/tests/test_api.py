from datetime import date, timedelta

from conftest import (
    COMPANY,
    COORDINATOR,
    OTHER_COMPANY,
    OTHER_STUDENT,
    STUDENT,
    approved_application,
    placement,
    submit,
)


async def test_submit_creates_application_and_publishes_event(client, publisher):
    response = await submit(client)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "submitted"
    assert body["company_id"] == 100
    assert body["internship_title"] == "Estágio Backend"
    assert body["allowed_transitions"] == ["under_review", "withdrawn"]
    assert body["history"][0]["to_status"] == "submitted"
    event = publisher.of_type("application.submitted")[0]
    assert event.payload["student_name"] == "Ana Souza"


async def test_submit_rules(client, upstreams):
    assert (await submit(client)).status_code == 201
    assert (await submit(client)).status_code == 409  # duplicate
    assert (await submit(client, internship_id=11)).status_code == 409  # closed offer
    assert (await submit(client, internship_id=99)).status_code == 404
    ineligible = await submit(client, headers=OTHER_STUDENT)  # Design student, CC offer
    assert ineligible.status_code == 422
    assert "curso" in ineligible.json()["detail"]
    assert (await submit(client, headers=COMPANY)).status_code == 403
    upstreams.down = True
    assert (await submit(client, internship_id=12)).status_code == 503


async def test_full_company_flow_with_status_events(client, publisher):
    approved = await approved_application(client)
    assert approved["status"] == "approved"
    assert approved["placement"]["insurance_policy"] == "AP-2026-001"
    assert approved["placement"]["hours_per_week"] == 30
    assert [h["to_status"] for h in approved["history"]] == [
        "submitted",
        "under_review",
        "approved",
    ]
    events = publisher.of_type("application.status_changed")
    assert [e.payload["to_status"] for e in events] == ["under_review", "approved"]
    terms = events[-1].payload["placement"]
    assert terms["insurer"] == "Seguradora Exemplo"
    assert terms["company_name"] == "ACME Tecnologia"


async def test_approval_validates_legal_rules(client):
    created = (await submit(client)).json()
    url = f"/applications/{created['id']}"
    await client.post(f"{url}/review", headers=COMPANY)
    too_long = await client.post(f"{url}/approve", json=placement(hours_per_day=7), headers=COMPANY)
    assert too_long.status_code == 422
    assert "6 h" in too_long.json()["detail"]
    no_insurance = await client.post(
        f"{url}/approve", json=placement(insurer=None), headers=COMPANY
    )
    assert no_insurance.status_code == 422
    assert "seguro" in no_insurance.json()["detail"]
    start = date.today()
    three_years = await client.post(
        f"{url}/approve",
        json=placement(
            start_date=start.isoformat(), end_date=(start + timedelta(days=3 * 365)).isoformat()
        ),
        headers=COMPANY,
    )
    assert three_years.status_code == 422
    assert "2 anos" in three_years.json()["detail"]


async def test_invalid_transitions_return_409(client):
    created = (await submit(client)).json()
    url = f"/applications/{created['id']}"
    approve_early = await client.post(f"{url}/approve", json=placement(), headers=COMPANY)
    assert approve_early.status_code == 409
    assert (await client.post(f"{url}/reject", json={}, headers=COMPANY)).status_code == 409
    assert (await client.post(f"{url}/complete", json={}, headers=COMPANY)).status_code == 409
    withdrawn = await client.post(f"{url}/withdraw", json={"reason": "outra vaga"}, headers=STUDENT)
    assert withdrawn.json()["status"] == "withdrawn"
    assert withdrawn.json()["status_reason"] == "outra vaga"
    assert (await client.post(f"{url}/review", headers=COMPANY)).status_code == 409


async def test_reject_and_terminate_paths(client):
    created = (await submit(client)).json()
    url = f"/applications/{created['id']}"
    await client.post(f"{url}/review", headers=COMPANY)
    rejected = await client.post(f"{url}/reject", json={"reason": "perfil"}, headers=COMPANY)
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["allowed_transitions"] == []
    assert (await client.post(f"{url}/terminate", json={}, headers=COORDINATOR)).status_code == 409


async def test_access_control(client):
    created = (await submit(client)).json()
    url = f"/applications/{created['id']}"
    assert (await client.get(url, headers=STUDENT)).status_code == 200
    assert (await client.get(url, headers=COMPANY)).status_code == 200
    assert (await client.get(url, headers=COORDINATOR)).status_code == 200
    assert (await client.get(url, headers=OTHER_STUDENT)).status_code == 403
    assert (await client.get(url, headers=OTHER_COMPANY)).status_code == 403
    assert (await client.post(f"{url}/review", headers=OTHER_COMPANY)).status_code == 403
    assert (await client.post(f"{url}/review", headers=STUDENT)).status_code == 403
    assert (await client.get("/applications/999", headers=COORDINATOR)).status_code == 404


async def test_lists_board_stats_and_placements(client):
    approved = await approved_application(client)
    mine = (await client.get("/applications", headers=STUDENT)).json()
    assert [a["id"] for a in mine] == [approved["id"]]
    assert (await client.get("/applications", headers=OTHER_COMPANY)).json() == []
    filtered = await client.get(
        "/applications?status=approved&internship_id=10", headers=COORDINATOR
    )
    assert len(filtered.json()) == 1
    board = (await client.get("/applications/board", headers=COMPANY)).json()
    assert board["total"] == 1
    assert len(board["columns"]["approved"]) == 1
    assert set(board["columns"]) >= {"submitted", "active", "closed"}
    stats = (await client.get("/applications/stats", headers=COMPANY)).json()
    assert stats["approved"] == 1 and stats["active"] == 0
    approved_placements = await client.get("/placements?status=approved", headers=COORDINATOR)
    summary = approved_placements.json()[0]
    assert summary["student_name"] == "Ana Souza"
    assert summary["report_state"] == "n/a"
    assert summary["max_end_date"] is not None
    assert (await client.get("/placements", headers=COORDINATOR)).json() == []
