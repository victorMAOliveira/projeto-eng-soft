"""Login, registration and logout pages."""

from fastapi import APIRouter, Form, Request
from fastapi.responses import Response

from web_frontend.session import TOKEN_COOKIE, current_user
from web_frontend.web import gateway, redirect, render

router = APIRouter()


def _safe_next(next_url: str | None) -> str:
    """Only allow local redirects after login (no open redirect)."""
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return "/"


@router.get("/login")
async def login_page(request: Request, next: str | None = None) -> Response:
    """Login form."""
    if current_user(request):
        return redirect(_safe_next(next))
    return render(request, "auth/login.html", next=_safe_next(next))


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
) -> Response:
    """Authenticate through the gateway and store the JWT in an HttpOnly cookie."""
    result = await gateway(request).post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    if not result.ok:
        message = (
            "Serviço de usuários indisponível. Tente novamente em instantes."
            if result.unavailable
            else "E-mail ou senha inválidos."
        )
        return render(
            request,
            "auth/login.html",
            error=message,
            email=email,
            next=_safe_next(next),
            status_code=401 if result.status == 401 else 200,
        )
    response = redirect(_safe_next(next))
    response.set_cookie(
        TOKEN_COOKIE,
        result.data["access_token"],
        max_age=int(result.data["expires_in"]),
        httponly=True,
        samesite="lax",
        secure=request.app.state.settings.cookie_secure,
    )
    return response


@router.get("/cadastro")
async def register_page(request: Request) -> Response:
    """Registration form (students and companies)."""
    return render(request, "auth/register.html", form={})


@router.post("/cadastro")
async def register(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("student"),
) -> Response:
    """Create the account through the gateway, then send the user to login."""
    form = {"full_name": full_name, "email": email, "role": role}
    if role not in ("student", "company"):
        return render(request, "auth/register.html", form=form, error="Papel inválido.")
    result = await gateway(request).post(
        "/api/auth/register",
        json={"full_name": full_name, "email": email, "password": password, "role": role},
    )
    if not result.ok:
        return render(request, "auth/register.html", form=form, error=result.error)
    return redirect("/login", flash="Conta criada! Faça login para continuar.")


@router.post("/logout")
async def logout(request: Request) -> Response:
    """Forget the session cookie."""
    response = redirect("/login", flash="Sessão encerrada.", kind="info")
    response.delete_cookie(TOKEN_COOKIE)
    return response
