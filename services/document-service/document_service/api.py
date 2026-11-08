"""HTTP API of the document-service (TCE and activity reports)."""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import Response
from pydantic import BaseModel, Field

from document_service.pdf import render_preview_png
from document_service.storage import FileStorage, Store
from eh_auth import Principal, Role, get_current_principal, require_role
from eh_events import AgreementApproved, EventType, Publisher, ReportSubmitted
from eh_http import CircuitOpenError, ResilientClient, UpstreamUnavailableError

router = APIRouter()
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


class ReviewIn(BaseModel):
    """Coordination feedback on a report."""

    comment: str = Field(default="", max_length=2000)


def store_dep(request: Request) -> Store:
    """Document store configured at startup."""
    return request.app.state.store


def files_dep(request: Request) -> FileStorage:
    """File storage (volume) configured at startup."""
    return request.app.state.files


def publisher_dep(request: Request) -> Publisher:
    """Event publisher configured at startup."""
    return request.app.state.publisher


def scope(principal: Principal) -> dict[str, Any]:
    """Equality filter limiting documents to what ``principal`` may see."""
    if principal.role == Role.STUDENT:
        return {"student_id": principal.id}
    if principal.role == Role.COMPANY:
        return {"company_id": principal.id}
    return {}


def visible(doc: dict[str, Any] | None, principal: Principal, kind: str) -> dict[str, Any]:
    """Return ``doc`` if the caller may see it (404/403 otherwise)."""
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{kind} não encontrado")
    if any(doc.get(k) != v for k, v in scope(principal).items()):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso negado a este documento")
    return doc


def public(doc: dict[str, Any]) -> dict[str, Any]:
    """Serialise a stored document (``_id`` → ``id``, no file paths)."""
    out = {k: v for k, v in doc.items() if k not in ("_id", "file_path")}
    out["id"] = doc["_id"]
    if "versions" in out:
        out["versions"] = [{k: v for k, v in ver.items() if k != "path"} for ver in out["versions"]]
    return out


# ------------------------------------------------------------------ agreements
@router.get("/agreements", tags=["agreements"], summary="Listar TCEs visíveis ao papel")
async def list_agreements(
    status_filter: str | None = Query(None, alias="status"),
    application_id: int | None = None,
    principal: Principal = Depends(get_current_principal),
    store: Store = Depends(store_dep),
) -> list[dict[str, Any]]:
    """Agreements filtered by status and/or application."""
    filters = scope(principal)
    if status_filter:
        filters["status"] = status_filter
    if application_id is not None:
        filters["application_id"] = application_id
    return [public(d) for d in await store.agreements.find(filters)]


@router.get("/agreements/{agreement_id}", tags=["agreements"], summary="Metadados do TCE")
async def get_agreement(
    agreement_id: str,
    principal: Principal = Depends(get_current_principal),
    store: Store = Depends(store_dep),
) -> dict[str, Any]:
    """Agreement metadata."""
    return public(visible(await store.agreements.get(agreement_id), principal, "TCE"))


