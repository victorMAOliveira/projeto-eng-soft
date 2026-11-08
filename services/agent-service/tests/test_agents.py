import asyncio
from types import SimpleNamespace

import httpx
from agent_service.agents import AGENTS
from agent_service.tools import MUTATING_TOOLS, TOOLS
from conftest import COMPANY, COORDINATOR, STUDENT, ScriptedLlm, block, make_app


def test_guardrails_tools_never_change_application_status():
    forbidden = ("approve", "reject", "withdraw", "transition", "status", "terminate", "complete")
    for name in TOOLS:
        assert not any(word in name for word in forbidden)
    assert {"send_notification", "check_deadlines"} == MUTATING_TOOLS
    assert AGENTS["screening"].tools == ("get_candidate_ranking",)
    assert set(AGENTS["application_assistant"].tools) == {
        "search_internships",
        "get_recommendations",
        "get_profile",
    }
    for spec in AGENTS.values():
        assert "nunca altera o status" in spec.system_prompt
        for name in spec.tools:
            schema = TOOLS[name].to_anthropic()["input_schema"]
            assert schema["additionalProperties"] is False


async def test_assistant_rules_mode_with_trail(client):
    status = (await client.get("/agents/status", headers=STUDENT)).json()
    assert status["mode"] == "rules"
    assert status["model"] == "claude-haiku-5-5"
    run = (await client.post("/agents/application-assistant/run", json={}, headers=STUDENT)).json()
    assert run["mode"] == "rules" and run["status"] == "completed"
    assert "Estágio Backend" in run["output"]
    assert "Docker" in run["output"]  # missing skill tip
    assert "Prezada equipe da ACME" in run["cover_letter"]
    tools = [s["tool_name"] for s in run["steps"] if s["kind"] == "tool_call"]
    assert tools == ["get_profile", "get_recommendations"]
    assert run["steps"][-1]["kind"] == "final"
    detail = (await client.get(f"/agents/runs/{run['id']}", headers=STUDENT)).json()
    assert detail["steps"] == run["steps"]
    explicit = (
        await client.post(
            "/agents/application-assistant/run", json={"internship_id": 11}, headers=STUDENT
        )
    ).json()
    assert "não passa nos filtros" in explicit["output"]


async def test_assistant_degrades_when_recommendation_service_is_down(client, platform):
    platform.down.add("recommendation-service")
    run = (
        await client.post(
            "/agents/application-assistant/run", json={"question": "python"}, headers=STUDENT
        )
    ).json()
    assert run["status"] == "completed"
    assert "indisponível" in run["output"]
    failed = [s for s in run["steps"] if not s["ok"]]
    assert failed[0]["tool_name"] == "get_recommendations"
    assert run["cover_letter"] is None


async def test_screening_rules_mode(client):
    run = (
        await client.post("/agents/screening/run", json={"internship_id": 10}, headers=COMPANY)
    ).json()
    assert "1. Ana — score 80%" in run["output"]
    assert "Davi: não atende" in run["output"]
    assert "decisão" in run["output"]
    assert (
        await client.post("/agents/screening/run", json={"internship_id": 10}, headers=STUDENT)
    ).status_code == 403


async def test_screening_failure_is_recorded(client, platform):
    platform.down.add("recommendation-service")
    run = (
        await client.post("/agents/screening/run", json={"internship_id": 10}, headers=COMPANY)
    ).json()
    assert run["status"] == "failed"
    assert "indisponível" in run["error"]


async def test_follow_up_publishes_due_soon_once_and_notifies(client, platform, publisher):
    first = (await client.post("/agents/follow-up/run", headers=COORDINATOR)).json()
    assert "3 estágio(s) ativo(s)" in first["output"]
    events = publisher.of_type("report.due_soon")
    assert sorted(e.payload["application_id"] for e in events) == [1, 2]
    assert any(e.payload["overdue"] for e in events)
    assert "limite de 2 anos" in first["output"] and "jornada acima" in first["output"]
    assert platform.notifications[0]["role"] == "coordinator"
    second = (await client.post("/agents/follow-up/run", headers=COORDINATOR)).json()
    assert len(publisher.of_type("report.due_soon")) == 2  # deduplicated
    assert "já alertado" in second["output"]
    runs = (await client.get("/agents/runs?agent=follow_up", headers=COORDINATOR)).json()
    assert len(runs) == 2
    assert (await client.get("/agents/runs", headers=STUDENT)).json() == []
    assert (await client.get(f"/agents/runs/{runs[0]['id']}", headers=STUDENT)).status_code == 403
    assert (await client.get("/agents/runs/999", headers=COORDINATOR)).status_code == 404


