from conftest import fake_jwt, login_as
from web_frontend.gateway import error_message
from web_frontend.session import decode_claims

VAGA = {
    "id": 7,
    "title": "Estágio Backend",
    "description": "APIs com FastAPI",
    "requirements": ["Python", "SQL"],
    "course": "Ciência da Computação",
    "min_semester": 4,
    "hours_per_day": 6,
    "hours_per_week": 30,
    "modality": "hybrid",
    "city": "Maceió",
    "stipend": 1200.0,
    "positions": 1,
    "company_id": 5,
    "company_name": "ACME",
    "status": "open",
    "published_at": "2026-11-08T12:00:00Z",
    "closed_at": None,
}
STATS = {"open": 3, "closed": 1, "by_course": {"Ciência da Computação": 3}, "by_modality": {}}
PROFILE = {
    "user_id": 1,
    "name": "Ana Souza",
    "email": "ana@ufal.test",
    "course": "Ciência da Computação",
    "semester": 5,
    "skills": ["Python"],
    "resume_summary": "",
    "weekly_availability_hours": 30,
    "preferred_modality": "hybrid",
    "city": "Maceió",
    "is_pcd": False,
    "completeness": 0.8,
}


def test_decode_claims_handles_bad_and_expired_tokens():
    assert decode_claims("not-a-jwt") is None
    assert decode_claims(fake_jwt())["role"] == "student"
    assert decode_claims("a.bm90LWpzb24.c") is None


def test_error_message_formats_validation_errors():
    body = {"detail": [{"loc": ["body", "hours_per_day"], "msg": "too big"}]}
    assert error_message(body, 422) == "hours_per_day: too big"
    assert error_message({"detail": "Proibido"}, 403) == "Proibido"
    assert error_message(None, 500) == "Erro 500"


async def test_anonymous_user_is_redirected_to_login(client):
    response = await client.get("/vagas")
    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=/vagas"
    htmx = await client.get("/vagas", headers={"HX-Request": "true"})
    assert htmx.headers["HX-Redirect"].startswith("/login")


