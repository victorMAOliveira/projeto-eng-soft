"""Capture the report screenshots by driving the real UI with Playwright.

The main flow is executed through the web interface itself (forms and
buttons), so each print shows the system actually being used:
company publishes an offer → student sees it recommended and applies →
company ranks and approves → TCE generated → coordination approves →
student submits a report → notifications → microservices status.

Most screens are captured with the "Mostrar microsserviços" toggle ON.
``--degraded`` captures the graceful-degradation screens (run it with the
recommendation and agent services stopped — see ``make screenshots``).

Runs inside ``mcr.microsoft.com/playwright/python`` (compose service
``screenshots``) and writes ``docs/relatorio/img/screens/*.png``.
"""

import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, sync_playwright

BASE = os.environ.get("FRONTEND_URL", "http://web-frontend:8080").rstrip("/")
OUT = Path(__file__).resolve().parent.parent / "docs" / "relatorio" / "img" / "screens"
STUDENT = ("estudante@ufal.test", "Estudante@2026")
COMPANY = ("rh@techsolucoes.test", "Empresa@2026")
COORDINATOR = ("coordenacao@ufal.test", "Coord@2026")
MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


def new_context(browser, show_services: bool = True) -> BrowserContext:
    """Desktop-sized context, optionally with the microservices toggle on."""
    context = browser.new_context(viewport={"width": 1440, "height": 900}, locale="pt-BR")
    if show_services:
        context.add_cookies([{"name": "eh_show_services", "value": "1", "url": BASE}])
    return context


def login(context: BrowserContext, credentials: tuple[str, str]) -> Page:
    """Log in through the login form and return the page (dashboard)."""
    page = context.new_page()
    page.goto(f"{BASE}/login")
    page.fill("input[name=email]", credentials[0])
    page.fill("input[name=password]", credentials[1])
    page.click("button[type=submit]")
    page.wait_for_url(f"{BASE}/")
    return page


def shot(page: Page, name: str, full_page: bool = False) -> None:
    """Save a screenshot once the page settled."""
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(300)
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=full_page)
    print(f"  ✓ {name}.png")


