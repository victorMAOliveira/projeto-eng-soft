import pytest
from conftest import VAGA, headers

from eh_auth import Role

COMPANY = headers(Role.COMPANY, 10, "ACME Tecnologia")
OTHER_COMPANY = headers(Role.COMPANY, 11, "Beta Sistemas")
STUDENT = headers(Role.STUDENT, 20, "Ana")
COORD = headers(Role.COORDINATOR, 30, "Coordenação")


async def publish(client, **overrides):
    response = await client.post("/internships", json={**VAGA, **overrides}, headers=COMPANY)
    assert response.status_code == 201, response.text
    return response.json()


async def test_company_publishes_internship_and_event(client, publisher):
    body = await publish(client)
    assert body["status"] == "open"
    assert body["company_id"] == 10
    assert body["company_name"] == "ACME Tecnologia"
    assert body["requirements"] == ["Python", "SQL", "Git"]
    event = publisher.of_type("internship.published")[0]
    assert event.payload["internship_id"] == body["id"]
    assert event.payload["requirements"] == ["Python", "SQL", "Git"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"hours_per_day": 7},  # > 6 h/day
        {"hours_per_week": 31},  # > 30 h/week
        {"hours_per_day": 4, "hours_per_week": 30},  # weekly > 6 * daily
        {"requirements": []},
        {"requirements": ["  "]},
        {"modality": "presencial"},
    ],
)
async def test_invalid_offers_are_rejected(client, overrides):
    response = await client.post("/internships", json={**VAGA, **overrides}, headers=COMPANY)
    assert response.status_code == 422


async def test_students_cannot_publish(client):
    assert (await client.post("/internships", json=VAGA, headers=STUDENT)).status_code == 403
    assert (await client.post("/internships", json=VAGA)).status_code == 401


async def test_search_filters_and_pagination(client):
    await publish(client)
    await publish(client, title="Estágio Frontend", requirements=["React"], modality="remote")
    await publish(client, title="Estágio Obras", course="Engenharia Civil", city="Arapiraca")
    page = (await client.get("/internships", headers=STUDENT)).json()
    assert page["total"] == 3
    assert page["items"][0]["title"] == "Estágio Obras"  # most recent first
    remote = (await client.get("/internships?modality=remote", headers=STUDENT)).json()
    assert [i["title"] for i in remote["items"]] == ["Estágio Frontend"]
    by_text = (await client.get("/internships?q=react", headers=STUDENT)).json()
    assert by_text["total"] == 1
    civil = await client.get(
        "/internships", params={"course": "Engenharia Civil", "city": "arapiraca"}, headers=STUDENT
    )
    assert civil.json()["total"] == 1
    paged = (await client.get("/internships?size=2&page=2", headers=STUDENT)).json()
    assert len(paged["items"]) == 1


async def test_get_detail_and_404(client):
    created = await publish(client)
    detail = await client.get(f"/internships/{created['id']}", headers=STUDENT)
    assert detail.json()["title"] == VAGA["title"]
    assert (await client.get("/internships/999", headers=STUDENT)).status_code == 404


async def test_close_rules_and_event(client, publisher):
    created = await publish(client)
    url = f"/internships/{created['id']}/close"
    assert (await client.post(url, headers=OTHER_COMPANY)).status_code == 403
    assert (await client.post(url, headers=STUDENT)).status_code == 403
    closed = await client.post(url, headers=COMPANY)
    assert closed.json()["status"] == "closed"
    assert closed.json()["closed_at"]
    assert (await client.post(url, headers=COMPANY)).status_code == 409
    assert publisher.of_type("internship.closed")[0].payload["internship_id"] == created["id"]
    assert (await client.post("/internships/999/close", headers=COORD)).status_code == 404
    open_only = (await client.get("/internships", headers=STUDENT)).json()
    assert open_only["total"] == 0
    everything = (await client.get("/internships?status=all", headers=STUDENT)).json()
    assert everything["total"] == 1


async def test_mine_and_stats(client):
    await publish(client)
    await publish(client, modality="remote")
    await client.post("/internships", json=VAGA, headers=OTHER_COMPANY)
    mine = (await client.get("/internships/mine", headers=COMPANY)).json()
    assert len(mine) == 2
    assert (await client.get("/internships/mine", headers=STUDENT)).status_code == 403
    stats = (await client.get("/internships/stats", headers=STUDENT)).json()
    assert stats["open"] == 3
    assert stats["closed"] == 0
    assert stats["by_course"] == {"Ciência da Computação": 3}
    assert stats["by_modality"]["remote"] == 1
