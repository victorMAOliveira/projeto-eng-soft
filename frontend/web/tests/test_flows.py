from conftest import login_as

APP = {
    "id": 7,
    "internship_id": 3,
    "student_id": 1,
    "company_id": 5,
    "student_name": "Ana Souza",
    "company_name": "ACME",
    "internship_title": "Estágio Backend",
    "student_course": "Ciência da Computação",
    "cover_letter": "Olá",
    "status": "under_review",
    "status_reason": None,
    "allowed_transitions": ["approved", "rejected", "withdrawn"],
    "placement": None,
    "history": [
        {
            "from_status": None,
            "to_status": "submitted",
            "actor_role": "student",
            "reason": None,
            "created_at": "2026-11-08T12:00:00Z",
        },
        {
            "from_status": "submitted",
            "to_status": "under_review",
            "actor_role": "company",
            "reason": None,
            "created_at": "2026-11-08T12:05:00Z",
        },
    ],
    "created_at": "2026-11-08T12:00:00Z",
    "updated_at": "2026-11-08T12:05:00Z",
}
PLACEMENT = {
    "start_date": "2026-12-01",
    "end_date": "2027-11-30",
    "hours_per_day": 6,
    "hours_per_week": 30,
    "stipend": 1500.0,
    "insurer": "Seguradora",
    "insurance_policy": "AP-1",
    "supervisor_name": "Carla",
    "activities": "",
    "agreement_id": "tce-1",
    "activated_at": None,
    "last_report_at": None,
    "next_report_due": "2027-06-01",
    "reports_count": 0,
}
TCE = {
    "id": "tce-1",
    "application_id": 7,
    "student_name": "Ana Souza",
    "company_name": "ACME",
    "internship_title": "Estágio Backend",
    "version": 1,
    "status": "pending_approval",
    "created_at": "2026-11-08T12:10:00Z",
    "approved_at": None,
    "terms": PLACEMENT,
}
SUMMARY = {
    "application_id": 7,
    "student_id": 1,
    "student_name": "Ana Souza",
    "company_id": 5,
    "company_name": "ACME",
    "internship_title": "Estágio Backend",
    "status": "active",
    "is_pcd": False,
    "start_date": "2026-12-01",
    "end_date": "2027-11-30",
    "hours_per_day": 6,
    "hours_per_week": 30,
    "agreement_id": "tce-1",
    "last_report_at": None,
    "next_report_due": "2026-11-20",
    "reports_count": 0,
    "report_state": "due_soon",
    "days_to_report": 12,
    "max_end_date": "2028-11-30",
}
REPORT = {
    "id": "rel-1",
    "application_id": 7,
    "student_id": 1,
    "company_id": 5,
    "student_name": "Ana Souza",
    "internship_title": "Estágio Backend",
    "title": "Relatório 1",
    "period_start": "2026-12-01",
    "period_end": "2027-05-31",
    "status": "submitted",
    "review_comment": None,
    "created_at": "2027-06-01T10:00:00Z",
    "versions": [
        {"version": 1, "filename": "r.pdf", "size_bytes": 10, "uploaded_at": "2027-06-01T10:00:00Z"}
    ],
}
STATS = {
    s: 1
    for s in (
        "submitted",
        "under_review",
        "approved",
        "agreement_pending",
        "active",
        "completed",
        "rejected",
        "withdrawn",
        "terminated",
    )
}
NOTICES = {
    "items": [
        {
            "id": "n1",
            "recipient": "user:1",
            "title": "TCE gerado",
            "message": "m",
            "kind": "info",
            "link": "/termos/tce-1",
            "event_type": "agreement.generated",
            "created_at": "2026-11-08T12:10:00Z",
            "read": False,
        }
    ],
    "unread": 1,
}


async def test_student_applies_and_sees_board(client, gw):
    gw.add("POST", "/api/applications", {**APP, "status": "submitted"}, status=201)
    gw.add(
        "GET",
        "/api/applications/board",
        {
            "columns": {
                "submitted": [],
                "under_review": [APP],
                "approved": [],
                "agreement_pending": [],
                "active": [],
                "completed": [],
                "closed": [],
            },
            "total": 1,
        },
        service="application-service",
    )
    login_as(client)
    applied = await client.post("/vagas/3/candidatar", data={"cover_letter": "Olá"})
    assert applied.headers["location"] == "/candidaturas/7"
    board = await client.get("/candidaturas")
    assert "Em análise" in board.text and "Estágio Backend" in board.text
    assert 'data-service="application-service"' in board.text
    gw.add("POST", "/api/applications", {"detail": "Você já se candidatou a esta vaga"}, status=409)
    again = await client.post("/vagas/3/candidatar", data={})
    assert again.headers["location"] == "/vagas/3"


