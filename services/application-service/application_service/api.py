"""HTTP API of the application-service (applications, transitions, placements)."""

from collections.abc import AsyncIterator
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from application_service.domain import (
    FINAL_STATUSES,
    InvalidTransitionError,
    LegalRuleViolationError,
    Status,
    eligibility_problems,
    validate_duration,
    validate_insurance,
    validate_workload,
)
from application_service.models import Application, Placement, StatusChange
from application_service.schemas import (
    ApplicationIn,
    ApplicationOut,
    Board,
    PlacementIn,
    PlacementSummary,
    ReasonIn,
)
from application_service.service import (
    placement_summary,
    previous_days_at_company,
    status_changed_event,
    to_out,
    transition,
)
from application_service.upstreams import Upstreams
from eh_auth import Principal, Role, get_current_principal, require_role
from eh_events import ApplicationSubmitted, EventType, Publisher

router = APIRouter()

BOARD_COLUMNS = [
    Status.SUBMITTED,
    Status.UNDER_REVIEW,
    Status.APPROVED,
    Status.AGREEMENT_PENDING,
    Status.ACTIVE,
    Status.COMPLETED,
    "closed",
]


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Session bound to this service's own database."""
    async with request.app.state.db.session() as session:
        yield session


def get_publisher(request: Request) -> Publisher:
    """Event publisher configured at startup."""
    return request.app.state.publisher


def get_upstreams(request: Request) -> Upstreams:
    """REST clients for other services."""
    return request.app.state.upstreams


def bearer(request: Request) -> str:
    """The caller's raw bearer token (forwarded to upstream services)."""
    return request.headers.get("authorization", "").partition(" ")[2]


def scope_filter(principal: Principal):
    """SQL condition restricting rows to what ``principal`` may see."""
    if principal.role == Role.STUDENT:
        return Application.student_id == principal.id
    if principal.role == Role.COMPANY:
        return Application.company_id == principal.id
    return True  # coordinator and internal services see everything


async def load(session: AsyncSession, application_id: int, principal: Principal) -> Application:
    """Load an application the caller may access (404/403 otherwise)."""
    application = await session.get(Application, application_id)
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidatura não encontrada")
    owner = (principal.role == Role.STUDENT and application.student_id == principal.id) or (
        principal.role == Role.COMPANY and application.company_id == principal.id
    )
    if not owner and principal.role not in (Role.COORDINATOR, Role.SERVICE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso negado a esta candidatura")
    return application


async def commit_transition(
    session: AsyncSession,
    publisher: Publisher,
    application: Application,
    target: str,
    principal: Principal,
    reason: str | None = None,
) -> ApplicationOut:
    """Apply a transition (409 when invalid), commit, then publish the event."""
    try:
        previous = transition(
            application, target, actor_id=principal.id, actor_role=principal.role, reason=reason
        )
    except InvalidTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    await publisher.publish(
        EventType.APPLICATION_STATUS_CHANGED, status_changed_event(application, previous)
    )
    return to_out(application)


@router.post(
    "/applications",
    response_model=ApplicationOut,
    status_code=status.HTTP_201_CREATED,
    tags=["applications"],
    summary="Candidatar-se a uma vaga (estudante; publica application.submitted)",
)
async def submit(
    body: ApplicationIn,
    request: Request,
    principal: Principal = Depends(require_role(Role.STUDENT)),
    session: AsyncSession = Depends(get_session),
    publisher: Publisher = Depends(get_publisher),
    upstreams: Upstreams = Depends(get_upstreams),
) -> ApplicationOut:
    """Validate the offer (open) and eligibility (course, period, availability)."""
    token = bearer(request)
    internship = await upstreams.internship(body.internship_id, token)
    if internship is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vaga não encontrada")
    if internship["status"] != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, "A vaga não está aberta")
    profile = await upstreams.student_profile(principal.id, token) or {}
    problems = eligibility_problems(
        student_course=profile.get("course"),
        student_semester=profile.get("semester"),
        weekly_availability=profile.get("weekly_availability_hours"),
        internship_course=internship["course"],
        min_semester=internship["min_semester"],
        hours_per_week=internship["hours_per_week"],
    )
    if problems:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, " ".join(problems))
    duplicate = await session.scalar(
        select(Application.id).where(
            Application.internship_id == body.internship_id,
            Application.student_id == principal.id,
        )
    )
    if duplicate:
        raise HTTPException(status.HTTP_409_CONFLICT, "Você já se candidatou a esta vaga")

    application = Application(
        internship_id=body.internship_id,
        student_id=principal.id,
        company_id=internship["company_id"],
        student_name=principal.name,
        company_name=internship["company_name"],
        internship_title=internship["title"],
        student_course=profile.get("course"),
        student_is_pcd=bool(profile.get("is_pcd")),
        internship_hours_per_day=internship["hours_per_day"],
        internship_hours_per_week=internship["hours_per_week"],
        internship_stipend=internship["stipend"],
        cover_letter=body.cover_letter,
        status=Status.SUBMITTED,
        # set explicitly: reading an unloaded relationship would lazy-load (async IO)
        placement=None,
        history=[
            StatusChange(
                from_status=None,
                to_status=Status.SUBMITTED,
                actor_id=principal.id,
                actor_role=principal.role,
            )
        ],
    )
    session.add(application)
    await session.commit()
    await publisher.publish(
        EventType.APPLICATION_SUBMITTED,
        ApplicationSubmitted(
            application_id=application.id,
            internship_id=application.internship_id,
            student_id=application.student_id,
            company_id=application.company_id,
            student_name=application.student_name,
            internship_title=application.internship_title,
        ),
    )
    return to_out(application)


