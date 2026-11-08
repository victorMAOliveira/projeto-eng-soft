"""Application pages: apply, kanban board, detail, transitions and approval form."""

from fastapi import APIRouter, Request
from fastapi.responses import Response

from web_frontend.web import gateway, redirect, render, require_user

router = APIRouter()

COLUMNS = [
    ("submitted", "Enviadas"),
    ("under_review", "Em análise"),
    ("approved", "Aprovadas"),
    ("agreement_pending", "TCE pendente"),
    ("active", "Estágio ativo"),
    ("completed", "Concluídos"),
    ("closed", "Encerradas"),
]

# action slug -> (API action, roles allowed, success message)
ACTIONS = {
    "analisar": ("review", ("company",), "Candidatura em análise."),
    "rejeitar": ("reject", ("company",), "Candidatura rejeitada."),
    "retirar": ("withdraw", ("student",), "Candidatura retirada."),
    "concluir": ("complete", ("company", "coordinator"), "Estágio concluído."),
    "rescindir": ("terminate", ("company", "coordinator"), "Estágio rescindido."),
}


@router.post("/vagas/{internship_id}/candidatar")
async def apply(request: Request, internship_id: int) -> Response:
    """Student applies with an optional cover letter."""
    user = require_user(request, "student")
    form = await request.form()
    result = await gateway(request).post(
        "/api/applications",
        token=user.token,
        json={"internship_id": internship_id, "cover_letter": str(form.get("cover_letter", ""))},
    )
    if not result.ok:
        return redirect(f"/vagas/{internship_id}", flash=result.error, kind="error")
    return redirect(f"/candidaturas/{result.data['id']}", flash="Candidatura enviada!")


@router.get("/candidaturas")
async def board(request: Request) -> Response:
    """Kanban of applications by status (scope depends on the role)."""
    user = require_user(request)
    result = await gateway(request).get("/api/applications/board", token=user.token)
    return render(request, "applications/board.html", result=result, columns=COLUMNS)


@router.get("/candidaturas/{application_id}")
async def detail(request: Request, application_id: int) -> Response:
    """Application detail with placement terms and the audit trail."""
    user = require_user(request)
    result = await gateway(request).get(f"/api/applications/{application_id}", token=user.token)
    if result.status in (403, 404):
        return render(
            request, "not_found.html", status_code=404, message="Candidatura não encontrada."
        )
    return render(request, "applications/detail.html", result=result, app=result.data)


@router.get("/candidaturas/{application_id}/aprovar")
async def approve_form(request: Request, application_id: int) -> Response:
    """Company informs the internship terms (they become the TCE)."""
    user = require_user(request, "company")
    result = await gateway(request).get(f"/api/applications/{application_id}", token=user.token)
    return render(request, "applications/approve.html", result=result, app=result.data, form={})


@router.post("/candidaturas/{application_id}/aprovar")
async def approve(request: Request, application_id: int) -> Response:
    """Send the approval; legal rules are validated by the application-service."""
    user = require_user(request, "company")
    raw = await request.form()
    form = {k: str(v).strip() for k, v in raw.items()}
    payload = {
        "start_date": form.get("start_date"),
        "end_date": form.get("end_date"),
        "supervisor_name": form.get("supervisor_name", ""),
        "insurer": form.get("insurer") or None,
        "insurance_policy": form.get("insurance_policy") or None,
        "activities": form.get("activities", ""),
        "hours_per_day": int(form["hours_per_day"]) if form.get("hours_per_day") else None,
        "hours_per_week": int(form["hours_per_week"]) if form.get("hours_per_week") else None,
    }
    api = gateway(request)
    result = await api.post(
        f"/api/applications/{application_id}/approve", token=user.token, json=payload
    )
    if not result.ok:
        current = await api.get(f"/api/applications/{application_id}", token=user.token)
        return render(
            request,
            "applications/approve.html",
            result=current,
            app=current.data,
            form=form,
            error=result.error,
        )
    return redirect(
        f"/candidaturas/{application_id}",
        flash="Candidato aprovado! O TCE será gerado automaticamente pelo document-service.",
    )


@router.get("/vagas/{internship_id}/candidatos")
async def candidates(request: Request, internship_id: int) -> Response:
    """Applicants of one offer (company owner or coordination)."""
    user = require_user(request, "company", "coordinator")
    api = gateway(request)
    vaga = await api.get(f"/api/internships/{internship_id}", token=user.token)
    applications = await api.get(
        "/api/applications", token=user.token, params={"internship_id": internship_id}
    )
    return render(
        request,
        "applications/candidates.html",
        vaga=vaga,
        applications=applications,
        internship_id=internship_id,
    )


# Declared last so that /candidaturas/{id}/aprovar is matched by its own route first.
@router.post("/candidaturas/{application_id}/{action}")
async def act(request: Request, application_id: int, action: str) -> Response:
    """Run a state machine transition (the service answers 409 if invalid)."""
    if action not in ACTIONS:
        return render(request, "not_found.html", status_code=404, message="Ação desconhecida.")
    api_action, roles, message = ACTIONS[action]
    user = require_user(request, *roles)
    form = await request.form()
    result = await gateway(request).post(
        f"/api/applications/{application_id}/{api_action}",
        token=user.token,
        json={"reason": str(form.get("reason", "")) or None},
    )
    back = str(form.get("back") or f"/candidaturas/{application_id}")
    if not result.ok:
        return redirect(back, flash=result.error, kind="error")
    return redirect(back, flash=message)