async def test_detail_and_transitions(client, gw):
    gw.add(
        "GET", "/api/applications/7", {**APP, "placement": PLACEMENT}, service="application-service"
    )
    gw.add("POST", "/api/applications/7/reject", {**APP, "status": "rejected"})
    gw.add("POST", "/api/applications/7/withdraw", {"detail": "Transição inválida"}, status=409)
    login_as(client, "company", 5, "ACME")
    page = await client.get("/candidaturas/7")
    assert "Seguradora" in page.text and "Rejeitar" in page.text
    rejected = await client.post(
        "/candidaturas/7/rejeitar", data={"reason": "perfil", "back": "/candidaturas"}
    )
    assert rejected.headers["location"] == "/candidaturas"
    assert b'"reason":"perfil"' in gw.calls[-1].content
    assert (await client.post("/candidaturas/7/explodir")).status_code == 404
    login_as(client)
    invalid = await client.post("/candidaturas/7/retirar")
    assert invalid.headers["location"] == "/candidaturas/7"
    gw.add("GET", "/api/applications/8", {"detail": "x"}, status=404)
    assert (await client.get("/candidaturas/8")).status_code == 404


async def test_approve_form_success_and_legal_error(client, gw):
    gw.add("GET", "/api/applications/7", APP)
    gw.add("POST", "/api/applications/7/approve", {**APP, "status": "approved"})
    login_as(client, "company", 5, "ACME")
    assert "Termo de Compromisso" in (await client.get("/candidaturas/7/aprovar")).text
    form = {
        "start_date": "2026-12-01",
        "end_date": "2027-11-30",
        "supervisor_name": "Carla",
        "insurer": "Seg",
        "insurance_policy": "AP",
        "hours_per_day": "6",
        "hours_per_week": "30",
    }
    ok = await client.post("/candidaturas/7/aprovar", data=form)
    assert ok.headers["location"] == "/candidaturas/7"
    gw.add("POST", "/api/applications/7/approve", {"detail": "O TCE exige seguro"}, status=422)
    error = await client.post("/candidaturas/7/aprovar", data={**form, "insurer": ""})
    assert "O TCE exige seguro" in error.text


async def test_candidates_page(client, gw):
    gw.add("GET", "/api/internships/3", {"id": 3, "title": "Estágio Backend"})
    gw.add("GET", "/api/applications", [APP], service="application-service")
    login_as(client, "company", 5, "ACME")
    page = await client.get("/vagas/3/candidatos")
    assert "Ana Souza" in page.text
    assert gw.calls[-1].url.params["internship_id"] == "3"


async def test_agreements_pages_and_binary_proxy(client, gw):
    gw.add("GET", "/api/agreements", [TCE], service="document-service")
    gw.add("GET", "/api/agreements/tce-1", TCE, service="document-service")
    gw.add("POST", "/api/agreements/tce-1/approve", {**TCE, "status": "approved"})
    login_as(client, "coordinator", 9, "Coordenação")
    assert "tce-1" in (await client.get("/termos?status=pending_approval")).text
    detail = await client.get("/termos/tce-1")
    assert "Aprovar TCE" in detail.text and "/termos/tce-1/preview.png" in detail.text
    approved = await client.post("/termos/tce-1/aprovar")
    assert approved.headers["location"] == "/termos/tce-1"
    gw.add(
        "POST", "/api/agreements/tce-1/approve", {"detail": "Este TCE já foi aprovado"}, status=409
    )
    assert (await client.post("/termos/tce-1/aprovar")).status_code == 303
    gw.add("GET", "/api/agreements/nope", {"detail": "x"}, status=404)
    assert (await client.get("/termos/nope")).status_code == 404
    # binary proxy: the fake gateway answers JSON, the proxy just relays the bytes
    gw.add("GET", "/api/agreements/tce-1/pdf", {"pdf": True}, service="document-service")
    pdf = await client.get("/termos/tce-1/pdf")
    assert pdf.headers["content-type"] == "application/pdf"
    missing = await client.get("/termos/nope/preview.png")
    assert missing.status_code == 404