@router.get(
    "/applications",
    response_model=list[ApplicationOut],
    tags=["applications"],
    summary="Listar candidaturas visíveis ao papel (filtros: vaga, status)",
)
async def list_applications(
    internship_id: int | None = None,
    status_filter: str | None = Query(None, alias="status"),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[ApplicationOut]:
    """Students see their own, companies those of their offers, coordination all."""
    stmt = select(Application).where(scope_filter(principal)).order_by(Application.id.desc())
    if internship_id is not None:
        stmt = stmt.where(Application.internship_id == internship_id)
    if status_filter:
        stmt = stmt.where(Application.status == status_filter)
    rows = await session.scalars(stmt.limit(500))
    return [to_out(a) for a in rows.all()]


@router.get(
    "/applications/board",
    response_model=Board,
    tags=["applications"],
    summary="Candidaturas agrupadas por status (kanban)",
)
async def board(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> Board:
    """Kanban columns; rejected, withdrawn and terminated share the ``closed`` column."""
    rows = await session.scalars(
        select(Application).where(scope_filter(principal)).order_by(Application.updated_at.desc())
    )
    columns: dict[str, list[ApplicationOut]] = {str(c): [] for c in BOARD_COLUMNS}
    total = 0
    for application in rows.all():
        key = (
            "closed"
            if application.status in FINAL_STATUSES - {Status.COMPLETED}
            else application.status
        )
        columns[key].append(to_out(application))
        total += 1
    return Board(columns=columns, total=total)


@router.get(
    "/applications/stats",
    tags=["applications"],
    summary="Contagem por status (escopo do papel)",
)
async def stats(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    """Number of applications per status."""
    rows = await session.scalars(select(Application.status).where(scope_filter(principal)))
    counts = {s.value: 0 for s in Status}
    for value in rows.all():
        counts[value] += 1
    return counts


@router.get(
    "/applications/{application_id}",
    response_model=ApplicationOut,
    tags=["applications"],
    summary="Detalhe da candidatura (com termos e histórico)",
)
async def get_application(
    application_id: int,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> ApplicationOut:
    """Return one application visible to the caller."""
    return to_out(await load(session, application_id, principal))


@router.post(
    "/applications/{application_id}/review",
    response_model=ApplicationOut,
    tags=["transitions"],
    summary="Iniciar análise (empresa): submitted → under_review",
)
async def review(
    application_id: int,
    principal: Principal = Depends(require_role(Role.COMPANY)),
    session: AsyncSession = Depends(get_session),
    publisher: Publisher = Depends(get_publisher),
) -> ApplicationOut:
    """Company starts reviewing the application."""
    application = await load(session, application_id, principal)
    return await commit_transition(session, publisher, application, Status.UNDER_REVIEW, principal)


@router.post(
    "/applications/{application_id}/approve",
    response_model=ApplicationOut,
    tags=["transitions"],
    summary="Aprovar candidato com os termos do estágio (empresa): under_review → approved",
)
async def approve(
    application_id: int,
    body: PlacementIn,
    principal: Principal = Depends(require_role(Role.COMPANY)),
    session: AsyncSession = Depends(get_session),
    publisher: Publisher = Depends(get_publisher),
) -> ApplicationOut:
    """Validate Lei 11.788/2008 rules (422) and approve; starts the TCE saga."""
    application = await load(session, application_id, principal)
    hours_day = body.hours_per_day or application.internship_hours_per_day
    hours_week = body.hours_per_week or application.internship_hours_per_week
    try:
        validate_workload(hours_day, hours_week)
        validate_insurance(body.insurer, body.insurance_policy)
        previous = await previous_days_at_company(
            session,
            student_id=application.student_id,
            company_id=application.company_id,
            exclude_application=application.id,
        )
        validate_duration(
            body.start_date,
            body.end_date,
            is_pcd=application.student_is_pcd,
            previous_days=previous,
        )
    except LegalRuleViolationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, exc.message) from exc
    if application.status != Status.UNDER_REVIEW:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Transição inválida: {application.status} → approved"
        )
    application.placement = Placement(
        start_date=body.start_date,
        end_date=body.end_date,
        hours_per_day=hours_day,
        hours_per_week=hours_week,
        stipend=body.stipend if body.stipend is not None else application.internship_stipend,
        insurer=(body.insurer or "").strip(),
        insurance_policy=(body.insurance_policy or "").strip(),
        supervisor_name=body.supervisor_name.strip(),
        activities=body.activities,
    )
    return await commit_transition(session, publisher, application, Status.APPROVED, principal)


@router.post(
    "/applications/{application_id}/reject",
    response_model=ApplicationOut,
    tags=["transitions"],
    summary="Rejeitar (empresa): under_review → rejected",
)
async def reject(
    application_id: int,
    body: ReasonIn,
    principal: Principal = Depends(require_role(Role.COMPANY)),
    session: AsyncSession = Depends(get_session),
    publisher: Publisher = Depends(get_publisher),
) -> ApplicationOut:
    """Company rejects the candidate, optionally with a reason."""
    application = await load(session, application_id, principal)
    return await commit_transition(
        session, publisher, application, Status.REJECTED, principal, body.reason
    )


@router.post(
    "/applications/{application_id}/withdraw",
    response_model=ApplicationOut,
    tags=["transitions"],
    summary="Desistir (estudante): submitted|under_review → withdrawn",
)
async def withdraw(
    application_id: int,
    body: ReasonIn,
    principal: Principal = Depends(require_role(Role.STUDENT)),
    session: AsyncSession = Depends(get_session),
    publisher: Publisher = Depends(get_publisher),
) -> ApplicationOut:
    """Student withdraws the application."""
    application = await load(session, application_id, principal)
    return await commit_transition(
        session, publisher, application, Status.WITHDRAWN, principal, body.reason
    )


@router.post(
    "/applications/{application_id}/complete",
    response_model=ApplicationOut,
    tags=["transitions"],
    summary="Concluir estágio (empresa/coordenação): active → completed",
)
async def complete(
    application_id: int,
    body: ReasonIn,
    principal: Principal = Depends(require_role(Role.COMPANY, Role.COORDINATOR)),
    session: AsyncSession = Depends(get_session),
    publisher: Publisher = Depends(get_publisher),
) -> ApplicationOut:
    """Finish an active internship normally."""
    application = await load(session, application_id, principal)
    return await commit_transition(
        session, publisher, application, Status.COMPLETED, principal, body.reason
    )


@router.post(
    "/applications/{application_id}/terminate",
    response_model=ApplicationOut,
    tags=["transitions"],
    summary="Rescindir estágio (empresa/coordenação): active → terminated",
)
async def terminate(
    application_id: int,
    body: ReasonIn,
    principal: Principal = Depends(require_role(Role.COMPANY, Role.COORDINATOR)),
    session: AsyncSession = Depends(get_session),
    publisher: Publisher = Depends(get_publisher),
) -> ApplicationOut:
    """End an active internship early."""
    application = await load(session, application_id, principal)
    return await commit_transition(
        session, publisher, application, Status.TERMINATED, principal, body.reason
    )


@router.get(
    "/placements",
    response_model=list[PlacementSummary],
    tags=["placements"],
    summary="Estágios (com prazos de relatório) visíveis ao papel",
)
async def placements(
    status_filter: str = Query(
        "active", alias="status", description="Status separados por vírgula"
    ),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[PlacementSummary]:
    """Internships with report deadlines (used by dashboards and the follow-up agent)."""
    statuses = [s.strip() for s in status_filter.split(",") if s.strip()]
    rows = await session.scalars(
        select(Application)
        .join(Placement)
        .where(scope_filter(principal), Application.status.in_(statuses))
        .order_by(Placement.next_report_due.asc().nulls_last(), Application.id)
    )
    today = date.today()
    return [placement_summary(a, today) for a in rows.all()]