def wait_for(page: Page, url: str, text: str, timeout: float = 40) -> None:
    """Reload ``url`` until ``text`` appears (eventual consistency of events)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        page.goto(url)
        if text in page.content():
            return
        page.wait_for_timeout(700)
    raise RuntimeError(f"'{text}' não apareceu em {url}")


def main_flow(browser) -> None:
    """Run the main flow through the UI capturing each step."""
    anon = new_context(browser, show_services=False)
    page = anon.new_page()
    page.goto(f"{BASE}/login")
    shot(page, "01-login")
    anon.close()

    stamp = time.strftime("%H%M%S")
    title = f"Estágio em Microsserviços Python {stamp}"
    company_ctx, student_ctx, coord_ctx = (new_context(browser) for _ in range(3))

    company = login(company_ctx, COMPANY)
    shot(company, "02-dashboard-empresa")
    company.goto(f"{BASE}/vagas/nova")
    company.fill("input[name=title]", title)
    company.fill(
        "textarea[name=description]",
        "Desenvolver APIs REST em Python com FastAPI, PostgreSQL e Docker em arquitetura de microsserviços.",
    )
    company.fill("input[name=requirements]", "Python, SQL, Docker, Git")
    company.select_option("select[name=course]", "Ciência da Computação")
    company.fill("input[name=min_semester]", "4")
    company.select_option("select[name=modality]", "hybrid")
    company.fill("input[name=stipend]", "1500")
    shot(company, "03-empresa-publica-vaga", full_page=True)
    company.click("form[action='/vagas'] button[type=submit]")
    company.wait_for_url(f"{BASE}/vagas/*")
    internship_id = company.url.rstrip("/").split("/")[-1]
    shot(company, "04-vaga-publicada")

    student = login(student_ctx, STUDENT)
    shot(student, "05-dashboard-estudante", full_page=True)
    wait_for(student, f"{BASE}/recomendacoes", title)
    shot(student, "06-recomendacoes-explicadas", full_page=True)
    # The assistant runs before applying: applied offers leave the recommendations.
    student.goto(f"{BASE}/assistente?internship_id={internship_id}")
    student.click("form[action='/assistente/executar'] button[type=submit]")
    student.wait_for_selector("#run-result .trail")
    shot(student, "07-assistente-ia-trilha", full_page=True)
    student.goto(f"{BASE}/vagas/{internship_id}")
    student.fill(
        "textarea[name=cover_letter]",
        "Tenho experiência com Python e Docker em projetos acadêmicos e quero atuar com microsserviços.",
    )
    shot(student, "08-estudante-candidata-se")
    student.click("form[action$='/candidatar'] button[type=submit]")
    student.wait_for_url(f"{BASE}/candidaturas/*")
    application_id = student.url.rstrip("/").split("/")[-1]

    wait_for(company, f"{BASE}/vagas/{internship_id}/candidatos", "Ranking de candidatos")
    wait_for(company, f"{BASE}/vagas/{internship_id}/candidatos", "Ana Beatriz Souza")
    shot(company, "09-ranking-candidatos", full_page=True)
    company.goto(f"{BASE}/candidaturas")
    shot(company, "10-kanban-empresa")
    company.goto(f"{BASE}/candidaturas/{application_id}")
    company.click("form[action$='/analisar'] button")
    company.wait_for_url(f"{BASE}/candidaturas/{application_id}")
    company.click(f"a[href='/candidaturas/{application_id}/aprovar']")
    start = date.today() + timedelta(days=10)
    company.fill("input[name=start_date]", start.isoformat())
    company.fill("input[name=end_date]", (start + timedelta(days=365)).isoformat())
    company.fill("input[name=supervisor_name]", "Carla Mendes (fictícia)")
    company.fill("input[name=insurer]", "Seguradora Exemplo S.A. (fictícia)")
    company.fill("input[name=insurance_policy]", f"AP-DEMO-{stamp}")
    company.fill(
        "textarea[name=activities]", "Desenvolvimento de APIs, testes automatizados e documentação."
    )
    shot(company, "11-empresa-aprova-com-termos", full_page=True)
    company.click("form[action$='/aprovar'] button[type=submit]")
    company.wait_for_url(f"{BASE}/candidaturas/{application_id}")
    company.goto(f"{BASE}/assistente?internship_id={internship_id}")
    company.click("form[action='/assistente/executar'] button[type=submit]")
    company.wait_for_selector("#run-result .trail")
    shot(company, "12-triagem-ia", full_page=True)

    coordinator = login(coord_ctx, COORDINATOR)
    wait_for(coordinator, f"{BASE}/candidaturas/{application_id}", "Ver Termo de Compromisso")
    shot(coordinator, "13-candidatura-tce-pendente", full_page=True)
    coordinator.click("a:has-text('Ver Termo de Compromisso')")
    coordinator.wait_for_selector(".pdf-preview img")
    coordinator.wait_for_function("document.querySelector('.pdf-preview img').naturalWidth > 0")
    shot(coordinator, "14-tce-preview-aprovacao", full_page=True)
    coordinator.click("form[action$='/aprovar'] button[type=submit]")
    coordinator.wait_for_load_state("networkidle")
    coordinator.goto(f"{BASE}/")
    shot(coordinator, "15-dashboard-coordenacao", full_page=True)

    wait_for(student, f"{BASE}/candidaturas/{application_id}", "Estágio ativo")
    shot(student, "16-estagio-ativo-historico", full_page=True)
    student.goto(f"{BASE}/relatorios")
    student.select_option("select[name=application_id]", application_id)
    student.fill("input[name=title]", "Relatório de atividades — 1º mês")
    student.fill("input[name=period_start]", start.isoformat())
    student.fill("input[name=period_end]", (start + timedelta(days=30)).isoformat())
    student.set_input_files(
        "input[name=file]",
        {"name": "relatorio.pdf", "mimeType": "application/pdf", "buffer": MINIMAL_PDF},
    )
    student.click("form[action='/relatorios'] button[type=submit]")
    student.wait_for_url(f"{BASE}/relatorios")
    shot(student, "17-relatorio-enviado", full_page=True)
    student.goto(f"{BASE}/candidaturas")
    shot(student, "18-kanban-estudante")
    wait_for(student, f"{BASE}/notificacoes", "TCE aprovado")
    shot(student, "19-notificacoes-estudante", full_page=True)

    coordinator.goto(f"{BASE}/relatorios")
    shot(coordinator, "20-relatorios-prazos", full_page=True)
    coordinator.goto(f"{BASE}/assistente")
    coordinator.click("form[action='/assistente/executar'] button[type=submit]")
    coordinator.wait_for_selector("#run-result .trail")
    shot(coordinator, "21-agente-acompanhamento", full_page=True)
    coordinator.goto(f"{BASE}/status")
    shot(coordinator, "22-status-microsservicos", full_page=True)

    plain = new_context(browser, show_services=False)
    page = login(plain, COMPANY)
    shot(page, "23-dashboard-toggle-desligado")
    for context in (company_ctx, student_ctx, coord_ctx, plain):
        context.close()


def degraded(browser) -> None:
    """Screens with recommendation-service and agent-service stopped."""
    context = new_context(browser)
    page = login(context, STUDENT)
    shot(page, "24-degradacao-dashboard", full_page=True)
    page.goto(f"{BASE}/recomendacoes")
    shot(page, "25-degradacao-recomendacoes")
    page.goto(f"{BASE}/status")
    shot(page, "26-degradacao-status", full_page=True)
    context.close()


def main() -> int:
    """Entry point."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        print(f"Capturando telas de {BASE}")
        if "--degraded" in sys.argv:
            degraded(browser)
        else:
            main_flow(browser)
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
