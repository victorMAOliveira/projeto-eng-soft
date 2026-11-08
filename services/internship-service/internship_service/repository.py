"""Internship queries."""

from sqlalchemy import String, cast, func, or_, select

from eh_db import BaseRepository
from internship_service.models import Internship


class InternshipRepository(BaseRepository[Internship]):
    """Search and statistics over internship offers."""

    model = Internship

    async def search(
        self,
        *,
        q: str | None = None,
        course: str | None = None,
        modality: str | None = None,
        city: str | None = None,
        status: str | None = "open",
        company_id: int | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Internship], int]:
        """Filter offers; ``q`` matches title, description, requirements or company."""
        conditions = []
        if q:
            like = f"%{q.strip()}%"
            conditions.append(
                or_(
                    Internship.title.ilike(like),
                    Internship.description.ilike(like),
                    Internship.company_name.ilike(like),
                    cast(Internship.requirements, String).ilike(like),
                )
            )
        if course:
            conditions.append(Internship.course == course)
        if modality:
            conditions.append(Internship.modality == modality)
        if city:
            conditions.append(Internship.city.ilike(city))
        if status:
            conditions.append(Internship.status == status)
        if company_id is not None:
            conditions.append(Internship.company_id == company_id)

        total = await self.session.scalar(
            select(func.count()).select_from(Internship).where(*conditions)
        )
        rows = await self.session.scalars(
            select(Internship)
            .where(*conditions)
            .order_by(Internship.published_at.desc(), Internship.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows.all()), int(total or 0)

    async def counts_by(self, column: str, status: str = "open") -> dict[str, int]:
        """Count offers with ``status`` grouped by ``column``."""
        attribute = getattr(Internship, column)
        rows = await self.session.execute(
            select(attribute, func.count())
            .where(Internship.status == status)
            .group_by(attribute)
            .order_by(func.count().desc())
        )
        return {key: count for key, count in rows.all()}
