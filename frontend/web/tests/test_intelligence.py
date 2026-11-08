from conftest import login_as

REC = {
    "internship_id": 10,
    "title": "Estágio Backend",
    "company_name": "ACME",
    "course": "CC",
    "modality": "hybrid",
    "city": "Maceió",
    "stipend": 1500.0,
    "hours_per_week": 30,
    "requirements": ["Python", "SQL", "Docker"],
    "score": 0.71,
    "components": {"cosine": 0.4, "jaccard": 0.5, "preference": 1.0},
    "matched_skills": ["Python", "SQL"],
    "missing_skills": ["Docker"],
    "reasons": [],
    "eliminated_by": [],
    "explanation": "Você tem 2 de 3 habilidades exigidas.",
    "strategy": "hybrid",
}
RECS = {
    "student_id": 1,
    "strategy": "hybrid",
    "weights": {"content": 0.5, "attributes": 0.35, "preference": 0.15},
    "items": [REC],
    "filtered": [
        {
            **REC,
            "internship_id": 11,
            "title": "Estágio Design",
            "eliminated_by": ["Curso incompatível."],
        }
    ],
    "filtered_count": 1,
    "already_applied": [],
}
RUN = {
    "id": 4,
    "agent": "application_assistant",
    "title": "Assistente de Candidatura",
    "user_id": 1,
    "mode": "rules",
    "model": None,
    "status": "completed",
    "input": {},
    "output": "POR QUE...",
    "cover_letter": "Prezada equipe da ACME",
    "error": None,
    "steps_count": 2,
    "started_at": "2026-11-08T12:00:00Z",
    "finished_at": "2026-11-08T12:00:01Z",
    "steps": [
        {
            "position": 1,
            "kind": "tool_call",
            "tool_name": "get_profile",
            "tool_input": {},
            "tool_output": {"name": "Ana"},
            "ok": True,
            "duration_ms": 3.2,
        },
        {
            "position": 2,
            "kind": "tool_call",
            "tool_name": "get_recommendations",
            "tool_input": {"k": 5},
            "tool_output": {"error": "x"},
            "ok": False,
            "duration_ms": 1.0,
        },
        {
            "position": 3,
            "kind": "final",
            "tool_name": None,
            "tool_input": None,
            "tool_output": {"status": "completed"},
            "ok": True,
            "duration_ms": 0,
        },
    ],
}
STATUS = {
    "mode": "rules",
    "model": "claude-haiku-5-5",
    "max_steps": 6,
    "timeout_seconds": 45,
    "agents": {},
    "follow_up_schedule": {"interval_minutes": 60, "next_run": "2026-11-08T13:00:00+00:00"},
}


async def test_recommendations_page_shows_explanations(client, gw):
    gw.add(
        "GET", "/api/recommendations/students/1/internships", RECS, service="recommendation-service"
    )
    login_as(client)
    page = await client.get("/recomendacoes")
    assert "Estágio Backend" in page.text
    assert "✓ Python" in page.text and "✗ Docker" in page.text
    assert "Curso incompatível" in page.text
    assert 'data-service="recommendation-service"' in page.text
    gw.add("GET", "/api/recommendations/students/1/internships", {**RECS, "strategy": "cold_start"})
    assert "Cold start" in (await client.get("/recomendacoes")).text


async def test_recommendations_degrade_gracefully(client, gw):
    gw.add(
        "GET",
        "/api/recommendations/students/1/internships",
        {"detail": "x", "service": "recommendation-service"},
        status=503,
    )
    login_as(client)
    page = await client.get("/recomendacoes")
    assert page.status_code == 200
    assert "Degradação graciosa" in page.text


