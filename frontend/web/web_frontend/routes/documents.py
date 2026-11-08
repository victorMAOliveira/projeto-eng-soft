"""TCE (termos) and activity report pages."""

from fastapi import APIRouter, Request
from fastapi.responses import Response

from web_frontend.web import gateway, redirect, render, require_user

router = APIRouter()


async def _proxy_binary(request: Request, path: str, media_type: str) -> Response:
    """Stream a binary document from the gateway with the user's token."""
    user = require_user(request)
    upstream = await gateway(request).raw("GET", path, token=user.token)
    if upstream is None or upstream.status_code != 200:
        return Response(status_code=upstream.status_code if upstream else 503)
    headers = {"X-Served-By": upstream.headers.get("x-served-by", "")}
    if "content-disposition" in upstream.headers:
        headers["Content-Disposition"] = upstream.headers["content-disposition"]
    return Response(upstream.content, media_type=media_type, headers=headers)


@router.get("/termos")
async def agreements(request: Request, status: str | None = None) -> Response:
    """Agreements visible to the role (coordination sees the approval queue)."""
    user = require_user(request)
    params = {"status": status} if status else {}
    result = await gateway(request).get("/api/agreements", token=user.token, params=params)
    return render(request, "documents/agreements.html", result=result, status_filter=status)


@router.get("/termos/{agreement_id}")
async def agreement_detail(request: Request, agreement_id: str) -> Response:
    """TCE preview (PNG of page 1), download and coordination approval."""
    user = require_user(request)
    result = await gateway(request).get(f"/api/agreements/{agreement_id}", token=user.token)
    if result.status in (403, 404):
        return render(request, "not_found.html", status_code=404, message="TCE não encontrado.")
    return render(request, "documents/agreement.html", result=result, tce=result.data)


@router.get("/termos/{agreement_id}/pdf")
async def agreement_pdf(request: Request, agreement_id: str) -> Response:
    """PDF proxied from the document-service."""
    return await _proxy_binary(request, f"/api/agreements/{agreement_id}/pdf", "application/pdf")


@router.get("/termos/{agreement_id}/preview.png")
async def agreement_preview(request: Request, agreement_id: str) -> Response:
    """PNG preview proxied from the document-service."""
    return await _proxy_binary(request, f"/api/agreements/{agreement_id}/preview.png", "image/png")


@router.post("/termos/{agreement_id}/aprovar")
async def approve_agreement(request: Request, agreement_id: str) -> Response:
    """Coordination approves the TCE (the internship becomes active via the saga)."""
    user = require_user(request, "coordinator")
    result = await gateway(request).post(
        f"/api/agreements/{agreement_id}/approve", token=user.token
    )
    if not result.ok:
        return redirect(f"/termos/{agreement_id}", flash=result.error, kind="error")
    return redirect(
        f"/termos/{agreement_id}", flash="TCE aprovado. O estágio passará a ativo em instantes."
    )


@router.get("/relatorios")
async def reports(request: Request) -> Response:
    """Reports list; students also get the upload form for their active internships."""
    user = require_user(request)
    api = gateway(request)
    result = await api.get("/api/reports", token=user.token)
    placements = await api.get("/api/placements", token=user.token, params={"status": "active"})
    return render(request, "documents/reports.html", result=result, placements=placements)


@router.post("/relatorios")
async def upload_report(request: Request) -> Response:
    """Forward the multipart upload to the document-service through the gateway."""
    user = require_user(request, "student")
    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        return redirect("/relatorios", flash="Selecione o arquivo PDF do relatório.", kind="error")
    content = await upload.read()
    result = await gateway(request).post(
        "/api/reports",
        token=user.token,
        data={
            k: str(form.get(k, ""))
            for k in ("application_id", "title", "period_start", "period_end")
        },
        files={"file": (upload.filename or "relatorio.pdf", content, "application/pdf")},
    )
    if not result.ok:
        return redirect("/relatorios", flash=result.error, kind="error")
    return redirect("/relatorios", flash="Relatório enviado (versão 1).")


@router.post("/relatorios/{report_id}/versoes")
async def upload_version(request: Request, report_id: str) -> Response:
    """Upload a new version of an existing report."""
    user = require_user(request, "student")
    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        return redirect("/relatorios", flash="Selecione o arquivo PDF.", kind="error")
    result = await gateway(request).post(
        f"/api/reports/{report_id}/versions",
        token=user.token,
        files={
            "file": (upload.filename or "relatorio.pdf", await upload.read(), "application/pdf")
        },
    )
    if not result.ok:
        return redirect("/relatorios", flash=result.error, kind="error")
    return redirect("/relatorios", flash="Nova versão enviada.")


@router.get("/relatorios/{report_id}/versoes/{version}")
async def download_version(request: Request, report_id: str, version: int) -> Response:
    """Download one report version."""
    return await _proxy_binary(
        request, f"/api/reports/{report_id}/versions/{version}/file", "application/pdf"
    )


@router.post("/relatorios/{report_id}/revisar")
async def review_report(request: Request, report_id: str) -> Response:
    """Coordination records its review."""
    user = require_user(request, "coordinator")
    form = await request.form()
    result = await gateway(request).post(
        f"/api/reports/{report_id}/review",
        token=user.token,
        json={"comment": str(form.get("comment", ""))},
    )
    if not result.ok:
        return redirect("/relatorios", flash=result.error, kind="error")
    return redirect("/relatorios", flash="Revisão registrada.")
