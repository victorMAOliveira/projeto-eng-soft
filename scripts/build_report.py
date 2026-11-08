"""Report build helper (``make report``).

* ``prepare`` (tools image) — refresh the generated blocks of
  ``docs/relatorio/relatorio.md`` between ``<!-- BEGIN:x -->`` / ``<!-- END:x -->``
  markers: test results, offline evaluation, reuse metrics/matrix, gateway
  routes and policies, the endpoint table of every service (introspected
  from the FastAPI routers, including the role each route requires),
  component versions and ``docker compose ps``.
* ``pdf`` (Playwright image) — print ``build/relatorio.html`` (made by pandoc)
  to ``build/relatorio.pdf`` with the table of contents after the cover and
  page numbers in the footer.
"""

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs" / "relatorio" / "relatorio.md"
GENERATED = ROOT / "docs" / "relatorio" / "generated"
BUILD = ROOT / "docs" / "relatorio" / "build"
SERVICE_MODULES = {
    "user-service": "user_service.api",
    "internship-service": "internship_service.api",
    "application-service": "application_service.api",
    "document-service": "document_service.api",
    "notification-service": "notification_service.api",
    "recommendation-service": "recommendation_service.api",
    "agent-service": "agent_service.api",
}
ROLE_PT = {"student": "estudante", "company": "empresa", "coordinator": "coordenação", "service": "serviço interno"}


def replace_block(text: str, name: str, content: str) -> str:
    """Replace the content between the markers of block ``name``."""
    pattern = re.compile(rf"(<!-- BEGIN:{re.escape(name)} -->\n).*?(\n<!-- END:{re.escape(name)} -->)", re.DOTALL)
    if not pattern.search(text):
        print(f"  (marcador {name} ausente)")
        return text
    return pattern.sub(lambda m: m.group(1) + content.strip("\n") + m.group(2), text)


def roles_of(route) -> str:
    """Describe who may call ``route`` by inspecting its auth dependencies."""
    from eh_auth import Role, get_current_principal, get_optional_principal

    def walk(dependant):
        for dep in dependant.dependencies:
            yield dep
            yield from walk(dep)

    for dep in walk(route.dependant):
        call = dep.call
        for cell in getattr(call, "__closure__", None) or ():
            contents = cell.cell_contents
            if isinstance(contents, frozenset) and contents and all(isinstance(r, Role) for r in contents):
                order = ["student", "company", "coordinator", "service"]
                return ", ".join(ROLE_PT[r] for r in order if Role(r) in contents)
        if call is get_current_principal:
            return "autenticado (qualquer papel)"
        if call is get_optional_principal:
            return "público (token opcional)"
    return "público"


def endpoints_table(service: str) -> str:
    """Markdown table of a service's routes, introspected from its router."""
    sys.path.insert(0, str(ROOT / "services" / service))
    module = __import__(SERVICE_MODULES[service], fromlist=["router"])
    lines = ["| Método | Rota | Papel exigido | Descrição |", "|---|---|---|---|"]
    for route in module.router.routes:
        methods = "/".join(sorted(route.methods - {"HEAD"}))
        summary = (route.summary or route.name).replace("|", "/")
        lines.append(f"| {methods} | `{route.path}` | {roles_of(route)} | {summary} |")
    lines.append("| GET | `/health`, `/ready`, `/version` | público | Health Check API (`eh_observability`) |")
    return "\n".join(lines)


def gateway_tables() -> tuple[str, str]:
    """Routing table and role policies of the API Gateway."""
    sys.path.insert(0, str(ROOT / "services" / "api-gateway"))
    from api_gateway.routes import POLICIES, ROUTES

    routes = ["| Prefixo público | Serviço de destino | Rota no serviço | Autenticação |", "|---|---|---|---|"]
    for r in ROUTES:
        routes.append(f"| `{r.prefix}/*` | {r.service} | `{r.prefix.removeprefix('/api')}/*` | {'pública' if r.public else 'JWT'} |")
    routes += [
        "| `GET /services` | (gateway) | — | pública — agrega `/ready` e `/version` |",
        "| `GET /routes` | (gateway) | — | pública — esta tabela |",
    ]
    policies = ["| Método | Caminho (regex) | Papéis permitidos |", "|---|---|---|"]
    order = ["student", "company", "coordinator"]
    for p in POLICIES:
        roles = ", ".join(ROLE_PT[r] for r in order if r in {x.value for x in p.roles})
        policies.append(f"| {p.method} | `{p.pattern}` | {roles} |")
    return "\n".join(routes), "\n".join(policies)