@router.get("/agreements/{agreement_id}/pdf", tags=["agreements"], summary="PDF do TCE")
async def agreement_pdf(
    agreement_id: str,
    principal: Principal = Depends(get_current_principal),
    store: Store = Depends(store_dep),
    files: FileStorage = Depends(files_dep),
) -> Response:
    """Download the generated PDF."""
    doc = visible(await store.agreements.get(agreement_id), principal, "TCE")
    return Response(
        files.read(doc["file_path"]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{agreement_id}.pdf"'},
    )


@router.get(
    "/agreements/{agreement_id}/preview.png",
    tags=["agreements"],
    summary="Pré-visualização (PNG da 1ª página)",
)
async def agreement_preview(
    agreement_id: str,
    principal: Principal = Depends(get_current_principal),
    store: Store = Depends(store_dep),
    files: FileStorage = Depends(files_dep),
) -> Response:
    """First page rendered as PNG (pypdfium2) for the preview screen."""
    doc = visible(await store.agreements.get(agreement_id), principal, "TCE")
    return Response(render_preview_png(files.read(doc["file_path"])), media_type="image/png")


@router.post(
    "/agreements/{agreement_id}/approve",
    tags=["agreements"],
    summary="Aprovar TCE (coordenação; publica agreement.approved)",
)
async def approve_agreement(
    agreement_id: str,
    principal: Principal = Depends(require_role(Role.COORDINATOR)),
    store: Store = Depends(store_dep),
    publisher: Publisher = Depends(publisher_dep),
) -> dict[str, Any]:
    """Coordination approval; the application-service then activates the internship."""
    doc = await store.agreements.get(agreement_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "TCE não encontrado")
    if doc["status"] != "pending_approval":
        raise HTTPException(status.HTTP_409_CONFLICT, "Este TCE já foi aprovado")
    now = datetime.now(UTC)
    await store.agreements.update(
        agreement_id, {"status": "approved", "approved_at": now, "approved_by": principal.id}
    )
    await publisher.publish(
        EventType.AGREEMENT_APPROVED,
        AgreementApproved(
            agreement_id=agreement_id,
            application_id=doc["application_id"],
            student_id=doc["student_id"],
            company_id=doc["company_id"],
            approved_by=principal.id,
            approved_at=now,
            student_name=doc.get("student_name", ""),
            internship_title=doc.get("internship_title", ""),
        ),
    )
    return public(await store.agreements.get(agreement_id))


# --------------------------------------------------------------------- reports
async def read_pdf_upload(file: UploadFile) -> bytes:
    """Accept only PDF files up to 5 MB."""
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Arquivo maior que 5 MB")
    if not content.startswith(b"%PDF"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Envie o relatório em PDF")
    return content


async def active_application(request: Request, application_id: int) -> dict[str, Any]:
    """Ask application-service (REST, caller's token) for the application."""
    client: ResilientClient = request.app.state.applications
    try:
        response = await client.get(
            f"/applications/{application_id}",
            headers={"Authorization": request.headers.get("authorization", "")},
        )
    except (CircuitOpenError, UpstreamUnavailableError) as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "application-service indisponível"
        ) from exc
    if response.status_code in (403, 404):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Estágio não encontrado")
    application = response.json()
    if application["status"] not in ("active", "completed"):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Relatórios só podem ser enviados para estágios ativos"
        )
    return application


def _version(number: int, filename: str, path: str, size: int, now: datetime) -> dict[str, Any]:
    return {
        "version": number,
        "filename": filename,
        "path": path,
        "size_bytes": size,
        "uploaded_at": now,
    }


@router.post(
    "/reports",
    status_code=status.HTTP_201_CREATED,
    tags=["reports"],
    summary="Enviar relatório de atividades (estudante; publica report.submitted)",
)
async def submit_report(
    request: Request,
    application_id: int = Form(...),
    title: str = Form(..., min_length=3, max_length=150),
    period_start: date = Form(...),
    period_end: date = Form(...),
    file: UploadFile = File(...),
    principal: Principal = Depends(require_role(Role.STUDENT)),
    store: Store = Depends(store_dep),
    files: FileStorage = Depends(files_dep),
    publisher: Publisher = Depends(publisher_dep),
) -> dict[str, Any]:
    """Store version 1 of a report for an active internship of the caller."""
    if period_end < period_start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Período inválido")
    content = await read_pdf_upload(file)
    application = await active_application(request, application_id)
    report_id = f"rel-{uuid.uuid4().hex[:12]}"
    now = datetime.now(UTC)
    path = files.save(f"reports/{report_id}/v1.pdf", content)
    doc = {
        "_id": report_id,
        "application_id": application_id,
        "student_id": principal.id,
        "company_id": application["company_id"],
        "student_name": application["student_name"],
        "internship_title": application["internship_title"],
        "title": title,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "status": "submitted",
        "review_comment": None,
        "reviewed_by": None,
        "created_at": now,
        "versions": [_version(1, file.filename or "relatorio.pdf", path, len(content), now)],
    }
    await store.reports.insert(doc)
    await publisher.publish(EventType.REPORT_SUBMITTED, _report_event(doc, 1, now))
    return public(doc)