async def test_reports_flow(client, gw):
    gw.add("GET", "/api/reports", [REPORT], service="document-service")
    gw.add("GET", "/api/placements", [SUMMARY], service="application-service")
    gw.add("POST", "/api/reports", REPORT, status=201)
    gw.add("POST", "/api/reports/rel-1/versions", REPORT, status=201)
    gw.add("POST", "/api/reports/rel-1/review", {**REPORT, "status": "reviewed"})
    gw.add("GET", "/api/reports/rel-1/versions/1/file", {"pdf": True})
    login_as(client)
    page = await client.get("/relatorios")
    assert (
        "Relatório 1" in page.text
        and "Enviar relatório" in page.text
        and "vence em 12" in page.text
    )
    files = {"file": ("r.pdf", b"%PDF-1.4", "application/pdf")}
    data = {
        "application_id": "7",
        "title": "Relatório 1",
        "period_start": "2026-12-01",
        "period_end": "2027-05-31",
    }
    sent = await client.post("/relatorios", data=data, files=files)
    assert sent.headers["location"] == "/relatorios"
    assert b"multipart/form-data" in gw.calls[-1].headers["content-type"].encode()
    assert (await client.post("/relatorios", data=data)).headers["location"] == "/relatorios"
    assert (await client.post("/relatorios/rel-1/versoes", files=files)).status_code == 303
    assert (await client.post("/relatorios/rel-1/versoes")).status_code == 303
    assert (await client.get("/relatorios/rel-1/versoes/1")).status_code == 200
    gw.add("POST", "/api/reports", {"detail": "Envie o relatório em PDF"}, status=422)
    assert (await client.post("/relatorios", data=data, files=files)).status_code == 303
    login_as(client, "coordinator", 9)
    assert (
        await client.post("/relatorios/rel-1/revisar", data={"comment": "ok"})
    ).status_code == 303
    gw.add("POST", "/api/reports/rel-1/review", {"detail": "x"}, status=404)
    assert (await client.post("/relatorios/rel-1/revisar", data={})).status_code == 303


async def test_notifications_and_counter(client, gw):
    gw.add("GET", "/api/notifications", NOTICES, service="notification-service")
    gw.add("POST", "/api/notifications/read-all", {"unread": 0})
    gw.add("GET", "/api/notifications/unread-count", {"unread": 3})
    assert (await client.get("/notificacoes/contador")).text == ""
    login_as(client)
    page = await client.get("/notificacoes")
    assert "TCE gerado" in page.text and "agreement.generated" in page.text
    assert (await client.post("/notificacoes/ler-todas")).status_code == 303
    counter = await client.get("/notificacoes/contador")
    assert ">3<" in counter.text


async def test_dashboards_with_sprint2_panels(client, gw):
    gw.add("GET", "/api/applications/stats", STATS, service="application-service")
    gw.add("GET", "/api/placements", [SUMMARY], service="application-service")
    gw.add("GET", "/api/notifications", NOTICES, service="notification-service")
    gw.add("GET", "/api/agreements", [TCE], service="document-service")
    gw.add(
        "GET",
        "/api/internships/stats",
        {"open": 2, "closed": 0, "by_course": {"CC": 2}, "by_modality": {}},
    )
    gw.add("GET", "/api/internships", {"items": [], "total": 0, "page": 1, "size": 5})
    gw.add("GET", "/api/internships/mine", [])
    gw.add(
        "GET",
        "/api/profiles/students/me",
        {"user_id": 1, "name": "Ana", "email": "a", "skills": [], "completeness": 0.2},
    )
    login_as(client, "coordinator", 9, "Coordenação")
    coord = await client.get("/")
    assert "TCE aguardando aprovação" in coord.text and "Revisar" in coord.text
    assert 'data-service="notification-service"' in coord.text
    login_as(client)
    student = await client.get("/")
    assert "Meu estágio" in student.text
    login_as(client, "company", 5, "ACME")
    assert "Candidaturas a analisar" in (await client.get("/")).text
