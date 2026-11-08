"""Internship pages: list/search, detail, creation and closing."""

from fastapi import APIRouter, Request
from fastapi.responses import Response

from web_frontend.web import gateway, is_htmx, redirect, render, require_user

router = APIRouter()

FORM_FIELDS = (
    "title",
    "description",
    "requirements",
    "course",
    "min_semester",
    "hours_per_day",
    "hours_per_week",
    "modality",
    "city",
    "stipend",
    "positions",
)


@router.get("/vagas")
async def list_internships(
    request: Request,
    q: str | None = None,
    course: str | None = None,
    modality: str | None = None,
    city: str | None = None,
    mine: int = 0,
    page: int = 1,
) -> Response:
    """Search offers; HTMX requests receive only the results partial."""
    user = require_user(request)
    api = gateway(request)
    if mine and user.role == "company":
        result = await api.get("/api/internships/mine", token=user.token)
        data = {"items": result.data or [], "total": len(result.data or []), "page": 1, "size": 200}
    else:
        params = {
            k: v
            for k, v in {"q": q, "course": course, "modality": modality, "city": city}.items()
            if v
        }
        params.update(page=page, size=12)
        result = await api.get("/api/internships", token=user.token, params=params)
        data = result.data if result.ok else {"items": [], "total": 0, "page": 1, "size": 12}
    context = {
        "result": result,
        "page_data": data,
        "filters": {
            "q": q or "",
            "course": course or "",
            "modality": modality or "",
            "city": city or "",
        },
        "mine": bool(mine),
    }
    template = "internships/_results.html" if is_htmx(request) else "internships/list.html"
    return render(request, template, **context)


@router.get("/vagas/nova")
async def new_internship_page(request: Request) -> Response:
    """Offer creation form (companies)."""
    require_user(request, "company")
    return render(request, "internships/form.html", form={"hours_per_day": 6, "hours_per_week": 30})


@router.post("/vagas")
async def create_internship(request: Request) -> Response:
    """Publish the offer through the gateway (validation happens in the service)."""
    user = require_user(request, "company")
    raw = await request.form()
    form = {field: str(raw.get(field, "")).strip() for field in FORM_FIELDS}
    payload = {
        **form,
        "requirements": [r.strip() for r in form["requirements"].split(",") if r.strip()],
        "min_semester": int(form["min_semester"] or 0),
        "hours_per_day": int(form["hours_per_day"] or 0),
        "hours_per_week": int(form["hours_per_week"] or 0),
        "stipend": float((form["stipend"] or "0").replace(",", ".")),
        "positions": int(form["positions"] or 1),
    }
    result = await gateway(request).post("/api/internships", token=user.token, json=payload)
    if not result.ok:
        return render(request, "internships/form.html", form=form, error=result.error)
    return redirect(f"/vagas/{result.data['id']}", flash="Vaga publicada com sucesso.")


@router.get("/vagas/{internship_id}")
async def internship_detail(request: Request, internship_id: int) -> Response:
    """Offer details with the actions allowed to the current role."""
    user = require_user(request)
    result = await gateway(request).get(f"/api/internships/{internship_id}", token=user.token)
    if result.status == 404:
        return render(request, "not_found.html", status_code=404, message="Vaga não encontrada.")
    return render(request, "internships/detail.html", result=result, vaga=result.data)


@router.post("/vagas/{internship_id}/encerrar")
async def close_internship(request: Request, internship_id: int) -> Response:
    """Close an offer (owner company or coordination)."""
    user = require_user(request, "company", "coordinator")
    result = await gateway(request).post(
        f"/api/internships/{internship_id}/close", token=user.token
    )
    if not result.ok:
        return redirect(f"/vagas/{internship_id}", flash=result.error, kind="error")
    return redirect(f"/vagas/{internship_id}", flash="Vaga encerrada.")
