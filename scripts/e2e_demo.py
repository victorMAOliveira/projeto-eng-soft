"""End-to-end test of the main flow through the API Gateway (``make e2e``).

Runs against the Compose stack with fresh, uniquely named accounts:

1. registration and login with roles (company, student, coordination);
2. company publishes an offer (legal workload validated);
3. student fills the profile and receives the offer as an explained recommendation;
4. student applies; company sees the candidate ranking and approves (TCE terms);
5. the TCE PDF is generated automatically (saga) and can be downloaded;
6. coordination approves the TCE and the internship becomes active;
7. student submits an activity report; the follow-up agent runs with its trail;
8. every transition produced notifications for the actors involved;
9. an invalid transition returns HTTP 409 and the platform health is "up".

Exit code 0 only if every step passes.
"""

import os
import sys
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eh_auth import JWTAuth  # noqa: E402

GATEWAY = os.environ.get("GATEWAY_URL", "http://localhost:8000")
PASSWORD = "E2e@Senha2026"


class Step:
    """Pretty, numbered step reporter that stops at the first failure."""

    count = 0

    def __init__(self, title: str) -> None:
        Step.count += 1
        self.title = f"{Step.count:02d}. {title}"
        self.started = time.perf_counter()

    def __enter__(self) -> "Step":
        print(f"{self.title} ...", end=" ", flush=True)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        ms = (time.perf_counter() - self.started) * 1000
        if exc_type is None:
            print(f"ok ({ms:.0f} ms)")
            return False
        print(f"FALHOU: {exc}")
        raise SystemExit(1)


def expect(response: httpx.Response, *codes: int) -> dict | list:
    """Assert the status code and return the JSON body."""
    assert response.status_code in codes, f"{response.request.method} {response.request.url.path} -> {response.status_code}: {response.text[:300]}"
    return response.json() if response.content and "json" in response.headers.get("content-type", "") else {}


def poll(fetch, condition, timeout: float = 30.0, interval: float = 0.5):
    """Call ``fetch`` until ``condition(result)`` holds."""
    deadline = time.time() + timeout
    result = fetch()
    while not condition(result) and time.time() < deadline:
        time.sleep(interval)
        result = fetch()
    assert condition(result), f"condição não atingida em {timeout}s: {str(result)[:300]}"
    return result


