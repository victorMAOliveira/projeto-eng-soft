"""Profile pages (student academic profile, company profile)."""

from fastapi import APIRouter, Request
from fastapi.responses import Response

from web_frontend.web import gateway, redirect, render, require_user

router = APIRouter()


@router.get("/perfil")
async def profile_page(request: Request) -> Response:
    """Show the profile form of the logged-in student or company."""
    user = require_user(request, "student", "company")
    path = "/api/profiles/students/me" if user.role == "student" else "/api/profiles/companies/me"
    result = await gateway(request).get(path, token=user.token)
    template = "profile/student.html" if user.role == "student" else "profile/company.html"
    return render(request, template, result=result, form=result.data or {})


@router.post("/perfil")
async def save_profile(request: Request) -> Response:
    """Save the profile through the gateway."""
    user = require_user(request, "student", "company")
    raw = await request.form()
    form = {key: str(value).strip() for key, value in raw.items()}
    if user.role == "student":
        payload = {
            "course": form.get("course", ""),
            "semester": int(form.get("semester") or 0),
            "enrollment": form.get("enrollment") or None,
            "skills": [s.strip() for s in form.get("skills", "").split(",") if s.strip()],
            "resume_summary": form.get("resume_summary", ""),
            "weekly_availability_hours": int(form.get("weekly_availability_hours") or 0),
            "preferred_modality": form.get("preferred_modality") or None,
            "city": form.get("city") or None,
            "is_pcd": form.get("is_pcd") == "on",
        }
        path, template = "/api/profiles/students/me", "profile/student.html"
    else:
        payload = {
            key: form.get(key) or None
            for key in ("trade_name", "cnpj", "sector", "city", "website")
        }
        payload["description"] = form.get("description", "")
        path, template = "/api/profiles/companies/me", "profile/company.html"
    result = await gateway(request).put(path, token=user.token, json=payload)
    if not result.ok:
        form_view = {**payload, "skills": payload.get("skills", [])}
        return render(request, template, result=result, form=form_view, error=result.error)
    return redirect("/perfil", flash="Perfil salvo.")
