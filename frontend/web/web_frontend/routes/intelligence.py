"""Recommendation and AI-agent pages (recommendation-service and agent-service)."""

from fastapi import APIRouter, Request
from fastapi.responses import Response

from web_frontend.web import gateway, is_htmx, render, require_user

router = APIRouter()

AGENT_ENDPOINTS = {
    "student": ("/api/agents/application-assistant/run", "application_assistant"),
    "company": ("/api/agents/screening/run", "screening"),
    "coordinator": ("/api/agents/follow-up/run", "follow_up"),
}


@router.get("/recomendacoes")
async def recommendations(request: Request) -> Response:
    """Explainable recommendations for the logged-in student."""
    user = require_user(request, "student")
    result = await gateway(request).get(
        f"/api/recommendations/students/{user.id}/internships",
        token=user.token,
        params={"k": 10, "include_filtered": "true"},
    )
    return render(request, "intelligence/recommendations.html", result=result)


async def _assistant_context(request: Request, user) -> dict:
    api = gateway(request)
    status = await api.get("/api/agents/status", token=user.token)
    _, agent = AGENT_ENDPOINTS[user.role]
    runs = await api.get("/api/agents/runs", token=user.token, params={"agent": agent, "limit": 8})
    options = None
    if user.role == "student":
        options = await api.get(
            f"/api/recommendations/students/{user.id}/internships",
            token=user.token,
            params={"k": 10},
        )
    elif user.role == "company":
        options = await api.get("/api/internships/mine", token=user.token)
    return {"status": status, "runs": runs, "options": options}


@router.get("/assistente")
async def assistant(
    request: Request, run_id: int | None = None, internship_id: int | None = None
) -> Response:
    """AI assistant page adapted to the role, with the last runs and their trail."""
    user = require_user(request, "student", "company", "coordinator")
    context = await _assistant_context(request, user)
    run = None
    if run_id is not None:
        run = await gateway(request).get(f"/api/agents/runs/{run_id}", token=user.token)
    return render(
        request, "intelligence/assistant.html", run=run, selected=internship_id, **context
    )


@router.post("/assistente/executar")
async def run_agent(request: Request) -> Response:
    """Run the role's agent; HTMX receives only the result partial."""
    user = require_user(request, "student", "company", "coordinator")
    endpoint, _ = AGENT_ENDPOINTS[user.role]
    form = await request.form()
    payload: dict = {}
    if form.get("internship_id"):
        payload["internship_id"] = int(str(form["internship_id"]))
    if form.get("question"):
        payload["question"] = str(form["question"])
    run = await gateway(request).post(endpoint, token=user.token, json=payload)
    if is_htmx(request):
        return render(request, "intelligence/_run.html", run=run)
    context = await _assistant_context(request, user)
    return render(
        request,
        "intelligence/assistant.html",
        run=run,
        selected=payload.get("internship_id"),
        **context,
    )
