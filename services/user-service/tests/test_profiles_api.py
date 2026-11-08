from conftest import login, register

PROFILE = {
    "course": "Ciência da Computação",
    "semester": 5,
    "skills": ["Python", " python ", "SQL", "Docker  Compose"],
    "resume_summary": "Monitora de algoritmos, projetos com FastAPI.",
    "weekly_availability_hours": 30,
    "preferred_modality": "hybrid",
    "city": "Maceió",
    "is_pcd": False,
}


async def test_new_student_has_empty_profile(client):
    await register(client, "ana@ufal.test")
    headers = await login(client, "ana@ufal.test")
    body = (await client.get("/profiles/students/me", headers=headers)).json()
    assert body["skills"] == []
    assert body["completeness"] == 0.0


async def test_update_profile_normalises_and_publishes_event(client, publisher):
    await register(client, "ana@ufal.test")
    headers = await login(client, "ana@ufal.test")
    response = await client.put("/profiles/students/me", json=PROFILE, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["skills"] == ["Python", "SQL", "Docker Compose"]
    assert body["completeness"] == 1.0
    event = publisher.of_type("profile.updated")[-1]
    assert event.payload["skills"] == ["Python", "SQL", "Docker Compose"]
    assert event.payload["course"] == "Ciência da Computação"
    assert event.payload["name"] == "Ana Souza"


async def test_weekly_availability_above_legal_limit_is_rejected(client):
    await register(client, "ana@ufal.test")
    headers = await login(client, "ana@ufal.test")
    response = await client.put(
        "/profiles/students/me", json={**PROFILE, "weekly_availability_hours": 40}, headers=headers
    )
    assert response.status_code == 422


async def test_company_cannot_edit_student_profile(client):
    await register(client, "rh@acme.test", role="company", name="ACME")
    headers = await login(client, "rh@acme.test")
    response = await client.put("/profiles/students/me", json=PROFILE, headers=headers)
    assert response.status_code == 403


async def test_student_profile_visibility(client):
    ana = (await register(client, "ana@ufal.test")).json()
    bob = (await register(client, "bob@ufal.test", name="Bob")).json()
    await register(client, "rh@acme.test", role="company", name="ACME")
    company = await login(client, "rh@acme.test")
    bob_headers = await login(client, "bob@ufal.test")
    assert (await client.get(f"/profiles/students/{ana['id']}", headers=company)).status_code == 200
    forbidden = await client.get(f"/profiles/students/{ana['id']}", headers=bob_headers)
    assert forbidden.status_code == 403
    own = await client.get(f"/profiles/students/{bob['id']}", headers=bob_headers)
    assert own.status_code == 200
    assert (await client.get("/profiles/students/999", headers=company)).status_code == 404


async def test_batch_profiles(client):
    a = (await register(client, "a@ufal.test")).json()
    b = (await register(client, "b@ufal.test", name="Bea")).json()
    c = (await register(client, "rh@acme.test", role="company", name="ACME")).json()
    company = await login(client, "rh@acme.test")
    url = f"/profiles/students?ids={a['id']},{b['id']},{c['id']}"
    response = await client.get(url, headers=company)
    assert [p["user_id"] for p in response.json()] == [a["id"], b["id"]]
    assert (await client.get("/profiles/students?ids=x", headers=company)).status_code == 422


async def test_company_profile_roundtrip(client):
    created = (await register(client, "rh@acme.test", role="company", name="ACME")).json()
    headers = await login(client, "rh@acme.test")
    mine = (await client.get("/profiles/companies/me", headers=headers)).json()
    assert mine["trade_name"] == "ACME"
    update = {
        "trade_name": "ACME Tecnologia",
        "sector": "Software",
        "city": "Maceió",
        "description": "x",
    }
    response = await client.put("/profiles/companies/me", json=update, headers=headers)
    assert response.json()["sector"] == "Software"
    await register(client, "ana@ufal.test")
    student = await login(client, "ana@ufal.test")
    public = (await client.get(f"/profiles/companies/{created['id']}", headers=student)).json()
    assert public["trade_name"] == "ACME Tecnologia"
    assert (await client.get("/profiles/companies/999", headers=student)).status_code == 404