def main() -> int:
    """Run the scenario."""
    tag = uuid.uuid4().hex[:8]
    api = httpx.Client(base_url=GATEWAY, timeout=60)
    service = {"Authorization": f"Bearer {JWTAuth(os.environ['JWT_SECRET']).create_service_token('e2e')}"}
    print(f"E2E via {GATEWAY} (execução {tag})\n")

    def login(email: str) -> tuple[dict, int]:
        body = expect(api.post("/api/auth/login", json={"email": email, "password": PASSWORD}), 200)
        return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]["id"]

    with Step("Cadastro e login com papéis (empresa, estudante, coordenação)"):
        accounts = {
            "company": (f"e2e-empresa-{tag}@empresas.test", "E2E Engenharia de Software Ltda (fictícia)"),
            "student": (f"e2e-estudante-{tag}@ufal.test", "Estudante E2E (fictícia)"),
            "coordinator": (f"e2e-coord-{tag}@ufal.test", "Coordenação E2E (fictícia)"),
        }
        for role, (email, name) in accounts.items():
            headers = service if role == "coordinator" else {}
            expect(api.post("/api/auth/register", headers=headers,
                            json={"email": email, "password": PASSWORD, "full_name": name, "role": role}), 201)
        company, _ = login(accounts["company"][0])
        student, student_id = login(accounts["student"][0])
        coordinator, _ = login(accounts["coordinator"][0])
        expect(api.get("/api/internships"), 401)  # gateway requires JWT

    with Step("Empresa publica vaga (jornada acima de 6 h/dia é rejeitada)"):
        offer = {
            "title": f"Estágio em Engenharia de Software {tag}",
            "description": "Desenvolver microsserviços em Python com FastAPI, eventos e testes automatizados.",
            "requirements": ["Python", "FastAPI", "Docker", "RabbitMQ"],
            "course": "Ciência da Computação", "min_semester": 4, "hours_per_day": 6,
            "hours_per_week": 30, "modality": "hybrid", "city": "Maceió", "stipend": 1600,
        }
        expect(api.post("/api/internships", headers=company, json={**offer, "hours_per_day": 8}), 422)
        expect(api.post("/api/internships", headers=student, json=offer), 403)
        vaga = expect(api.post("/api/internships", headers=company, json=offer), 201)

    with Step("Estudante preenche o perfil e recebe a vaga recomendada com explicação"):
        expect(api.put("/api/profiles/students/me", headers=student, json={
            "course": "Ciência da Computação", "semester": 6, "skills": ["Python", "FastAPI", "Docker", "SQL"],
            "resume_summary": "Desenvolvo APIs com Python e FastAPI e tenho interesse em microsserviços.",
            "weekly_availability_hours": 30, "preferred_modality": "hybrid", "city": "Maceió",
        }), 200)
        recs = poll(
            lambda: expect(api.get(f"/api/recommendations/students/{student_id}/internships",
                                   headers=student, params={"k": 50}), 200),
            lambda body: any(i["internship_id"] == vaga["id"] for i in body["items"]),
        )
        item = next(i for i in recs["items"] if i["internship_id"] == vaga["id"])
        assert item["matched_skills"] == ["Python", "FastAPI", "Docker"], item
        assert item["missing_skills"] == ["RabbitMQ"], item
        assert "3 de 4" in item["explanation"]

    with Step("Estudante se candidata; empresa vê o ranking e aprova com seguro"):
        application = expect(api.post("/api/applications", headers=student,
                                      json={"internship_id": vaga["id"], "cover_letter": "Quero participar."}), 201)
        app_id = application["id"]
        ranking = poll(
            lambda: expect(api.get(f"/api/recommendations/internships/{vaga['id']}/candidates", headers=company), 200),
            lambda body: any(i["student_id"] == student_id for i in body["items"]),
        )
        assert ranking["items"][0]["application_id"] == app_id
        expect(api.post(f"/api/applications/{app_id}/review", headers=company), 200)
        start = date.today() + timedelta(days=7)
        terms = {"start_date": start.isoformat(), "end_date": (start + timedelta(days=365)).isoformat(),
                 "supervisor_name": "Supervisora E2E (fictícia)", "insurer": "Seguradora Exemplo (fictícia)",
                 "insurance_policy": f"AP-E2E-{tag}"}
        expect(api.post(f"/api/applications/{app_id}/approve", headers=company,
                        json={**terms, "insurance_policy": None}), 422)  # TCE needs insurance
        approved = expect(api.post(f"/api/applications/{app_id}/approve", headers=company, json=terms), 200)
        assert approved["status"] == "approved"

    with Step("TCE gerado automaticamente em PDF (saga: approved → agreement_pending)"):
        pending = poll(lambda: expect(api.get(f"/api/applications/{app_id}", headers=student), 200),
                       lambda body: body["status"] == "agreement_pending")
        agreement_id = pending["placement"]["agreement_id"]
        pdf = api.get(f"/api/agreements/{agreement_id}/pdf", headers=student)
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF"), pdf.status_code
        assert pdf.headers["x-served-by"] == "document-service"

    with Step("Coordenação aprova o TCE e o estágio passa a ativo"):
        expect(api.post(f"/api/agreements/{agreement_id}/approve", headers=company), 403)
        expect(api.post(f"/api/agreements/{agreement_id}/approve", headers=coordinator), 200)
        active = poll(lambda: expect(api.get(f"/api/applications/{app_id}", headers=student), 200),
                      lambda body: body["status"] == "active")
        assert active["placement"]["next_report_due"]

    with Step("Estudante envia relatório; agente de acompanhamento roda com trilha"):
        report = expect(api.post(
            "/api/reports", headers=student,
            data={"application_id": str(app_id), "title": "Relatório parcial E2E",
                  "period_start": start.isoformat(), "period_end": (start + timedelta(days=30)).isoformat()},
            files={"file": ("relatorio.pdf", b"%PDF-1.4\n% relatorio e2e\n", "application/pdf")},
        ), 201)
        assert report["versions"][0]["version"] == 1
        poll(lambda: expect(api.get(f"/api/applications/{app_id}", headers=student), 200),
             lambda body: body["placement"]["reports_count"] == 1)
        run = expect(api.post("/api/agents/follow-up/run", headers=coordinator), 200)
        assert run["status"] == "completed" and run["steps"], run
        assert any(s["tool_name"] == "check_deadlines" for s in run["steps"])
        assistant = expect(api.post("/api/agents/application-assistant/run", headers=student,
                                    json={"internship_id": vaga["id"]}), 200)
        assert assistant["status"] == "completed"

    with Step("Cada transição gerou notificações para os envolvidos"):
        def titles(headers):
            return [n["title"] for n in expect(api.get("/api/notifications", headers=headers, params={"limit": 100}), 200)["items"]]

        student_titles = poll(lambda: titles(student), lambda t: "TCE aprovado — estágio ativo!" in t)
        assert {"Candidatura enviada", "TCE gerado"} <= set(student_titles), student_titles
        company_titles = poll(lambda: titles(company), lambda t: "Relatório enviado" in t)
        assert {"Vaga publicada", "Nova candidatura", "TCE aprovado"} <= set(company_titles), company_titles
        assert "TCE aguardando aprovação" in titles(coordinator)

    with Step("Transição inválida retorna 409 e todos os serviços estão no ar"):
        expect(api.post(f"/api/applications/{app_id}/withdraw", headers=student, json={}), 409)
        health = expect(api.get("/services"), 200)
        assert health["status"] == "up", [(s["name"], s["status"]) for s in health["services"]]

    print(f"\nE2E concluído com sucesso: {Step.count} etapas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
