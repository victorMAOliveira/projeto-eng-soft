"""Repositories built on :class:`eh_db.BaseRepository`."""

from sqlalchemy import select

from eh_db import BaseRepository
from user_service.models import CompanyProfile, StudentProfile, User


class UserRepository(BaseRepository[User]):
    """Queries over accounts."""

    model = User

    async def by_email(self, email: str) -> User | None:
        """Return the account with ``email`` (already normalised) or ``None``."""
        return await self.session.scalar(select(User).where(User.email == email))

    async def by_ids(self, ids: list[int]) -> list[User]:
        """Return the accounts whose id is in ``ids``."""
        if not ids:
            return []
        result = await self.session.scalars(select(User).where(User.id.in_(ids)).order_by(User.id))
        return list(result.all())


class StudentProfileRepository(BaseRepository[StudentProfile]):
    """Student profiles (primary key = user id)."""

    model = StudentProfile


class CompanyProfileRepository(BaseRepository[CompanyProfile]):
    """Company profiles (primary key = user id)."""

    model = CompanyProfile
