"""HTTP API of the internship-service."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from eh_auth import Principal, Role, get_current_principal, require_role
from eh_events import EventType, InternshipClosed, InternshipPublished, Publisher
from internship_service.models import Internship
from internship_service.repository import InternshipRepository
from internship_service.schemas import InternshipIn, InternshipOut, InternshipPage, InternshipStats

router = APIRouter(tags=["internships"])


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Session bound to this service's own database."""
    async with request.app.state.db.session() as session:
        yield session


def get_publisher(request: Request) -> Publisher:
    """Event publisher configured at startup."""
    return request.app.state.publisher


def published_event(internship: Internship) -> InternshipPublished:
    """Build the ``internship.published`` payload (full offer, for read models)."""
    return InternshipPublished(
        internship_id=internship.id,
        company_id=internship.company_id,
        company_name=internship.company_name,
        title=internship.title,
        description=internship.description,
        requirements=list(internship.requirements),
        course=internship.course,
        min_semester=internship.min_semester,
        hours_per_day=internship.hours_per_day,
        hours_per_week=internship.hours_per_week,
        modality=internship.modality,
        city=internship.city,
        stipend=internship.stipend,
        published_at=internship.published_at,
    )


@router.get("/internships", response_model=InternshipPage, summary="Buscar vagas")
async def search_internships(
    q: str | None = Query(None, max_length=100, description="Texto livre"),
    course: str | None = None,
    modality: Literal["onsite", "remote", "hybrid"] | None = None,
    city: str | None = None,
    status_filter: Literal["open", "closed", "all"] = Query("open", alias="status"),
    company_id: int | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    _: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> InternshipPage:
    """Search offers (open ones by default) with filters and pagination."""
    items, total = await InternshipRepository(session).search(
        q=q,
        course=course,
        modality=modality,
        city=city,
        status=None if status_filter == "all" else status_filter,
        company_id=company_id,
        offset=(page - 1) * size,
        limit=size,
    )
    return InternshipPage(
        items=[InternshipOut.model_validate(i) for i in items], total=total, page=page, size=size
    )


@router.get("/internships/mine", response_model=list[InternshipOut], summary="Vagas da empresa")
async def my_internships(
    principal: Principal = Depends(require_role(Role.COMPANY)),
    session: AsyncSession = Depends(get_session),
) -> list[Internship]:
    """All offers (open and closed) of the calling company."""
    items, _ = await InternshipRepository(session).search(
        status=None, company_id=principal.id, limit=200
    )
    return items


@router.get("/internships/stats", response_model=InternshipStats, summary="Indicadores")
async def stats(
    _: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> InternshipStats:
    """Counters of open/closed offers, by course and by modality."""
    repo = InternshipRepository(session)
    return InternshipStats(
        open=await repo.count(status="open"),
        closed=await repo.count(status="closed"),
        by_course=await repo.counts_by("course"),
        by_modality=await repo.counts_by("modality"),
    )


@router.get("/internships/{internship_id}", response_model=InternshipOut, summary="Detalhe")
async def get_internship(
    internship_id: int,
    _: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> Internship:
    """Return one offer."""
    internship = await InternshipRepository(session).get(internship_id)
    if internship is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vaga não encontrada")
    return internship


@router.post(
    "/internships",
    response_model=InternshipOut,
    status_code=status.HTTP_201_CREATED,
    summary="Publicar vaga (empresa; publica internship.published)",
)
async def publish_internship(
    body: InternshipIn,
    principal: Principal = Depends(require_role(Role.COMPANY)),
    session: AsyncSession = Depends(get_session),
    publisher: Publisher = Depends(get_publisher),
) -> Internship:
    """Publish an offer; workload limits of Lei 11.788/2008 are validated (422)."""
    internship = await InternshipRepository(session).add(
        Internship(**body.model_dump(), company_id=principal.id, company_name=principal.name)
    )
    await session.commit()
    await publisher.publish(EventType.INTERNSHIP_PUBLISHED, published_event(internship))
    return internship


@router.post(
    "/internships/{internship_id}/close",
    response_model=InternshipOut,
    summary="Encerrar vaga (empresa dona ou coordenação; publica internship.closed)",
)
async def close_internship(
    internship_id: int,
    principal: Principal = Depends(require_role(Role.COMPANY, Role.COORDINATOR)),
    session: AsyncSession = Depends(get_session),
    publisher: Publisher = Depends(get_publisher),
) -> Internship:
    """Close an open offer."""
    internship = await InternshipRepository(session).get(internship_id)
    if internship is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vaga não encontrada")
    if principal.role == Role.COMPANY and internship.company_id != principal.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "A vaga pertence a outra empresa")
    if internship.status == "closed":
        raise HTTPException(status.HTTP_409_CONFLICT, "A vaga já está encerrada")
    internship.status = "closed"
    internship.closed_at = datetime.now(UTC)
    await session.commit()
    await publisher.publish(
        EventType.INTERNSHIP_CLOSED,
        InternshipClosed(internship_id=internship.id, company_id=internship.company_id),
    )
    return internship
