"""Event handlers that keep the read model up to date (projection)."""

import logging

from sqlalchemy import func, select

from eh_db import Database
from eh_events import (
    ApplicationStatusChanged,
    ApplicationSubmitted,
    Event,
    EventType,
    InternshipClosed,
    InternshipPublished,
    ProfileUpdated,
    UserRegistered,
    typed_payload,
)
from recommendation_service.models import RmApplication, RmInternship, RmStudent

logger = logging.getLogger("recommendation-service.projection")

ROUTING_KEYS = [
    EventType.USER_REGISTERED.value,
    EventType.PROFILE_UPDATED.value,
    EventType.INTERNSHIP_PUBLISHED.value,
    EventType.INTERNSHIP_CLOSED.value,
    EventType.APPLICATION_SUBMITTED.value,
    EventType.APPLICATION_STATUS_CHANGED.value,
]


class Projection:
    """Applies events to the ``rm_*`` tables (idempotent upserts)."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def __call__(self, event: Event) -> None:
        """Dispatch by event type."""
        payload = typed_payload(event)
        async with self.db.session() as session:
            match event.event_type:
                case EventType.USER_REGISTERED:
                    await self._registered(session, payload)
                case EventType.PROFILE_UPDATED:
                    await self._profile(session, payload)
                case EventType.INTERNSHIP_PUBLISHED:
                    await self._published(session, payload)
                case EventType.INTERNSHIP_CLOSED:
                    await self._closed(session, payload)
                case EventType.APPLICATION_SUBMITTED:
                    await self._applied(session, payload)
                case EventType.APPLICATION_STATUS_CHANGED:
                    await self._status(session, payload)

    async def _registered(self, session, p: UserRegistered) -> None:
        if p.role == "student" and await session.get(RmStudent, p.user_id) is None:
            session.add(RmStudent(student_id=p.user_id, name=p.name, skills=[]))

    async def _profile(self, session, p: ProfileUpdated) -> None:
        student = await session.get(RmStudent, p.user_id) or RmStudent(student_id=p.user_id)
        student.name = p.name
        student.course = p.course
        student.semester = p.semester
        student.skills = list(p.skills)
        student.resume_summary = p.resume_summary
        student.weekly_availability_hours = p.weekly_availability_hours
        student.preferred_modality = p.preferred_modality
        student.city = p.city
        session.add(student)

    async def _published(self, session, p: InternshipPublished) -> None:
        offer = await session.get(RmInternship, p.internship_id) or RmInternship(
            internship_id=p.internship_id, popularity=0
        )
        for field in (
            "company_id",
            "company_name",
            "title",
            "description",
            "course",
            "min_semester",
            "hours_per_day",
            "hours_per_week",
            "modality",
            "city",
            "stipend",
            "published_at",
        ):
            setattr(offer, field, getattr(p, field))
        offer.requirements = list(p.requirements)
        offer.status = "open"
        session.add(offer)

    async def _closed(self, session, p: InternshipClosed) -> None:
        offer = await session.get(RmInternship, p.internship_id)
        if offer is not None:
            offer.status = "closed"

    async def _applied(self, session, p: ApplicationSubmitted) -> None:
        if await session.get(RmApplication, p.application_id) is None:
            session.add(
                RmApplication(
                    application_id=p.application_id,
                    internship_id=p.internship_id,
                    student_id=p.student_id,
                )
            )
            await session.flush()
        offer = await session.get(RmInternship, p.internship_id)
        if offer is not None:
            offer.popularity = await session.scalar(
                select(func.count()).where(RmApplication.internship_id == p.internship_id)
            )

    async def _status(self, session, p: ApplicationStatusChanged) -> None:
        application = await session.get(RmApplication, p.application_id)
        if application is not None:
            application.status = p.to_status
