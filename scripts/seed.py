"""Load the SYNTHETIC demo data through the API Gateway (``make seed``).

Everything goes through the public API, so the normal events flow and every
read model (recommendations, notifications) is fed exactly like in real use.
The script is idempotent: existing accounts are reused, offers are published
once per company and repeated transitions are ignored (HTTP 409).

Fictitious demo accounts (also listed in the README):

* coordenacao@ufal.test / Coord@2026 — coordenação de estágio
* rh@techsolucoes.test / Empresa@2026 — empresa concedente
* estudante@ufal.test / Estudante@2026 — estudante com perfil completo
* calouro@ufal.test / Estudante@2026 — estudante sem perfil (cold start)
* demais contas: senha Demo@2026
"""

import io
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import httpx
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).resolve().parent))
from synthetic_data import generate, save  # noqa: E402

from eh_auth import JWTAuth  # noqa: E402

GATEWAY = os.environ.get("GATEWAY_URL", "http://localhost:8000")
COORDINATOR = ("coordenacao@ufal.test", "Coord@2026", "Helena Duarte (fictícia)")
COLD_START = ("calouro@ufal.test", "Estudante@2026", "Caio Calouro (fictício)")
TODAY = date.today()


class Api:
    """Small helper around the gateway with logging of unexpected answers."""

    def __init__(self) -> None:
        self.http = httpx.Client(base_url=GATEWAY, timeout=60)
        self.service = {"Authorization": f"Bearer {JWTAuth(os.environ['JWT_SECRET']).create_service_token('seed')}"}

    def call(self, method: str, path: str, headers=None, ok=(200, 201), **kwargs) -> httpx.Response:
        response = self.http.request(method, path, headers=headers or {}, **kwargs)
        if response.status_code not in ok and response.status_code not in (409,):
            print(f"  ! {method} {path} -> {response.status_code}: {response.text[:160]}")
        return response

    def account(self, email: str, password: str, name: str, role: str) -> tuple[dict, int]:
        headers = self.service if role == "coordinator" else {}
        self.call("POST", "/api/auth/register", headers,
                  json={"email": email, "password": password, "full_name": name, "role": role})
        login = self.http.post("/api/auth/login", json={"email": email, "password": password})
        login.raise_for_status()
        body = login.json()
        return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]["id"]


def wait_for_stack(api: Api, timeout: float = 180) -> None:
    """Wait until the gateway reports every service up."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if api.http.get("/services").json()["status"] == "up":
                return
        except (httpx.HTTPError, ValueError, KeyError):
            pass
        time.sleep(3)
    raise SystemExit("A stack não ficou saudável a tempo — rode `make up` primeiro.")


def report_pdf(title: str, student: str) -> bytes:
    """A small fictitious activity report in PDF."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(72, 770, title)
    pdf.setFont("Helvetica", 11)
    pdf.drawString(72, 745, f"Estagiário(a): {student}")
    pdf.drawString(72, 725, "Documento fictício gerado pelo seed do EstágioHub.")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def wait_status(api: Api, headers: dict, application_id: int, status: str, timeout: float = 30) -> dict:
    """Poll an application until the saga reaches ``status``."""
    deadline = time.time() + timeout
    body: dict = {}
    while time.time() < deadline:
        body = api.http.get(f"/api/applications/{application_id}", headers=headers).json()
        if body.get("status") == status:
            return body
        time.sleep(0.5)
    print(f"  ! candidatura {application_id} não chegou a {status} (está em {body.get('status')})")
    return body