def _report_event(doc: dict[str, Any], version: int, now: datetime) -> ReportSubmitted:
    return ReportSubmitted(
        report_id=doc["_id"],
        application_id=doc["application_id"],
        student_id=doc["student_id"],
        company_id=doc["company_id"],
        version=version,
        period_start=doc["period_start"],
        period_end=doc["period_end"],
        submitted_at=now,
        student_name=doc.get("student_name", ""),
        title=doc.get("title", ""),
    )


@router.post(
    "/reports/{report_id}/versions",
    status_code=status.HTTP_201_CREATED,
    tags=["reports"],
    summary="Enviar nova versão do relatório (versões anteriores são preservadas)",
)
async def add_version(
    report_id: str,
    file: UploadFile = File(...),
    principal: Principal = Depends(require_role(Role.STUDENT)),
    store: Store = Depends(store_dep),
    files: FileStorage = Depends(files_dep),
    publisher: Publisher = Depends(publisher_dep),
) -> dict[str, Any]:
    """Append version N+1 and reset the review status."""
    doc = visible(await store.reports.get(report_id), principal, "Relatório")
    content = await read_pdf_upload(file)
    number = len(doc["versions"]) + 1
    now = datetime.now(UTC)
    path = files.save(f"reports/{report_id}/v{number}.pdf", content)
    await store.reports.update(
        report_id,
        {"status": "submitted", "review_comment": None},
        push={
            "versions": _version(number, file.filename or "relatorio.pdf", path, len(content), now)
        },
    )
    await publisher.publish(EventType.REPORT_SUBMITTED, _report_event(doc, number, now))
    return public(await store.reports.get(report_id))


@router.get("/reports", tags=["reports"], summary="Listar relatórios visíveis ao papel")
async def list_reports(
    application_id: int | None = None,
    principal: Principal = Depends(get_current_principal),
    store: Store = Depends(store_dep),
) -> list[dict[str, Any]]:
    """Reports of the caller's scope, optionally for one internship."""
    filters = scope(principal)
    if application_id is not None:
        filters["application_id"] = application_id
    return [public(d) for d in await store.reports.find(filters)]


@router.get("/reports/{report_id}", tags=["reports"], summary="Detalhe do relatório")
async def get_report(
    report_id: str,
    principal: Principal = Depends(get_current_principal),
    store: Store = Depends(store_dep),
) -> dict[str, Any]:
    """Report metadata with all versions."""
    return public(visible(await store.reports.get(report_id), principal, "Relatório"))


@router.get(
    "/reports/{report_id}/versions/{version}/file",
    tags=["reports"],
    summary="Baixar uma versão do relatório",
)
async def report_file(
    report_id: str,
    version: int,
    principal: Principal = Depends(get_current_principal),
    store: Store = Depends(store_dep),
    files: FileStorage = Depends(files_dep),
) -> Response:
    """Return the PDF of one version."""
    doc = visible(await store.reports.get(report_id), principal, "Relatório")
    match = next((v for v in doc["versions"] if v["version"] == version), None)
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Versão não encontrada")
    return Response(
        files.read(match["path"]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{report_id}-v{version}.pdf"'},
    )


@router.post(
    "/reports/{report_id}/review",
    tags=["reports"],
    summary="Registrar revisão da coordenação",
)
async def review_report(
    report_id: str,
    body: ReviewIn,
    principal: Principal = Depends(require_role(Role.COORDINATOR)),
    store: Store = Depends(store_dep),
) -> dict[str, Any]:
    """Mark the latest version as reviewed with a comment."""
    if await store.reports.get(report_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relatório não encontrado")
    await store.reports.update(
        report_id,
        {"status": "reviewed", "review_comment": body.comment, "reviewed_by": principal.id},
    )
    return public(await store.reports.get(report_id))
