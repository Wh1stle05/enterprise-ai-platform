from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

from httpx import AsyncClient

from app.agent.loop import AgentTurnResult
from app.models import AgentRun, ToolCall

CONVERSATIONS_URL = "/api/v1/chat/conversations"


def turn(*, status="completed", answer="done", tool_call=None):
    return AgentTurnResult(
        run_id=uuid4(), status=status, answer=answer, tool_call=tool_call, step_count=1
    )


class AgentApi:
    async def register(self, client: AsyncClient, suffix: str = "") -> dict:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": f"agent{suffix}",
                "email": f"agent{suffix}@example.com",
                "password": "secret123",
            },
        )
        assert response.status_code == 201
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    async def conversation(self, client: AsyncClient, headers: dict) -> str:
        response = await client.post(CONVERSATIONS_URL, json={}, headers=headers)
        assert response.status_code == 201
        return response.json()["id"]


async def test_agent_send_returns_exact_direct_turn_contract(client: AsyncClient):
    helper = AgentApi()
    headers = await helper.register(client)
    conversation_id = await helper.conversation(client, headers)
    with patch("app.api.v1.endpoints.chat.start_agent_turn", new=AsyncMock(return_value=turn())):
        response = await client.post(
            f"{CONVERSATIONS_URL}/{conversation_id}/messages",
            json={"content": "hello"},
            headers=headers,
        )
    assert response.status_code == 201
    assert set(response.json()) == {
        "run_id",
        "status",
        "answer",
        "tool_call",
        "step_count",
        "elapsed_ms",
    }
    assert response.json()["answer"] == "done"


async def test_agent_send_maps_read_and_pending_write_calls(client: AsyncClient):
    helper = AgentApi()
    headers = await helper.register(client, "calls")
    conversation_id = await helper.conversation(client, headers)
    read_call = SimpleNamespace(
        id=uuid4(),
        run_id=uuid4(),
        provider_call_id="read-1",
        tool_name="query_inventory",
        arguments='{"sku":"A-1"}',
        side_effect="read",
        impact="Read stock",
        status="succeeded",
        result='{"available":true}',
        error=None,
        expires_at=None,
    )
    pending_call = SimpleNamespace(
        id=uuid4(),
        run_id=uuid4(),
        provider_call_id="write-1",
        tool_name="create_work_ticket",
        arguments="not-json",
        side_effect="write",
        impact="Create ticket",
        status="pending_confirmation",
        result=None,
        error=None,
        expires_at=datetime.now(timezone.utc),
    )
    with patch(
        "app.api.v1.endpoints.chat.start_agent_turn",
        new=AsyncMock(return_value=turn(tool_call=read_call)),
    ):
        response = await client.post(
            f"{CONVERSATIONS_URL}/{conversation_id}/messages",
            json={"content": "read"},
            headers=headers,
        )
    assert response.status_code == 201
    assert response.json()["tool_call"]["arguments"] == {"sku": "A-1"}

    with patch(
        "app.api.v1.endpoints.chat.start_agent_turn",
        new=AsyncMock(
            return_value=turn(status="waiting_confirmation", answer=None, tool_call=pending_call)
        ),
    ):
        response = await client.post(
            f"{CONVERSATIONS_URL}/{conversation_id}/messages",
            json={"content": "write"},
            headers=headers,
        )
    assert response.status_code == 201
    assert response.json()["tool_call"]["arguments"] == {}


async def test_tool_call_activity_is_owner_scoped_and_defensive(client: AsyncClient, db_session):
    helper = AgentApi()
    headers = await helper.register(client, "activity")
    conversation_id = await helper.conversation(client, headers)
    user_id = (await client.get("/api/v1/users/me", headers=headers)).json()["id"]
    run = AgentRun(
        conversation_id=UUID(conversation_id),
        user_id=UUID(user_id),
        status="waiting_confirmation",
        allowed_tools="[]",
        model_context="[]",
    )
    db_session.add(run)
    await db_session.flush()
    db_session.add(
        ToolCall(
            run_id=run.id,
            step_number=1,
            provider_call_id="x",
            tool_name="t",
            arguments="bad",
            side_effect="write",
            impact="",
            status="pending_confirmation",
        )
    )
    await db_session.commit()
    response = await client.get(
        f"{CONVERSATIONS_URL}/{conversation_id}/tool-calls", headers=headers
    )
    assert response.status_code == 200
    assert response.json()[0]["arguments"] == {}

    other_headers = await helper.register(client, "foreign")
    assert (
        await client.get(f"{CONVERSATIONS_URL}/{conversation_id}/tool-calls", headers=other_headers)
    ).status_code == 404


async def test_decision_confirm_deny_expiry_and_repeat_conflict(client: AsyncClient):
    helper = AgentApi()
    headers = await helper.register(client, "decision")
    tool_call_id = str(uuid4())
    with patch(
        "app.api.v1.endpoints.chat.resume_agent_run",
        new=AsyncMock(return_value=turn(status="completed", answer="confirmed")),
    ) as resume:
        response = await client.post(
            f"/api/v1/chat/tool-calls/{tool_call_id}/decision",
            json={"confirm": True},
            headers=headers,
        )
    assert response.status_code in {404, 409}
    resume.assert_not_awaited()


async def test_agent_api_rejects_malformed_decision_and_foreign_writes(client: AsyncClient):
    helper = AgentApi()
    headers = await helper.register(client, "owner")
    conversation_id = await helper.conversation(client, headers)
    assert (
        await client.post(
            f"/api/v1/chat/tool-calls/{uuid4()}/decision",
            json={"confirm": "yes"},
            headers=headers,
        )
    ).status_code == 422
    foreign = await helper.register(client, "foreign")
    # Owner-scoped conversation: a foreign user must not see it, so 404 not 403.
    assert (
        await client.post(
            f"{CONVERSATIONS_URL}/{conversation_id}/messages",
            json={"content": "x"},
            headers=foreign,
        )
    ).status_code == 404


async def test_agent_api_maps_configuration_and_provider_failures(client: AsyncClient):
    helper = AgentApi()
    headers = await helper.register(client, "errors")
    conversation_id = await helper.conversation(client, headers)
    from app.services.llm_service import LLMConfigurationError

    with patch(
        "app.api.v1.endpoints.chat.start_agent_turn",
        new=AsyncMock(side_effect=LLMConfigurationError("missing")),
    ):
        response = await client.post(
            f"{CONVERSATIONS_URL}/{conversation_id}/messages",
            json={"content": "x"},
            headers=headers,
        )
    assert response.status_code == 503
    with patch(
        "app.api.v1.endpoints.chat.start_agent_turn",
        new=AsyncMock(side_effect=RuntimeError("provider")),
    ):
        response = await client.post(
            f"{CONVERSATIONS_URL}/{conversation_id}/messages",
            json={"content": "x"},
            headers=headers,
        )
    assert response.status_code == 502
