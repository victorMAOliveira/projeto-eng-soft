"""HTTP API of the user-service: authentication, accounts and profiles."""

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from eh_auth import (
    JWTAuth,
    Principal,
    Role,
    get_current_principal,
    get_optional_principal,
    hash_password,
    require_role,
    verify_password,
)
from eh_events import EventType, ProfileUpdated, Publisher, UserRegistered
from user_service.models import CompanyProfile, StudentProfile, User
from user_service.repository import (
    UserRepository,
)
from user_service.schemas import (
    CompanyProfileIn,
    CompanyProfileOut,
    LoginRequest,
    RegisterRequest,
    StudentProfileIn,
    StudentProfileOut,
    TokenResponse,
    UserOut,
)

router = APIRouter()
PROFILE_FIELDS = ("course", "semester", "skills", "resume_summary", "weekly_availability_hours")


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Session bound to this service's own database."""
    async with request.app.state.db.session() as session:
        yield session


def get_publisher(request: Request) -> Publisher:
    """Event publisher configured at startup."""
    return request.app.state.publisher


def get_auth(request: Request) -> JWTAuth:
    """JWT issuer/validator configured at startup."""
    return request.app.state.auth


def profile_completeness(profile: StudentProfile | None) -> float:
    """Share (0..1) of the recommendation-relevant fields that are filled."""
    if profile is None:
        return 0.0
    filled = sum(1 for field in PROFILE_FIELDS if getattr(profile, field))
    return round(filled / len(PROFILE_FIELDS), 2)


def student_out(user: User) -> StudentProfileOut:
    """Merge account and profile into the API representation."""
    profile = user.student_profile
    data = {"user_id": user.id, "name": user.full_name, "email": user.email}
    if profile is not None:
        data.update(
            course=profile.course,
            semester=profile.semester,
            enrollment=profile.enrollment,
            skills=list(profile.skills or []),
            resume_summary=profile.resume_summary or "",
            weekly_availability_hours=profile.weekly_availability_hours,
            preferred_modality=profile.preferred_modality,
            city=profile.city,
            is_pcd=profile.is_pcd,
            updated_at=profile.updated_at,
        )
    return StudentProfileOut(**data, completeness=profile_completeness(profile))


def company_out(user: User) -> CompanyProfileOut:
    """Merge account and company profile into the API representation."""
    profile = user.company_profile
    return CompanyProfileOut(
        user_id=user.id,
        email=user.email,
        trade_name=profile.trade_name if profile else user.full_name,
        cnpj=profile.cnpj if profile else None,
        sector=profile.sector if profile else None,
        city=profile.city if profile else None,
        description=profile.description if profile else "",
        website=profile.website if profile else None,
    )


# --------------------------------------------------------------------- auth
@router.post(
    "/auth/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    tags=["auth"],
    summary="Cadastrar conta (estudante ou empresa; coordenação exige token de coordenação)",
)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
    publisher: Publisher = Depends(get_publisher),
    caller: Principal | None = Depends(get_optional_principal),
) -> User:
    """Create an account, its empty profile and publish ``user.registered``."""
    if body.role == Role.COORDINATOR and (
        caller is None or caller.role not in (Role.COORDINATOR, Role.SERVICE)
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cadastro de coordenação é restrito")
    users = UserRepository(session)
    if await users.by_email(body.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "E-mail já cadastrado")
    user = await users.add(
        User(
            email=body.email,
            password_hash=hash_password(body.password),
            full_name=body.full_name.strip(),
            role=body.role,
        )
    )
    if body.role == Role.STUDENT:
        session.add(StudentProfile(user_id=user.id, skills=[]))
    elif body.role == Role.COMPANY:
        session.add(CompanyProfile(user_id=user.id, trade_name=user.full_name))
    await session.commit()
    await publisher.publish(
        EventType.USER_REGISTERED,
        UserRegistered(user_id=user.id, email=user.email, name=user.full_name, role=user.role),
    )
    return user


@router.post("/auth/login", response_model=TokenResponse, tags=["auth"], summary="Login")
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
    auth: JWTAuth = Depends(get_auth),
) -> TokenResponse:
    """Check the password (argon2) and issue a JWT carrying the user's role."""
    user = await UserRepository(session).by_email(body.email)
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha inválidos")
    token = auth.create_token(
        user_id=user.id, role=user.role, name=user.full_name, email=user.email
    )
    return TokenResponse(
        access_token=token,
        expires_in=auth.expires_minutes * 60,
        user=UserOut.model_validate(user),
    )