async def test_login_sets_http_only_cookie(client, gw):
    gw.add(
        "POST",
        "/api/auth/login",
        {"access_token": fake_jwt(), "expires_in": 7200},
        service="user-service",
    )
    page = await client.get("/login")
    assert "Entrar" in page.text
    response = await client.post(
        "/login", data={"email": "ana@ufal.test", "password": "x", "next": "//evil.example"}
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "httponly" in response.headers["set-cookie"].lower()


async def test_login_failure_and_gateway_down(client, gw):
    gw.add("POST", "/api/auth/login", {"detail": "E-mail ou senha inválidos"}, status=401)
    response = await client.post("/login", data={"email": "a@b.co", "password": "x"})
    assert "E-mail ou senha inválidos." in response.text
    gw.down = True
    response = await client.post("/login", data={"email": "a@b.co", "password": "x"})
    assert "indisponível" in response.text


async def test_register_flow(client, gw):
    gw.add("POST", "/api/auth/register", {"id": 1}, status=201)
    assert "Criar conta" in (await client.get("/cadastro")).text
    ok = await client.post(
        "/cadastro",
        data={"full_name": "Ana", "email": "a@b.co", "password": "12345678", "role": "student"},
    )
    assert ok.headers["location"] == "/login"
    bad_role = await client.post(
        "/cadastro",
        data={"full_name": "Ana", "email": "a@b.co", "password": "12345678", "role": "coordinator"},
    )
    assert "Papel inválido" in bad_role.text
    gw.add("POST", "/api/auth/register", {"detail": "E-mail já cadastrado"}, status=409)
    dup = await client.post(
        "/cadastro",
        data={"full_name": "Ana", "email": "a@b.co", "password": "12345678", "role": "company"},
    )
    assert "E-mail já cadastrado" in dup.text


async def test_student_dashboard_shows_service_badges(client, gw):
    gw.add("GET", "/api/profiles/students/me", PROFILE, service="user-service")
    gw.add(
        "GET",
        "/api/internships",
        {"items": [VAGA], "total": 1, "page": 1, "size": 5},
        service="internship-service",
    )
    gw.add("GET", "/api/internships/stats", STATS, service="internship-service")
    login_as(client)
    page = await client.get("/")
    assert page.status_code == 200
    assert 'data-service="user-service"' in page.text
    assert 'data-service="internship-service"' in page.text
    assert "Estágio Backend" in page.text
    assert page.headers["X-Served-By"] == "web-frontend"


async def test_dashboard_degrades_when_a_service_is_unavailable(client, gw):
    gw.add("GET", "/api/profiles/students/me", PROFILE, service="user-service")
    gw.add("GET", "/api/internships", {"detail": "x", "service": "internship-service"}, status=503)
    gw.add(
        "GET",
        "/api/internships/stats",
        {"detail": "x", "service": "internship-service"},
        status=503,
    )
    login_as(client)
    page = await client.get("/")
    assert page.status_code == 200
    assert "internship-service" in page.text
    assert "Degradação graciosa" in page.text
    assert "Meu perfil acadêmico" in page.text


async def test_company_and_coordinator_dashboards(client, gw):
    gw.add("GET", "/api/internships/mine", [VAGA], service="internship-service")
    gw.add("GET", "/api/internships/stats", STATS, service="internship-service")
    gw.add("GET", "/api/internships", {"items": [VAGA], "total": 1, "page": 1, "size": 5})
    login_as(client, "company", 5, "ACME")
    assert "Minhas vagas" in (await client.get("/")).text
    login_as(client, "coordinator", 9, "Coordenação")
    assert "Vagas por curso" in (await client.get("/")).text


async def test_internship_list_detail_and_htmx_partial(client, gw):
    gw.add(
        "GET",
        "/api/internships",
        {"items": [VAGA], "total": 1, "page": 1, "size": 12},
        service="internship-service",
    )
    gw.add("GET", "/api/internships/7", VAGA, service="internship-service")
    login_as(client)
    full = await client.get("/vagas?q=python&modality=hybrid")
    assert "<html" in full.text and "Estágio Backend" in full.text
    query = gw.calls[-1].url.params
    assert query["q"] == "python" and query["modality"] == "hybrid"
    partial = await client.get("/vagas?q=python", headers={"HX-Request": "true"})
    assert "<html" not in partial.text and "Estágio Backend" in partial.text
    detail = await client.get("/vagas/7")
    assert "APIs com FastAPI" in detail.text
    gw.add("GET", "/api/internships/8", {"detail": "Vaga não encontrada"}, status=404)
    assert (await client.get("/vagas/8")).status_code == 404


async def test_company_creates_and_closes_internship(client, gw):
    gw.add("POST", "/api/internships", VAGA, status=201)
    gw.add("POST", "/api/internships/7/close", {**VAGA, "status": "closed"})
    gw.add("GET", "/api/internships/mine", [VAGA])
    login_as(client, "company", 5, "ACME")
    assert "Nova vaga" in (await client.get("/vagas/nova")).text
    form = {
        "title": "Estágio Backend",
        "description": "APIs com FastAPI",
        "requirements": "Python, SQL",
        "course": "Ciência da Computação",
        "min_semester": "4",
        "hours_per_day": "6",
        "hours_per_week": "30",
        "modality": "hybrid",
        "city": "Maceió",
        "stipend": "1200,50",
        "positions": "1",
    }
    created = await client.post("/vagas", data=form)
    assert created.headers["location"] == "/vagas/7"
    sent = gw.calls[-1]
    assert b'"requirements":["Python","SQL"]' in sent.content
    assert b'"stipend":1200.5' in sent.content
    gw.add(
        "POST",
        "/api/internships",
        {"detail": [{"loc": ["body", "hours_per_day"], "msg": "max 6"}]},
        status=422,
    )
    invalid = await client.post("/vagas", data={**form, "hours_per_day": "8"})
    assert "hours_per_day: max 6" in invalid.text
    closed = await client.post("/vagas/7/encerrar")
    assert closed.headers["location"] == "/vagas/7"
    mine = await client.get("/vagas?mine=1")
    assert "Minhas vagas" in mine.text


async def test_student_profile_save(client, gw):
    gw.add("GET", "/api/profiles/students/me", PROFILE, service="user-service")
    gw.add("PUT", "/api/profiles/students/me", PROFILE, service="user-service")
    login_as(client)
    assert "Dados acadêmicos" in (await client.get("/perfil")).text
    saved = await client.post(
        "/perfil",
        data={
            "course": "Ciência da Computação",
            "semester": "5",
            "skills": "Python, SQL",
            "weekly_availability_hours": "30",
            "is_pcd": "on",
        },
    )
    assert saved.status_code == 303
    assert b'"skills":["Python","SQL"]' in gw.calls[-1].content
    assert b'"is_pcd":true' in gw.calls[-1].content
    gw.add("PUT", "/api/profiles/students/me", {"detail": "erro"}, status=422)
    failed = await client.post(
        "/perfil", data={"course": "X", "semester": "1", "weekly_availability_hours": "50"}
    )
    assert "erro" in failed.text


async def test_company_profile_save(client, gw):
    gw.add(
        "GET",
        "/api/profiles/companies/me",
        {"user_id": 5, "email": "rh@acme.test", "trade_name": "ACME"},
    )
    gw.add(
        "PUT",
        "/api/profiles/companies/me",
        {"user_id": 5, "email": "rh@acme.test", "trade_name": "ACME"},
    )
    login_as(client, "company", 5, "ACME")
    assert "Dados da concedente" in (await client.get("/perfil")).text
    assert (await client.post("/perfil", data={"trade_name": "ACME"})).status_code == 303


async def test_logout_and_404(client):
    login_as(client)
    response = await client.post("/logout")
    assert response.headers["location"] == "/login"
    assert (await client.get("/nao-existe")).status_code == 404
