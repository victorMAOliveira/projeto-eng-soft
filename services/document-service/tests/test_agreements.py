from datetime import UTC, date, datetime

import pytest
from conftest import COMPANY, COORDINATOR, OTHER_COMPANY, OTHER_STUDENT, STUDENT, approved_payload
from document_service.pdf import (
    AgreementData,
    MissingInsuranceError,
    render_agreement_pdf,
    render_preview_png,
)
from document_service.storage import FileStorage, InMemoryCollection, MongoIdempotencyStore

from eh_events import EventType, make_event


def data(**overrides) -> AgreementData:
    values = dict(
        agreement_id="tce-1",
        version=1,
        student_name="Ana Souza",
        student_course="Ciência da Computação",
        company_name="ACME",
        internship_title="Estágio Backend",
        start_date=date(2026, 12, 1),
        end_date=date(2027, 11, 30),
        hours_per_day=6,
        hours_per_week=30,
        stipend=1500.0,
        insurer="Seguradora Exemplo",
        insurance_policy="AP-1",
        supervisor_name="Carla",
        activities="",
        is_pcd=True,
        generated_at=datetime.now(UTC),
    )
    values.update(overrides)
    return AgreementData(**values)


def test_pdf_and_preview_rendering():
    pdf = render_agreement_pdf(data())
    assert pdf.startswith(b"%PDF")
    png = render_preview_png(pdf, scale=0.5)
    assert png.startswith(b"\x89PNG")


@pytest.mark.parametrize("missing", [{"insurer": None}, {"insurance_policy": " "}])
def test_tce_requires_accident_insurance(missing):
    with pytest.raises(MissingInsuranceError):
        render_agreement_pdf(data(**missing))


async def test_generator_reacts_only_to_approval(app, store, publisher):
    generator = app.state.generator
    approved = make_event(
        EventType.APPLICATION_STATUS_CHANGED, approved_payload(), producer="application-service"
    )
    await generator(approved)
    other = approved_payload()
    other.to_status = "under_review"
    await generator(make_event(EventType.APPLICATION_STATUS_CHANGED, other, producer="x"))
    await generator(
        make_event("internship.closed", {"internship_id": 1, "company_id": 1}, producer="x")
    )
    docs = await store.agreements.find({})
    assert len(docs) == 1
    assert docs[0]["status"] == "pending_approval"
    event = publisher.of_type("agreement.generated")[0]
    assert event.payload["application_id"] == 7
    assert event.payload["student_name"] == "Ana Souza"


async def test_regeneration_increments_version_and_missing_insurance_is_blocked(app, publisher):
    first = await app.state.generator.generate(approved_payload())
    second = await app.state.generator.generate(approved_payload())
    assert (first["version"], second["version"]) == (1, 2)
    blocked = await app.state.generator.generate(approved_payload(insurance_policy=None))
    assert blocked is None
    assert len(publisher.of_type("agreement.generated")) == 2


async def test_agreement_endpoints_and_scope(client, agreement):
    agreement_id = agreement["_id"]
    listed = (await client.get("/agreements", headers=STUDENT)).json()
    assert [a["id"] for a in listed] == [agreement_id]
    assert "file_path" not in listed[0]
    assert (await client.get("/agreements", headers=OTHER_STUDENT)).json() == []
    pending = await client.get(
        "/agreements?status=pending_approval&application_id=7", headers=COORDINATOR
    )
    assert len(pending.json()) == 1
    assert (await client.get(f"/agreements/{agreement_id}", headers=COMPANY)).status_code == 200
    assert (
        await client.get(f"/agreements/{agreement_id}", headers=OTHER_COMPANY)
    ).status_code == 403
    assert (await client.get("/agreements/nope", headers=COORDINATOR)).status_code == 404
    pdf = await client.get(f"/agreements/{agreement_id}/pdf", headers=STUDENT)
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    preview = await client.get(f"/agreements/{agreement_id}/preview.png", headers=COMPANY)
    assert preview.content.startswith(b"\x89PNG")


async def test_coordinator_approval_publishes_event(client, agreement, publisher):
    url = f"/agreements/{agreement['_id']}/approve"
    assert (await client.post(url, headers=COMPANY)).status_code == 403
    approved = await client.post(url, headers=COORDINATOR)
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by"] == 300
    event = publisher.of_type("agreement.approved")[0]
    assert event.payload["application_id"] == 7
    assert (await client.post(url, headers=COORDINATOR)).status_code == 409
    assert (await client.post("/agreements/nope/approve", headers=COORDINATOR)).status_code == 404


async def test_mongo_idempotency_store_and_collection_semantics():
    store = MongoIdempotencyStore(InMemoryCollection())
    assert not await store.seen("e1")
    await store.mark("e1", "x")
    await store.mark("e1", "x")
    assert await store.seen("e1")


def test_file_storage_blocks_path_traversal(tmp_path):
    files = FileStorage(tmp_path)
    files.save("a/b.pdf", b"x")
    assert files.read("a/b.pdf") == b"x"
    with pytest.raises(ValueError):
        files.read("../escape.pdf")