# -------------------------------------------------------------------- users
@router.get("/users/me", response_model=UserOut, tags=["users"], summary="Conta autenticada")
async def me(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Return the caller's account."""
    user = await UserRepository(session).get(principal.id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conta não encontrada")
    return user


@router.get(
    "/users",
    response_model=list[UserOut],
    tags=["users"],
    summary="Listar contas (coordenação/serviços)",
)
async def list_users(
    role: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    _: Principal = Depends(require_role(Role.COORDINATOR, Role.SERVICE)),
    session: AsyncSession = Depends(get_session),
) -> list[User]:
    """List accounts, optionally filtered by role."""
    filters = {"role": role} if role else {}
    return await UserRepository(session).list(limit=limit, order_by=[User.id], **filters)


@router.get("/users/{user_id}", response_model=UserOut, tags=["users"], summary="Conta por id")
async def get_user(
    user_id: int,
    _: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Return the public data of an account."""
    user = await UserRepository(session).get(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conta não encontrada")
    return user


# ---------------------------------------------------------- student profile
@router.get(
    "/profiles/students/me",
    response_model=StudentProfileOut,
    tags=["profiles"],
    summary="Meu perfil acadêmico",
)
async def my_student_profile(
    principal: Principal = Depends(require_role(Role.STUDENT)),
    session: AsyncSession = Depends(get_session),
) -> StudentProfileOut:
    """Return the caller's academic profile."""
    user = await UserRepository(session).get(principal.id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conta não encontrada")
    return student_out(user)


@router.put(
    "/profiles/students/me",
    response_model=StudentProfileOut,
    tags=["profiles"],
    summary="Atualizar meu perfil acadêmico (publica profile.updated)",
)
async def update_student_profile(
    body: StudentProfileIn,
    principal: Principal = Depends(require_role(Role.STUDENT)),
    session: AsyncSession = Depends(get_session),
    publisher: Publisher = Depends(get_publisher),
) -> StudentProfileOut:
    """Save the academic profile and publish ``profile.updated`` with all its data."""
    user = await UserRepository(session).get(principal.id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conta não encontrada")
    profile = user.student_profile or StudentProfile(user_id=user.id)
    for field, value in body.model_dump().items():
        setattr(profile, field, value)
    session.add(profile)
    await session.commit()
    await session.refresh(user)
    result = student_out(user)
    await publisher.publish(
        EventType.PROFILE_UPDATED,
        ProfileUpdated(
            user_id=user.id,
            name=user.full_name,
            **body.model_dump(exclude={"enrollment"}),
        ),
    )
    return result


@router.get(
    "/profiles/students",
    response_model=list[StudentProfileOut],
    tags=["profiles"],
    summary="Perfis de vários estudantes (empresa, coordenação, serviços)",
)
async def student_profiles_batch(
    ids: str = Query(..., description="IDs separados por vírgula", examples=["1,2,3"]),
    _: Principal = Depends(require_role(Role.COMPANY, Role.COORDINATOR, Role.SERVICE)),
    session: AsyncSession = Depends(get_session),
) -> list[StudentProfileOut]:
    """Return the profiles of the given students (unknown ids are ignored)."""
    try:
        id_list = [int(x) for x in ids.split(",") if x.strip()][:200]
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "ids inválidos") from exc
    users = await UserRepository(session).by_ids(id_list)
    return [student_out(u) for u in users if u.role == Role.STUDENT]


@router.get(
    "/profiles/students/{user_id}",
    response_model=StudentProfileOut,
    tags=["profiles"],
    summary="Perfil de um estudante",
)
async def student_profile(
    user_id: int,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> StudentProfileOut:
    """Return a student profile (the student, companies, coordination or services)."""
    if principal.role == Role.STUDENT and principal.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso negado ao perfil de outro estudante")
    user = await UserRepository(session).get(user_id)
    if user is None or user.role != Role.STUDENT:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Estudante não encontrado")
    return student_out(user)


# ---------------------------------------------------------- company profile
@router.get(
    "/profiles/companies/me",
    response_model=CompanyProfileOut,
    tags=["profiles"],
    summary="Perfil da minha empresa",
)
async def my_company_profile(
    principal: Principal = Depends(require_role(Role.COMPANY)),
    session: AsyncSession = Depends(get_session),
) -> CompanyProfileOut:
    """Return the caller's company profile."""
    user = await UserRepository(session).get(principal.id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conta não encontrada")
    return company_out(user)


@router.put(
    "/profiles/companies/me",
    response_model=CompanyProfileOut,
    tags=["profiles"],
    summary="Atualizar perfil da empresa",
)
async def update_company_profile(
    body: CompanyProfileIn,
    principal: Principal = Depends(require_role(Role.COMPANY)),
    session: AsyncSession = Depends(get_session),
) -> CompanyProfileOut:
    """Save the company profile."""
    user = await UserRepository(session).get(principal.id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conta não encontrada")
    profile = user.company_profile or CompanyProfile(user_id=user.id, trade_name=body.trade_name)
    for field, value in body.model_dump().items():
        setattr(profile, field, value)
    session.add(profile)
    await session.commit()
    await session.refresh(user)
    return company_out(user)


@router.get(
    "/profiles/companies/{user_id}",
    response_model=CompanyProfileOut,
    tags=["profiles"],
    summary="Perfil público de uma empresa",
)
async def company_profile(
    user_id: int,
    _: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> CompanyProfileOut:
    """Return a company profile."""
    user = await UserRepository(session).get(user_id)
    if user is None or user.role != Role.COMPANY:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa não encontrada")
    return company_out(user)
