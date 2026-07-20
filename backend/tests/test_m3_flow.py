import pytest
from sqlalchemy import select

from app.agent.contracts import AgentDecision, PlannedToolCall, ToolContext, ToolDefinition
from app.agent.registry import ToolRegistry
from app.models import AuditLog


def m3_registry(expense_ids: list[str]) -> ToolRegistry:
    registry = ToolRegistry()

    async def knowledge(context: ToolContext, arguments: dict) -> dict:
        return {
            "answer": "Supplies are reimbursed with a receipt [S1].",
            "citations": [{"label": "[S1]"}],
        }

    async def expense(context: ToolContext, arguments: dict) -> dict:
        expense_ids.append("EXP-fixed")
        return {"expense_id": "EXP-fixed", "status": "submitted", **arguments}

    registry.register(
        ToolDefinition(
            name="knowledge_search",
            description="Search policy",
            side_effect="read",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            handler=knowledge,
            impact=lambda args: "Read expense policy.",
        )
    )
    registry.register(
        ToolDefinition(
            name="submit_expense",
            description="Submit expense",
            side_effect="write",
            parameters={
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "currency": {"type": "string"},
                    "category": {"type": "string"},
                    "description": {"type": "string"},
                    "receipt_reference": {"type": "string"},
                },
                "required": ["amount", "currency", "category", "description", "receipt_reference"],
            },
            handler=expense,
            impact=lambda args: f"Submit {args['amount']} {args['currency']} expense.",
        )
    )
    return registry


@pytest.mark.asyncio
async def test_m3_http_flow_requires_confirmation_and_audits_execution(
    client, db_session, monkeypatch
):
    expense_ids: list[str] = []
    registry = m3_registry(expense_ids)
    decisions = iter(
        [
            AgentDecision(
                tool_call=PlannedToolCall(
                    "knowledge-1", "knowledge_search", {"query": "expense policy"}
                )
            ),
            AgentDecision(
                tool_call=PlannedToolCall(
                    "expense-1",
                    "submit_expense",
                    {
                        "amount": 300,
                        "currency": "CNY",
                        "category": "supplies",
                        "description": "Office supplies",
                        "receipt_reference": "R-100",
                    },
                )
            ),
            AgentDecision(
                final_answer="The policy allows supplies with a receipt [S1]. Submitted EXP-fixed."
            ),
        ]
    )

    async def planner(*args, **kwargs):
        return next(decisions)

    monkeypatch.setattr("app.api.v1.endpoints.chat.build_default_registry", lambda: registry)
    monkeypatch.setattr("app.agent.loop.plan_next_step", planner)
    registered = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "m3-flow",
            "email": "m3-flow@example.com",
            "password": "secret123",
        },
    )
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    conversation = await client.post("/api/v1/chat/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]

    pending = await client.post(
        f"/api/v1/chat/conversations/{conversation_id}/messages",
        json={"content": "Check policy then submit 300 CNY for supplies"},
        headers=headers,
    )
    assert pending.status_code == 201
    pending_call = pending.json()["tool_call"]
    assert pending.json()["status"] == "waiting_confirmation"
    assert pending_call["arguments"]["receipt_reference"] == "R-100"
    assert expense_ids == []

    activity = await client.get(
        f"/api/v1/chat/conversations/{conversation_id}/tool-calls", headers=headers
    )
    assert [call["tool_name"] for call in activity.json()] == ["knowledge_search", "submit_expense"]
    assert activity.json()[-1]["status"] == "pending_confirmation"

    confirmed = await client.post(
        f"/api/v1/chat/tool-calls/{pending_call['id']}/decision",
        json={"confirm": True},
        headers=headers,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["answer"] and "EXP-fixed" in confirmed.json()["answer"]
    assert expense_ids == ["EXP-fixed"]

    rows = (
        (await db_session.execute(select(AuditLog).order_by(AuditLog.created_at))).scalars().all()
    )
    assert {row.action_type for row in rows} >= {
        "tool_call_requested",
        "tool_call_confirmed",
        "tool_call_succeeded",
    }

    other = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "m3-other",
            "email": "m3-other@example.com",
            "password": "secret123",
        },
    )
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    denied_conversation = await client.post(
        "/api/v1/chat/conversations", json={}, headers=other_headers
    )
    denied_id = denied_conversation.json()["id"]
    decisions2 = iter(
        [
            AgentDecision(
                tool_call=PlannedToolCall(
                    "expense-2",
                    "submit_expense",
                    {
                        "amount": 1,
                        "currency": "CNY",
                        "category": "supplies",
                        "description": "x",
                        "receipt_reference": "R-2",
                    },
                )
            )
        ]
    )

    async def planner2(*args, **kwargs):
        return next(decisions2)

    monkeypatch.setattr("app.agent.loop.plan_next_step", planner2)
    pending2 = await client.post(
        f"/api/v1/chat/conversations/{denied_id}/messages",
        json={"content": "submit"},
        headers=other_headers,
    )
    call2 = pending2.json()["tool_call"]["id"]
    foreign = await client.post(
        f"/api/v1/chat/tool-calls/{call2}/decision",
        json={"confirm": True},
        headers=headers,
    )
    assert foreign.status_code == 404
    denied = await client.post(
        f"/api/v1/chat/tool-calls/{call2}/decision",
        json={"confirm": False},
        headers=other_headers,
    )
    assert denied.status_code == 200
    assert expense_ids == ["EXP-fixed"]