async def test_scheduled_follow_up_runs_as_service(db, publisher, platform):
    app = make_app(db, publisher, platform)
    await app.state.scheduled_follow_up()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://a") as c:
        runs = (await c.get("/agents/runs", headers=COORDINATOR)).json()
    assert runs[0]["input"] == {"trigger": "scheduled"}
    assert runs[0]["user_id"] == 0


async def test_llm_mode_tool_loop_with_mocked_client(db, publisher, platform):
    llm = ScriptedLlm(
        [
            SimpleNamespace(
                stop_reason="tool_use",
                content=[
                    block("thinking", thinking=""),
                    block("tool_use", id="t1", name="get_recommendations", input={"k": 3}),
                    block(
                        "tool_use",
                        id="t2",
                        name="send_notification",
                        input={"title": "x", "message": "y"},
                    ),
                ],
            ),
            SimpleNamespace(
                stop_reason="end_turn",
                content=[
                    block(
                        "text",
                        text="A vaga combina porque você domina Python.\n<carta>Prezada ACME, ...</carta>",
                    ),
                ],
            ),
        ]
    )
    app = make_app(db, publisher, platform, llm=llm)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://a") as c:
        assert (await c.get("/agents/status", headers=STUDENT)).json()["mode"] == "llm"
        run = (
            await c.post(
                "/agents/application-assistant/run", json={"internship_id": 10}, headers=STUDENT
            )
        ).json()
    assert run["mode"] == "llm" and run["model"] == "claude-haiku-5-5"
    assert run["output"] == "A vaga combina porque você domina Python."
    assert run["cover_letter"] == "Prezada ACME, ..."
    kinds = [(s["kind"], s["tool_name"], s["ok"]) for s in run["steps"]]
    assert kinds[:4] == [
        ("llm", None, True),
        ("tool_call", "get_recommendations", True),
        ("tool_call", "send_notification", False),
        ("llm", None, True),
    ]
    first, second = llm.requests
    assert first["model"] == "claude-haiku-5-5"
    assert {t["name"] for t in first["tools"]} == {
        "search_internships",
        "get_recommendations",
        "get_profile",
    }
    assert "temperature" not in first
    tool_results = second["messages"][-1]["content"]
    assert tool_results[1]["is_error"] is True  # not allowed for this agent
    assert platform.notifications == []


async def test_llm_failures_fall_back_to_rules(db, publisher, platform):
    refusal = SimpleNamespace(stop_reason="refusal", content=[])
    for llm, expected in (
        (ScriptedLlm([refusal]), "recusou"),
        (ScriptedLlm([]), "limite de 6 passos"),  # never stops calling tools
    ):
        app = make_app(db, publisher, platform, llm=llm)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://a"
        ) as c:
            run = (
                await c.post("/agents/screening/run", json={"internship_id": 10}, headers=COMPANY)
            ).json()
        assert run["mode"] == "rules"
        assert expected in run["error"]
        assert "1. Ana" in run["output"]


async def test_llm_timeout_falls_back_to_rules(db, publisher, platform):
    class SlowLlm:
        async def create(self, **kwargs):
            await asyncio.sleep(1)

    app = make_app(db, publisher, platform, llm=SlowLlm(), agent_timeout_seconds=0.05)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://a") as c:
        run = (await c.post("/agents/follow-up/run", headers=COORDINATOR)).json()
    assert run["mode"] == "rules"
    assert "TimeoutError" in run["error"]


async def test_reports_tool_and_unknown_tool(db, publisher, platform):
    llm = ScriptedLlm(
        [
            SimpleNamespace(
                stop_reason="tool_use",
                content=[
                    block("tool_use", id="a", name="list_reports", input={"application_id": 1})
                ],
            ),
            SimpleNamespace(stop_reason="end_turn", content=[block("text", text="Tudo em dia.")]),
        ]
    )
    app = make_app(db, publisher, platform, llm=llm)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://a") as c:
        run = (await c.post("/agents/follow-up/run", headers=COORDINATOR)).json()
    assert run["output"] == "Tudo em dia."
    assert run["steps"][1]["tool_output"][0]["id"] == "r1"