def main() -> int:
    """Seed the whole demo state."""
    dataset = generate()
    save(dataset)
    api = Api()
    wait_for_stack(api)
    print(f"Seed via {GATEWAY} — dados SINTÉTICOS (seed {dataset.meta['seed']})")

    coord, _ = api.account(*COORDINATOR, "coordinator")
    print("✓ coordenação")

    companies: dict[str, tuple[dict, int]] = {}
    offers: dict[str, int] = {}
    for index, company in enumerate(dataset.companies):
        password = "Empresa@2026" if index == 0 else "Demo@2026"
        headers, company_id = api.account(company.email, password, company.name, "company")
        companies[company.key] = (headers, company_id)
        api.call("PUT", "/api/profiles/companies/me", headers, json={
            "trade_name": company.name, "sector": company.sector, "city": company.city,
            "description": company.description, "cnpj": f"00.000.000/000{index + 1}-00",
        })
        mine = {(v["title"], v["description"]): v["id"] for v in api.http.get("/api/internships/mine", headers=headers).json()}
        for offer in [v for v in dataset.internships if v.company_key == company.key]:
            key = (offer.title, offer.description)
            if key not in mine:
                created = api.call("POST", "/api/internships", headers, json={
                    "title": offer.title, "description": offer.description,
                    "requirements": offer.requirements, "course": offer.course,
                    "min_semester": offer.min_semester, "hours_per_day": offer.hours_per_day,
                    "hours_per_week": offer.hours_per_week, "modality": offer.modality,
                    "city": offer.city, "stipend": offer.stipend,
                })
                mine[key] = created.json()["id"]
            offers[offer.key] = mine[key]
    print(f"✓ {len(companies)} empresas e {len(offers)} vagas")

    students: dict[str, tuple[dict, int]] = {}
    for index, s in enumerate(dataset.students):
        password = "Estudante@2026" if index == 0 else "Demo@2026"
        headers, student_id = api.account(s.email, password, s.name, "student")
        students[s.key] = (headers, student_id)
        api.call("PUT", "/api/profiles/students/me", headers, json={
            "course": s.course, "semester": s.semester, "skills": s.skills,
            "resume_summary": s.resume_summary, "weekly_availability_hours": s.weekly_availability_hours,
            "preferred_modality": s.preferred_modality, "city": s.city, "is_pcd": s.is_pcd,
            "enrollment": f"2026{index + 1:04d}",
        })
    api.account(*COLD_START, "student")
    print(f"✓ {len(students) + 1} estudantes (1 sem perfil, para cold start)")

    # Applications: each student (but the demo one) applies to up to 2 relevant offers.
    best: dict[str, list[tuple[int, str]]] = {}
    for label in dataset.labels:
        best.setdefault(label["student"], []).append((-label["relevance"], label["internship"]))
    created: list[tuple[int, str, str]] = []  # (application id, student key, offer key)
    for s in dataset.students[1:36]:
        for _, offer_key in sorted(best.get(s.key, []))[:2]:
            response = api.call("POST", "/api/applications", students[s.key][0],
                                json={"internship_id": offers[offer_key], "cover_letter": "Tenho interesse na vaga."},
                                ok=(201, 409, 422))
            if response.status_code == 201:
                created.append((response.json()["id"], s.key, offer_key))
    print(f"✓ {len(created)} candidaturas novas")

    company_of = {v.key: v.company_key for v in dataset.internships}

    def as_company(offer_key: str) -> dict:
        return companies[company_of[offer_key]][0]

    def approve(app_id: int, offer_key: str, start: date, days: int) -> None:
        headers = as_company(offer_key)
        api.call("POST", f"/api/applications/{app_id}/review", headers)
        api.call("POST", f"/api/applications/{app_id}/approve", headers, json={
            "start_date": start.isoformat(), "end_date": (start + timedelta(days=days)).isoformat(),
            "supervisor_name": "Supervisor(a) fictício(a)", "insurer": "Seguradora Exemplo S.A. (fictícia)",
            "insurance_policy": f"AP-{app_id:05d}", "activities": "Atividades do plano de estágio (fictício).",
        })

    # Placements in interesting states (only for applications created in this run).
    plans = [  # (start offset in days, duration, coordination approves?)
        (-176, 365, True),   # active, report due in a few days
        (-200, 300, True),   # active, report overdue
        (-700, 729, True),   # active, close to the 2-year limit
        (-60, 300, True),    # active, report submitted below
        (15, 180, False),    # TCE waiting for coordination
        (20, 200, False),    # TCE waiting for coordination
    ]
    distinct = list({student: (a, student, o) for a, student, o in reversed(created)}.values())[::-1]
    placed = distinct[: len(plans)]
    placed_ids = {a for a, _, _ in placed}
    for (app_id, _, offer_key), (offset, days, _) in zip(placed, plans, strict=False):
        approve(app_id, offer_key, TODAY + timedelta(days=offset), days)
    for (app_id, student_key, offer_key), (_, _, coordination) in zip(placed, plans, strict=False):
        pending = wait_status(api, students[student_key][0], app_id, "agreement_pending")
        agreement = (pending.get("placement") or {}).get("agreement_id")
        if coordination and agreement:
            api.call("POST", f"/api/agreements/{agreement}/approve", coord)
            wait_status(api, students[student_key][0], app_id, "active")
    if len(placed) >= 4:
        app_id, student_key, _ = placed[3]
        student = next(s for s in dataset.students if s.key == student_key)
        api.call("POST", "/api/reports", students[student_key][0],
                 data={"application_id": str(app_id), "title": "Relatório de atividades — 1º bimestre",
                       "period_start": (TODAY - timedelta(days=60)).isoformat(), "period_end": TODAY.isoformat()},
                 files={"file": ("relatorio.pdf", report_pdf("Relatório de atividades", student.name), "application/pdf")})

    # Other applications: some under review, some rejected or withdrawn.
    for i, (app_id, student_key, offer_key) in enumerate(a for a in created if a[0] not in placed_ids):
        if i % 4 in (0, 1):
            api.call("POST", f"/api/applications/{app_id}/review", as_company(offer_key))
        if i % 4 == 1 and i % 8 == 1:
            api.call("POST", f"/api/applications/{app_id}/reject", as_company(offer_key),
                     json={"reason": "Perfil não aderente nesta seleção (fictício)."})
        if i % 9 == 2:
            api.call("POST", f"/api/applications/{app_id}/withdraw", students[student_key][0],
                     json={"reason": "Aceitei outra oportunidade (fictício)."})

    # The demo student applies to an offer of the demo company, left "under review" for the live demo.
    demo_student, demo_company = dataset.students[0], dataset.companies[0]
    demo_offer = next(
        (k for _, k in sorted(best.get(demo_student.key, [])) if company_of[k] == demo_company.key),
        None,
    )
    if demo_offer:
        response = api.call("POST", "/api/applications", students[demo_student.key][0],
                            json={"internship_id": offers[demo_offer],
                                  "cover_letter": "Gostaria muito de participar do time."}, ok=(201, 409))
        if response.status_code == 201:
            api.call("POST", f"/api/applications/{response.json()['id']}/review", as_company(demo_offer))

    api.call("POST", "/api/recommendations/rebuild", api.service)
    api.call("POST", "/api/agents/follow-up/run", coord)
    print("✓ estados de demonstração (TCE pendentes, estágios ativos, relatório, alertas)")
    print(
        "\nContas de demonstração (fictícias):\n"
        "  coordenação  coordenacao@ufal.test   Coord@2026\n"
        "  empresa      rh@techsolucoes.test    Empresa@2026\n"
        "  estudante    estudante@ufal.test     Estudante@2026\n"
        "  cold start   calouro@ufal.test       Estudante@2026\n"
        "  demais       (veja data/synthetic/dataset.json)  Demo@2026"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
