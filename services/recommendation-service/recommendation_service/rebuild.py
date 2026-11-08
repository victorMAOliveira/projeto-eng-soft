"""Rebuild the read model from the source services (REST, service token).

Normally the read model is fed by events; this is the recovery path when the
recommendation database is lost or the service joins an existing system.
"""

from datetime import UTC, datetime
from typing import Any

from eh_auth import JWTAuth
from eh_db import Database
from eh_http import ResilientClient
from recommendation_service.models import RmApplication, RmInternship, RmStudent


class Rebuilder:
    """Pulls users, profiles, offers and applications and upserts the ``rm_*`` tables."""

    def __init__(
        self,
        db: Database,
        auth: JWTAuth,
        users: ResilientClient,
        internships: ResilientClient,
        applications: ResilientClient,
    ) -> None:
        self.db = db
        self.auth = auth
        self.users = users
        self.internships = internships
        self.applications = applications

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.auth.create_service_token('recommendation-service')}"
        }

    async def _json(self, client: ResilientClient, path: str, **params: Any) -> Any:
        response = await client.get(path, params=params, headers=self._headers())
        response.raise_for_status()
        return response.json()

    async def run(self) -> dict[str, int]:
        """Rebuild everything; returns how many rows of each kind were imported."""
        users = await self._json(self.users, "/users", role="student", limit=500)
        ids = [u["id"] for u in users]
        profiles = []
        for start in range(0, len(ids), 100):
            chunk = ",".join(str(i) for i in ids[start : start + 100])
            profiles += await self._json(self.users, "/profiles/students", ids=chunk)
        offers, page = [], 1
        while True:
            data = await self._json(
                self.internships, "/internships", status="all", page=page, size=100
            )
            offers += data["items"]
            if page * data["size"] >= data["total"]:
                break
            page += 1
        applications = await self._json(self.applications, "/applications")

        async with self.db.session() as session:
            for p in profiles:
                row = await session.get(RmStudent, p["user_id"]) or RmStudent(
                    student_id=p["user_id"]
                )
                row.name = p["name"]
                row.course = p.get("course")
                row.semester = p.get("semester")
                row.skills = p.get("skills") or []
                row.resume_summary = p.get("resume_summary") or ""
                row.weekly_availability_hours = p.get("weekly_availability_hours")
                row.preferred_modality = p.get("preferred_modality")
                row.city = p.get("city")
                session.add(row)
            popularity: dict[int, int] = {}
            for a in applications:
                popularity[a["internship_id"]] = popularity.get(a["internship_id"], 0) + 1
                row = await session.get(RmApplication, a["id"]) or RmApplication(
                    application_id=a["id"]
                )
                row.internship_id = a["internship_id"]
                row.student_id = a["student_id"]
                row.status = a["status"]
                session.add(row)
            for o in offers:
                row = await session.get(RmInternship, o["id"]) or RmInternship(
                    internship_id=o["id"]
                )
                for field in (
                    "company_id",
                    "company_name",
                    "title",
                    "description",
                    "requirements",
                    "course",
                    "min_semester",
                    "hours_per_day",
                    "hours_per_week",
                    "modality",
                    "city",
                    "stipend",
                    "status",
                ):
                    setattr(row, field, o[field])
                row.published_at = datetime.fromisoformat(
                    o["published_at"].replace("Z", "+00:00")
                ).astimezone(UTC)
                row.popularity = popularity.get(o["id"], 0)
                session.add(row)
        return {
            "students": len(profiles),
            "internships": len(offers),
            "applications": len(applications),
        }
