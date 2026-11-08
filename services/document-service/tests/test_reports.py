from conftest import COMPANY, COORDINATOR, OTHER_STUDENT, PDF, STUDENT

FORM = {
    "application_id": "7",
    "title": "Relatório parcial 1",
    "period_start": "2026-12-01",
    "period_end": "2027-05-31",
}


async def upload(client, headers=STUDENT, form=None, content=PDF):
    return await client.post(
        "/reports",
        data=form or FORM,
        files={"file": ("relatorio.pdf", content, "application/pdf")},
        headers=headers,
    )


async def test_student_submits_report_and_event_is_published(client, publisher):
    response = await upload(client)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["company_id"] == 100
    assert body["versions"][0]["version"] == 1
    assert "path" not in body["versions"][0]
    event = publisher.of_type("report.submitted")[0]
    assert event.payload["application_id"] == 7
    assert event.payload["version"] == 1


async def test_upload_validations(client, applications):
    assert (await upload(client, content=b"not a pdf")).status_code == 422
    assert (await upload(client, content=b"%PDF" + b"0" * (5 * 1024 * 1024))).status_code == 413
    bad_period = {**FORM, "period_end": "2026-01-01"}
    assert (await upload(client, form=bad_period)).status_code == 422
    assert (await upload(client, form={**FORM, "application_id": "8"})).status_code == 404
    assert (await upload(client, headers=COMPANY)).status_code == 403
    applications.status = "agreement_pending"
    assert (await upload(client)).status_code == 409
    applications.down = True
    assert (await upload(client)).status_code == 503


async def test_versions_listing_download_and_review(client, publisher):
    report = (await upload(client)).json()
    url = f"/reports/{report['id']}"
    v2 = await client.post(
        f"{url}/versions",
        files={"file": ("v2.pdf", PDF + b"v2", "application/pdf")},
        headers=STUDENT,
    )
    assert [v["version"] for v in v2.json()["versions"]] == [1, 2]
    assert publisher.of_type("report.submitted")[-1].payload["version"] == 2
    old = await client.get(f"{url}/versions/1/file", headers=COORDINATOR)
    new = await client.get(f"{url}/versions/2/file", headers=COMPANY)
    assert old.content == PDF and new.content == PDF + b"v2"
    assert (await client.get(f"{url}/versions/3/file", headers=STUDENT)).status_code == 404
    assert len((await client.get("/reports?application_id=7", headers=COMPANY)).json()) == 1
    assert (await client.get("/reports", headers=OTHER_STUDENT)).json() == []
    assert (await client.get(url, headers=OTHER_STUDENT)).status_code == 403
    reviewed = await client.post(f"{url}/review", json={"comment": "Ótimo"}, headers=COORDINATOR)
    assert reviewed.json()["status"] == "reviewed"
    assert (await client.post(f"{url}/review", json={}, headers=STUDENT)).status_code == 403
    assert (
        await client.post("/reports/nope/review", json={}, headers=COORDINATOR)
    ).status_code == 404
