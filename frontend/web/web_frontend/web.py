"""Rendering helpers shared by all pages: templates, navigation, flash, auth guard."""

from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader

import eh_ui
from web_frontend.gateway import GatewayClient
from web_frontend.session import (
    FLASH_COOKIE,
    SHOW_SERVICES_COOKIE,
    TOKEN_COOKIE,
    SessionUser,
    current_user,
)

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.loader = ChoiceLoader(
    [FileSystemLoader(TEMPLATES_DIR), FileSystemLoader(eh_ui.templates_dir())]
)
eh_ui.register_filters(templates.env)

COURSES = [
    "Ciência da Computação",
    "Engenharia de Computação",
    "Sistemas de Informação",
    "Administração",
    "Engenharia Civil",
    "Design",
]

# (label, href, icon) — icons are inline SVG names from templates/_icons.html
NAV: dict[str, list[tuple[str, str, str]]] = {
    "student": [
        ("Painel", "/", "home"),
        ("Vagas", "/vagas", "briefcase"),
        ("Recomendações", "/recomendacoes", "star"),
        ("Candidaturas", "/candidaturas", "kanban"),
        ("Termos (TCE)", "/termos", "file"),
        ("Relatórios", "/relatorios", "report"),
        ("Assistente IA", "/assistente", "bot"),
        ("Notificações", "/notificacoes", "bell"),
        ("Meu perfil", "/perfil", "user"),
    ],
    "company": [
        ("Painel", "/", "home"),
        ("Minhas vagas", "/vagas?mine=1", "briefcase"),
        ("Publicar vaga", "/vagas/nova", "plus"),
        ("Candidaturas", "/candidaturas", "kanban"),
        ("Termos (TCE)", "/termos", "file"),
        ("Triagem IA", "/assistente", "bot"),
        ("Notificações", "/notificacoes", "bell"),
        ("Perfil da empresa", "/perfil", "user"),
    ],
    "coordinator": [
        ("Painel", "/", "home"),
        ("Vagas", "/vagas", "briefcase"),
        ("Candidaturas", "/candidaturas", "kanban"),
        ("Termos (TCE)", "/termos", "file"),
        ("Relatórios", "/relatorios", "report"),
        ("Acompanhamento IA", "/assistente", "bot"),
        ("Notificações", "/notificacoes", "bell"),
    ],
}


class LoginRequired(Exception):
    """Raised by pages that need an authenticated user (handled with a redirect)."""

    def __init__(self, next_url: str = "/") -> None:
        super().__init__(next_url)
        self.next_url = next_url


def gateway(request: Request) -> GatewayClient:
    """The gateway client created at startup."""
    return request.app.state.gateway


def require_user(request: Request, *roles: str) -> SessionUser:
    """Return the logged user or raise :class:`LoginRequired` (optionally checking role)."""
    user = current_user(request)
    if user is None or (roles and user.role not in roles):
        target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        raise LoginRequired(target)
    return user


def is_htmx(request: Request) -> bool:
    """``True`` for requests issued by HTMX (partial rendering)."""
    return request.headers.get("hx-request") == "true"


def active_nav_href(request: Request, items: list[tuple[str, str, str]]) -> str | None:
    """Pick the menu entry matching the URL (exact query first, then bare path)."""
    path, query = request.url.path, request.url.query
    exact = [href for _, href, _ in items if href == (f"{path}?{query}" if query else path)]
    if exact:
        return exact[0]
    bare = [href for _, href, _ in items if href == path]
    return bare[0] if bare else None


def render(
    request: Request, template: str, *, status_code: int = 200, **context: Any
) -> HTMLResponse:
    """Render ``template`` with the common context (user, nav, toggle, flash)."""
    user = current_user(request)
    flash = request.cookies.get(FLASH_COOKIE)
    nav = NAV.get(user.role, []) if user else []
    response = templates.TemplateResponse(
        request,
        template,
        {
            "user": user,
            "nav": nav,
            "active_href": active_nav_href(request, nav),
            "show_services": request.cookies.get(SHOW_SERVICES_COOKIE) == "1",
            "flash": flash.split("|", 1) if flash else None,
            "current_path": request.url.path,
            "courses": COURSES,
            **context,
        },
        status_code=status_code,
    )
    if flash:
        response.delete_cookie(FLASH_COOKIE)
    return response


def redirect(url: str, *, flash: str | None = None, kind: str = "success") -> Response:
    """303 redirect (works for HTMX too) with an optional one-shot flash message."""
    response = RedirectResponse(url, status_code=303)
    if flash:
        response.set_cookie(FLASH_COOKIE, f"{kind}|{flash}", max_age=30, httponly=True)
    return response


def login_redirect(request: Request, exc: LoginRequired) -> Response:
    """Send anonymous users to the login page, keeping the destination."""
    url = f"/login?next={quote(exc.next_url)}"
    if is_htmx(request):
        return Response(status_code=204, headers={"HX-Redirect": url})
    response = RedirectResponse(url, status_code=303)
    response.delete_cookie(TOKEN_COOKIE)
    return response
