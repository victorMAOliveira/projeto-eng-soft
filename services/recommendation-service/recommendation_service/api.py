"""HTTP API of the recommendation-service."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from eh_auth import Principal, Role, get_current_principal, require_role
from recommendation_service.models import RmApplication, RmInternship, RmStudent
from recommendation_service.recommender import (
    OfferFeatures,
    Recommendation,
    StudentFeatures,
    Weights,
    rank_candidates,
    recommend_for_student,
)

router = APIRouter(tags=["recommendations"])


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Session bound to this service's read model."""
    async with request.app.state.db.session() as session:
        yield session


def get_weights(request: Request) -> Weights:
    """Configured weights of the final score."""
    return request.app.state.weights


def to_student(row: RmStudent) -> StudentFeatures:
    """Read-model row → recommender features."""
    return StudentFeatures(
        id=row.student_id,
        name=row.name,
        course=row.course,
        semester=row.semester,
        skills=list(row.skills or []),
        summary=row.resume_summary or "",
        weekly_hours=row.weekly_availability_hours,
        modality=row.preferred_modality,
        city=row.city,
    )


def to_offer(row: RmInternship) -> OfferFeatures:
    """Read-model row → recommender features."""
    return OfferFeatures(
        id=row.internship_id,
        title=row.title,
        description=row.description,
        requirements=list(row.requirements or []),
        course=row.course,
        min_semester=row.min_semester,
        hours_per_day=row.hours_per_day,
        hours_per_week=row.hours_per_week,
        modality=row.modality,
        city=row.city,
        status=row.status,
        company_name=row.company_name,
        stipend=row.stipend,
        published_at=row.published_at,
        popularity=row.popularity,
    )


def serialize(rec: Recommendation, extra: dict[str, Any]) -> dict[str, Any]:
    """Recommendation + display fields of the recommended item."""
    return {
        **extra,
        "score": rec.score,
        "components": {"cosine": rec.cosine, "jaccard": rec.jaccard, "preference": rec.preference},
        "matched_skills": rec.matched_skills,
        "missing_skills": rec.missing_skills,
        "reasons": rec.reasons,
        "eliminated_by": rec.eliminated_by,
        "explanation": rec.explanation,
        "strategy": rec.strategy,
    }


def offer_view(row: RmInternship) -> dict[str, Any]:
    """Fields of an offer shown next to its score."""
    return {
        "internship_id": row.internship_id,
        "title": row.title,
        "company_name": row.company_name,
        "course": row.course,
        "modality": row.modality,
        "city": row.city,
        "stipend": row.stipend,
        "hours_per_week": row.hours_per_week,
        "requirements": row.requirements,
    }


@router.get(
    "/recommendations/students/{student_id}/internships",
    summary="Vagas recomendadas para um estudante (com explicação)",
)
async def recommend_internships(
    student_id: int,
    k: int = Query(10, ge=1, le=50),
    include_filtered: bool = False,
    principal: Principal = Depends(require_role(Role.STUDENT, Role.COORDINATOR, Role.SERVICE)),
    session: AsyncSession = Depends(get_session),
    weights: Weights = Depends(get_weights),
) -> dict[str, Any]:
    """Top-``k`` open offers for the student; already-applied offers are excluded."""
    if principal.role == Role.STUDENT and principal.id != student_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Recomendações de outro estudante")
    student_row = await session.get(RmStudent, student_id)
    student = to_student(student_row) if student_row else StudentFeatures(id=student_id)
    offers = {r.internship_id: r for r in (await session.scalars(select(RmInternship))).all()}
    applied = set(
        (
            await session.scalars(
                select(RmApplication.internship_id).where(RmApplication.student_id == student_id)
            )
        ).all()
    )
    ranked, filtered = recommend_for_student(
        student,
        [to_offer(o) for o in offers.values() if o.status == "open"],
        k=k,
        weights=weights,
        exclude_ids=applied,
    )
    return {
        "student_id": student_id,
        "strategy": ranked[0].strategy
        if ranked
        else ("cold_start" if not student.skills else "hybrid"),
        "weights": {
            "content": weights.content,
            "attributes": weights.attributes,
            "preference": weights.preference,
        },
        "generated_at": datetime.now(UTC).isoformat(),
        "items": [serialize(r, offer_view(offers[r.item_id])) for r in ranked],
        "filtered": [serialize(r, offer_view(offers[r.item_id])) for r in filtered]
        if include_filtered
        else [],
        "filtered_count": len(filtered),
        "already_applied": sorted(applied),
    }


@router.get(
    "/recommendations/internships/{internship_id}/candidates",
    summary="Ranking de candidatos de uma vaga (empresa dona, coordenação)",
)
async def recommend_candidates(
    internship_id: int,
    k: int = Query(10, ge=1, le=100),
    scope: Literal["applicants", "all"] = "applicants",
    principal: Principal = Depends(require_role(Role.COMPANY, Role.COORDINATOR, Role.SERVICE)),
    session: AsyncSession = Depends(get_session),
    weights: Weights = Depends(get_weights),
) -> dict[str, Any]:
    """Rank the applicants (default) or every student for an offer."""
    offer = await session.get(RmInternship, internship_id)
    if offer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vaga não encontrada no modelo de leitura")
    if principal.role == Role.COMPANY and offer.company_id != principal.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "A vaga pertence a outra empresa")
    applications = {
        a.student_id: a
        for a in (
            await session.scalars(
                select(RmApplication).where(RmApplication.internship_id == internship_id)
            )
        ).all()
    }
    stmt = select(RmStudent)
    if scope == "applicants":
        stmt = stmt.where(RmStudent.student_id.in_(list(applications) or [-1]))
    students = {s.student_id: s for s in (await session.scalars(stmt)).all()}
    ranked = rank_candidates(
        to_offer(offer), [to_student(s) for s in students.values()], k=k, weights=weights
    )
    items = []
    for rec in ranked:
        student = students[rec.item_id]
        application = applications.get(rec.item_id)
        items.append(
            serialize(
                rec,
                {
                    "student_id": student.student_id,
                    "name": student.name,
                    "course": student.course,
                    "semester": student.semester,
                    "skills": student.skills,
                    "application_id": application.application_id if application else None,
                    "application_status": application.status if application else None,
                },
            )
        )
    return {
        "internship_id": internship_id,
        "title": offer.title,
        "scope": scope,
        "requirements": offer.requirements,
        "items": items,
    }


@router.get("/recommendations/stats", summary="Tamanho do modelo de leitura e pesos")
async def stats(
    _: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    weights: Weights = Depends(get_weights),
) -> dict[str, Any]:
    """Counters of the read model (shows the projection is being fed)."""

    async def count(model, *where) -> int:
        return int(await session.scalar(select(func.count()).select_from(model).where(*where)) or 0)

    return {
        "students": await count(RmStudent),
        "internships_open": await count(RmInternship, RmInternship.status == "open"),
        "internships_total": await count(RmInternship),
        "applications": await count(RmApplication),
        "weights": {
            "content": weights.content,
            "attributes": weights.attributes,
            "preference": weights.preference,
        },
    }


@router.post(
    "/recommendations/rebuild",
    summary="Reconstruir o modelo de leitura a partir dos serviços de origem",
)
async def rebuild(
    request: Request,
    _: Principal = Depends(require_role(Role.COORDINATOR, Role.SERVICE)),
) -> dict[str, int]:
    """Re-import students, offers and applications via REST (recovery path)."""
    return await request.app.state.rebuilder.run()
