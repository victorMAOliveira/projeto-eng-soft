"""TCE use cases: generation (saga step reacting to approval) and approval."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from document_service.pdf import AgreementData, MissingInsuranceError, render_agreement_pdf
from document_service.storage import FileStorage, Store
from eh_events import (
    AgreementGenerated,
    ApplicationStatusChanged,
    Event,
    EventType,
    Publisher,
    typed_payload,
)

logger = logging.getLogger("document-service.agreements")


class AgreementGenerator:
    """Saga step: ``application.status_changed(approved)`` → TCE PDF → ``agreement.generated``."""

    def __init__(self, store: Store, files: FileStorage, publisher: Publisher) -> None:
        self.store = store
        self.files = files
        self.publisher = publisher

    async def __call__(self, event: Event) -> None:
        """Event handler registered in the consumer."""
        if event.event_type != EventType.APPLICATION_STATUS_CHANGED:
            return
        payload: ApplicationStatusChanged = typed_payload(event)
        if payload.to_status == "approved" and payload.placement is not None:
            await self.generate(payload)

    async def generate(self, payload: ApplicationStatusChanged) -> dict[str, Any] | None:
        """Render, store and announce the TCE; returns the agreement document.

        Without accident insurance the TCE is **not** issued (art. 9, IV).
        """
        terms = payload.placement
        assert terms is not None
        previous = await self.store.agreements.find({"application_id": payload.application_id})
        version = len(previous) + 1
        agreement_id = f"tce-{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC)
        data = AgreementData(
            agreement_id=agreement_id,
            version=version,
            student_name=payload.student_name,
            student_course=terms.student_course,
            company_name=terms.company_name,
            internship_title=payload.internship_title,
            start_date=terms.start_date,
            end_date=terms.end_date,
            hours_per_day=terms.hours_per_day,
            hours_per_week=terms.hours_per_week,
            stipend=terms.stipend,
            insurer=terms.insurer,
            insurance_policy=terms.insurance_policy,
            supervisor_name=terms.supervisor_name,
            activities=terms.activities,
            is_pcd=terms.is_pcd,
            generated_at=now,
        )
        try:
            pdf = render_agreement_pdf(data)
        except MissingInsuranceError:
            logger.error(
                "TCE not generated: missing accident insurance",
                extra={"application_id": payload.application_id},
            )
            return None
        path = self.files.save(f"agreements/{agreement_id}.pdf", pdf)
        doc = {
            "_id": agreement_id,
            "application_id": payload.application_id,
            "internship_id": payload.internship_id,
            "student_id": payload.student_id,
            "company_id": payload.company_id,
            "student_name": payload.student_name,
            "company_name": terms.company_name,
            "internship_title": payload.internship_title,
            "student_course": terms.student_course,
            "terms": terms.model_dump(mode="json"),
            "version": version,
            "status": "pending_approval",
            "file_path": path,
            "size_bytes": len(pdf),
            "created_at": now,
            "approved_at": None,
            "approved_by": None,
        }
        await self.store.agreements.insert(doc)
        await self.publisher.publish(
            EventType.AGREEMENT_GENERATED,
            AgreementGenerated(
                agreement_id=agreement_id,
                application_id=payload.application_id,
                student_id=payload.student_id,
                company_id=payload.company_id,
                version=version,
                student_name=payload.student_name,
                company_name=terms.company_name,
                internship_title=payload.internship_title,
            ),
        )
        return doc