async def test_student_assistant_page_and_htmx_run(client, gw):
    gw.add("GET", "/api/agents/status", STATUS, service="agent-service")
    gw.add("GET", "/api/agents/runs", [RUN], service="agent-service")
    gw.add("GET", "/api/agents/runs/4", RUN, service="agent-service")
    gw.add("GET", "/api/recommendations/students/1/internships", RECS)
    gw.add("POST", "/api/agents/application-assistant/run", RUN, service="agent-service")
    login_as(client)
    page = await client.get("/assistente?internship_id=10")
    assert "IA em modo regras" in page.text
    assert 'value="10" selected' in page.text
    detail = await client.get("/assistente?run_id=4")
    assert "Trilha de execução" in detail.text and "get_recommendations" in detail.text
    partial = await client.post(
        "/assistente/executar",
        data={"internship_id": "10", "question": "o que estudar?"},
        headers={"HX-Request": "true"},
    )
    assert "<html" not in partial.text and "Prezada equipe da ACME" in partial.text
    assert b'"internship_id":10' in gw.calls[-1].content
    full = await client.post("/assistente/executar", data={})
    assert "<html" in full.text


async def test_company_screening_and_coordinator_follow_up(client, gw):
    gw.add("GET", "/api/agents/status", {**STATUS, "mode": "llm"}, service="agent-service")
    gw.add("GET", "/api/agents/runs", [], service="agent-service")
    gw.add("GET", "/api/internships/mine", [{"id": 10, "title": "Estágio Backend"}])
    gw.add(
        "POST",
        "/api/agents/screening/run",
        {
            **RUN,
            "agent": "screening",
            "title": "Agente de Triagem",
            "mode": "llm",
            "model": "claude-haiku-5-5",
            "cover_letter": None,
        },
    )
    gw.add(
        "POST", "/api/agents/follow-up/run", {"detail": "x", "service": "agent-service"}, status=503
    )
    login_as(client, "company", 5, "ACME")
    page = await client.get("/assistente")
    assert "IA: claude-haiku-5-5" in page.text
    run = await client.post(
        "/assistente/executar", data={"internship_id": "10"}, headers={"HX-Request": "true"}
    )
    assert "Agente de Triagem" in run.text
    login_as(client, "coordinator", 9)
    assert "report.due_soon" in (await client.get("/assistente")).text
    failed = await client.post("/assistente/executar", data={}, headers={"HX-Request": "true"})
    assert "Agentes indisponíveis" in failed.text


async def test_assistant_page_when_agent_service_is_down(client, gw):
    gw.add("GET", "/api/agents/status", {"detail": "x", "service": "agent-service"}, status=503)
    gw.add("GET", "/api/agents/runs", {"detail": "x"}, status=503)
    gw.add("GET", "/api/recommendations/students/1/internships", RECS)
    login_as(client)
    page = await client.get("/assistente")
    assert "agent-service está indisponível" in page.text


async def test_candidates_page_with_ranking(client, gw):
    gw.add("GET", "/api/internships/3", {"id": 3, "title": "Estágio Backend"})
    gw.add("GET", "/api/applications", [])
    gw.add(
        "GET",
        "/api/recommendations/internships/3/candidates",
        {
            "internship_id": 3,
            "title": "Estágio Backend",
            "scope": "applicants",
            "requirements": ["Python"],
            "items": [
                {
                    "student_id": 1,
                    "name": "Ana Souza",
                    "course": "CC",
                    "semester": 5,
                    "skills": ["Python"],
                    "application_id": 7,
                    "application_status": "submitted",
                    "score": 0.8,
                    "components": {},
                    "matched_skills": ["Python"],
                    "missing_skills": [],
                    "reasons": [],
                    "eliminated_by": [],
                    "explanation": "Atende 1 de 1 requisitos.",
                    "strategy": "hybrid",
                }
            ],
        },
        service="recommendation-service",
    )
    login_as(client, "company", 5, "ACME")
    page = await client.get("/vagas/3/candidatos")
    assert "Ranking de candidatos" in page.text and "Atende 1 de 1" in page.text
    assert "Triagem com IA" in page.text