def tests_table() -> str:
    """Table from ``generated/test-summary.json`` (written by ``make test``)."""
    path = GENERATED / "test-summary.json"
    if not path.exists():
        return "_Execute `make test` para gerar esta tabela._"
    rows = json.loads(path.read_text(encoding="utf-8"))
    kinds = {"lint": "lint", "component": "componente", "service": "serviço", "frontend": "frontend"}
    lines = ["| Tipo | Pacote | Testes | Cobertura | Resultado |", "|---|---|---|---|---|"]
    total = 0
    for r in rows:
        total += r.get("passed", 0) or 0
        coverage = f"{r['coverage']}%" if r.get("coverage") is not None else "—"
        passed = r.get("passed", "—") if r["kind"] != "lint" else "—"
        lines.append(f"| {kinds[r['kind']]} | {r['name']} | {passed} | {coverage} | {'aprovado' if r['ok'] else 'falhou'} |")
    lines.append(f"| | **Total** | **{total}** | | |")
    return "\n".join(lines)


def components_table() -> str:
    """Name, version and description of each component (from pyproject.toml)."""
    lines = ["| Componente | Versão | Descrição |", "|---|---|---|"]
    for path in sorted((ROOT / "components").glob("*/pyproject.toml")):
        project = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
        description = project["description"].removeprefix("EstágioHub component: ")
        lines.append(f"| `{path.parent.name}` | {project['version']} | {description} |")
    return "\n".join(lines)


def service_versions_table() -> str:
    """Microservice → version table (from each pyproject.toml)."""
    lines = []
    for path in sorted([*(ROOT / "services").glob("*/pyproject.toml"), ROOT / "frontend" / "web" / "pyproject.toml"]):
        project = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
        lines.append(f"{project['name']}={project['version']}")
    return ", ".join(lines)


def read_generated(name: str, fallback: str) -> str:
    """Content of a generated file or a hint about how to produce it."""
    path = GENERATED / name
    return path.read_text(encoding="utf-8") if path.exists() else fallback


def prepare() -> int:
    """Inject every generated block into relatorio.md."""
    text = REPORT.read_text(encoding="utf-8")
    text = replace_block(text, "tests", tests_table())
    text = replace_block(text, "eval", read_generated("eval_metrics.md", "_Execute `make eval`._"))
    text = replace_block(text, "reuse-metrics", read_generated("reuse_metrics.md", "_Execute `make eval`._"))
    text = replace_block(text, "reuse-matrix", read_generated("reuse_matrix.md", "_Execute `make eval`._"))
    text = replace_block(text, "components", components_table())
    routes, policies = gateway_tables()
    text = replace_block(text, "gateway-routes", routes)
    text = replace_block(text, "gateway-policies", policies)
    for service in SERVICE_MODULES:
        text = replace_block(text, f"endpoints:{service}", endpoints_table(service))
    compose_ps = read_generated("compose-ps.txt", "Execute `make screenshots` (gera a saída de docker compose ps).")
    text = replace_block(text, "compose-ps", "```text\n" + compose_ps.strip() + "\n```")
    REPORT.write_bytes(text.encode("utf-8"))
    BUILD.mkdir(parents=True, exist_ok=True)
    print(f"relatorio.md atualizado ({service_versions_table()})")
    return 0


def pdf() -> int:
    """Print the pandoc HTML to PDF with Chromium (Playwright)."""
    from playwright.sync_api import sync_playwright

    html = BUILD / "relatorio.html"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(html.resolve().as_uri())
        page.evaluate(
            """() => {
                const toc = document.getElementById('TOC');
                const cover = document.querySelector('.capa');
                if (toc && cover) {
                    const title = document.createElement('h1');
                    title.textContent = 'Sumário';
                    title.className = 'sumario-titulo';
                    toc.prepend(title);
                    cover.after(toc);
                }
            }"""
        )
        page.wait_for_load_state("networkidle")
        page.pdf(
            path=str(BUILD / "relatorio.pdf"),
            format="A4",
            print_background=True,
            margin={"top": "2.2cm", "bottom": "2cm", "left": "2.5cm", "right": "2cm"},
            display_header_footer=True,
            header_template="<span></span>",
            footer_template=(
                '<div style="font-size:8px;width:100%;text-align:center;color:#64748b;">'
                'EstágioHub — Relatório Final · <span class="pageNumber"></span>/<span class="totalPages"></span></div>'
            ),
        )
        browser.close()
    print(BUILD / "relatorio.pdf")
    return 0


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "prepare"
    sys.exit({"prepare": prepare, "pdf": pdf}[command]())
