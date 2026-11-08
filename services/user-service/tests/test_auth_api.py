from conftest import login, register


async def test_register_creates_account_and_publishes_event(client, publisher):
    response = await register(client, "Ana@UFAL.test")
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ana@ufal.test"
    assert body["role"] == "student"
    assert "password" not in body and "password_hash" not in body
    events = publisher.of_type("user.registered")
    assert len(events) == 1
    assert events[0].payload == {
        "user_id": body["id"],
        "email": "ana@ufal.test",
        "name": "Ana Souza",
        "role": "student",
    }


async def test_duplicate_email_is_conflict(client):
    await register(client, "dup@ufal.test")
    assert (await register(client, "DUP@ufal.test")).status_code == 409


async def test_invalid_payloads_are_rejected(client):
    assert (await register(client, "not-an-email")).status_code == 422
    assert (await register(client, "x@ufal.test", password="short")).status_code == 422
    assert (await register(client, "y@ufal.test", role="admin")).status_code == 422


async def test_coordinator_registration_requires_privileged_token(client, auth):
    assert (await register(client, "coord@ufal.test", role="coordinator")).status_code == 403
    service = {"Authorization": f"Bearer {auth.create_service_token('seed')}"}
    response = await register(client, "coord@ufal.test", role="coordinator", headers=service)
    assert response.status_code == 201


async def test_login_returns_jwt_with_role(client, auth):
    await register(client, "acme@empresa.test", role="company", name="ACME Ltda")
    response = await client.post(
        "/auth/login", json={"email": "ACME@empresa.test", "password": "SenhaForte1"}
    )
    assert response.status_code == 200
    body = response.json()
    principal = auth.decode(body["access_token"])
    assert principal.role == "company"
    assert principal.name == "ACME Ltda"
    assert body["expires_in"] == 120 * 60
    assert body["user"]["email"] == "acme@empresa.test"


async def test_login_with_wrong_password_or_unknown_user(client):
    await register(client, "bia@ufal.test")
    wrong = await client.post(
        "/auth/login", json={"email": "bia@ufal.test", "password": "errada123"}
    )
    unknown = await client.post(
        "/auth/login", json={"email": "zz@ufal.test", "password": "errada1"}
    )
    assert wrong.status_code == unknown.status_code == 401


async def test_users_me_and_get_user(client):
    created = (await register(client, "caio@ufal.test", name="Caio")).json()
    headers = await login(client, "caio@ufal.test")
    assert (await client.get("/users/me", headers=headers)).json()["full_name"] == "Caio"
    assert (await client.get(f"/users/{created['id']}", headers=headers)).status_code == 200
    assert (await client.get("/users/999", headers=headers)).status_code == 404
    assert (await client.get("/users/me")).status_code == 401


async def test_list_users_is_restricted(client, auth):
    await register(client, "a1@ufal.test")
    await register(client, "c1@empresa.test", role="company", name="C1")
    student = await login(client, "a1@ufal.test")
    assert (await client.get("/users", headers=student)).status_code == 403
    service = {"Authorization": f"Bearer {auth.create_service_token('agent-service')}"}
    companies = (await client.get("/users?role=company", headers=service)).json()
    assert [u["email"] for u in companies] == ["c1@empresa.test"]


async def test_routes_for_removed_accounts_return_404(client, auth):
    ghost = {"Authorization": f"Bearer {auth.create_token(user_id=42, role='student', name='x')}"}
    assert (await client.get("/users/me", headers=ghost)).status_code == 404
    assert (await client.get("/profiles/students/me", headers=ghost)).status_code == 404
    company = {"Authorization": f"Bearer {auth.create_token(user_id=43, role='company', name='y')}"}
    assert (await client.get("/profiles/companies/me", headers=company)).status_code == 404
