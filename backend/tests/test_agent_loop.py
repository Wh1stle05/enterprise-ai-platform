import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.agent.contracts import AgentDecision, PlannedToolCall, ToolContext, ToolDefinition
from app.agent.loop import resume_agent_run, start_agent_turn
from app.agent.registry import ToolRegistry
from app.models import Conversation, User

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def registry(*, write=False):
    tools = ToolRegistry()

    async def handler(context: ToolContext, arguments: dict):
        if arguments.get("sku") == "FAIL":
            raise RuntimeError("handler exploded")
        return {"sku": arguments.get("sku", "LAPTOP-14"), "quantity": 7}

    tools.register(
        ToolDefinition(
            name="knowledge_search",
            description="Search knowledge.",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            side_effect="read",
            handler=handler,
            impact=lambda args: "search",
        )
    )
    tools.register(
        ToolDefinition(
            name="query_inventory",
            description="Query inventory.",
            parameters={
                "type": "object",
                "properties": {"sku": {"type": "string"}},
                "required": ["sku"],
            },
            side_effect="read",
            handler=handler,
            impact=lambda args: "inventory",
        )
    )
    if write:
        tools.register(
            ToolDefinition(
                name="write_item",
                description="Write item.",
                parameters={
                    "type": "object",
                    "properties": {"sku": {"type": "string"}},
                    "required": ["sku"],
                },
                side_effect="write",
                handler=handler,
                impact=lambda args: "write",
            )
        )
    return tools


async def make_conversation(db_session):
    user = User(
        id=uuid4(),
        username=f"u-{uuid4().hex[:8]}",
        email=f"{uuid4().hex[:8]}@example.com",
        hashed_password="hash",
    )
    conversation = Conversation(id=uuid4(), user_id=user.id, title="test")
    db_session.add_all([user, conversation])
    await db_session.flush()
    return user, conversation


@pytest.mark.asyncio
async def test_direct_answer_completes(db_session, monkeypatch):
    user, conversation = await make_conversation(db_session)
    monkeypatch.setattr("app.agent.loop.plan_next_step", lambda *args, **kwargs: _decision("done"))
    result = await start_agent_turn(
        db_session, registry(), conversation.id, user.id, "hello", now=NOW
    )
    assert result.status == "completed"
    assert result.answer == "done"


async def _decision(answer):
    return AgentDecision(final_answer=answer)


@pytest.mark.asyncio
async def test_knowledge_then_inventory_then_answer_preserves_observations(db_session, monkeypatch):
    user, conversation = await make_conversation(db_session)
    decisions = iter(
        [
            AgentDecision(tool_call=PlannedToolCall("k1", "knowledge_search", {"query": "policy"})),
            AgentDecision(tool_call=PlannedToolCall("i1", "query_inventory", {"sku": "LAPTOP-14"})),
            AgentDecision(final_answer="7 available"),
        ]
    )

    async def planner(*args, **kwargs):
        return next(decisions)

    monkeypatch.setattr("app.agent.loop.plan_next_step", planner)
    result = await start_agent_turn(
        db_session, registry(), conversation.id, user.id, "check stock", now=NOW
    )
    assert result.answer == "7 available"
    context = json.loads(result.model_context)
    assert context[1]["role"] == "assistant"
    assert context[1]["tool_calls"][0]["id"] == "k1"
    assert context[2] == {
        "role": "tool",
        "tool_call_id": "k1",
        "content": '{"quantity": 7, "sku": "LAPTOP-14"}',
    }
    assert context[3]["tool_calls"][0]["id"] == "i1"


@pytest.mark.asyncio
async def test_write_waits_then_resume_confirmation_executes(db_session, monkeypatch):
    user, conversation = await make_conversation(db_session)
    monkeypatch.setattr("app.core.config.settings.AGENT_TOOL_WHITELIST", ["write_item"])
    monkeypatch.setattr(
        "app.agent.loop.plan_next_step",
        lambda *args, **kwargs: AgentDecision(
            tool_call=PlannedToolCall("w1", "write_item", {"sku": "A"})
        ),
    )
    paused = await start_agent_turn(
        db_session, registry(write=True), conversation.id, user.id, "write", now=NOW
    )
    assert paused.status == "waiting_confirmation"
    assert paused.tool_call.status == "pending_confirmation"
    monkeypatch.setattr(
        "app.agent.loop.plan_next_step", lambda *args, **kwargs: _decision("written")
    )
    resumed = await resume_agent_run(
        db_session, registry(write=True), paused.run_id, user.id, confirm=True, now=NOW
    )
    assert resumed.status == "completed"
    assert resumed.answer == "written"


@pytest.mark.asyncio
async def test_write_denial_and_expiry_are_observed_and_stop_without_execution(
    db_session, monkeypatch
):
    user, conversation = await make_conversation(db_session)
    monkeypatch.setattr("app.core.config.settings.AGENT_TOOL_WHITELIST", ["write_item"])
    monkeypatch.setattr(
        "app.agent.loop.plan_next_step",
        lambda *args, **kwargs: AgentDecision(
            tool_call=PlannedToolCall("w1", "write_item", {"sku": "A"})
        ),
    )
    paused = await start_agent_turn(
        db_session, registry(write=True), conversation.id, user.id, "write", now=NOW
    )
    denied = await resume_agent_run(
        db_session, registry(write=True), paused.run_id, user.id, confirm=False, now=NOW
    )
    assert denied.status == "completed"
    assert "denied" in denied.answer.lower()

    paused = await start_agent_turn(
        db_session, registry(write=True), conversation.id, user.id, "write again", now=NOW
    )
    expired = await resume_agent_run(
        db_session,
        registry(write=True),
        paused.run_id,
        user.id,
        confirm=True,
        now=NOW + timedelta(minutes=10),
    )
    assert expired.status == "completed"
    assert "expired" in expired.answer.lower()


@pytest.mark.asyncio
async def test_validation_and_handler_feedback_are_returned_to_planner(db_session, monkeypatch):
    user, conversation = await make_conversation(db_session)
    decisions = iter(
        [
            AgentDecision(tool_call=PlannedToolCall("bad", "query_inventory", {})),
            AgentDecision(tool_call=PlannedToolCall("failed", "query_inventory", {"sku": "FAIL"})),
            AgentDecision(tool_call=PlannedToolCall("good", "query_inventory", {"sku": "A"})),
            AgentDecision(final_answer="recovered"),
        ]
    )

    async def planner(messages, *args, **kwargs):
        if len(messages) > 2:
            feedback = " ".join(message.get("content", "") for message in messages)
            assert (
                "invalid tool arguments" in feedback.lower()
                or "handler exploded" in feedback.lower()
            )
        return next(decisions)

    monkeypatch.setattr("app.agent.loop.plan_next_step", planner)
    result = await start_agent_turn(
        db_session, registry(), conversation.id, user.id, "recover", now=NOW
    )
    assert result.answer == "recovered"


@pytest.mark.asyncio
async def test_max_steps_and_time_are_bounded(db_session, monkeypatch):
    user, conversation = await make_conversation(db_session)
    monkeypatch.setattr(
        "app.agent.loop.plan_next_step",
        lambda *args, **kwargs: AgentDecision(
            tool_call=PlannedToolCall("x", "query_inventory", {"sku": "A"})
        ),
    )
    result = await start_agent_turn(
        db_session, registry(), conversation.id, user.id, "loop", now=NOW, max_steps=1
    )
    assert result.status == "limit_reached"
    assert result.step_count == 1
    result = await start_agent_turn(
        db_session, registry(), conversation.id, user.id, "slow", now=NOW, max_active_seconds=0
    )
    assert result.status == "limit_reached"


@pytest.mark.asyncio
async def test_whitelist_rejects_unavailable_tool_with_feedback(db_session, monkeypatch):
    user, conversation = await make_conversation(db_session)
    monkeypatch.setattr(
        "app.agent.loop.plan_next_step",
        lambda *args, **kwargs: AgentDecision(tool_call=PlannedToolCall("x", "blocked", {})),
    )
    result = await start_agent_turn(
        db_session,
        registry(),
        conversation.id,
        user.id,
        "blocked",
        allowed_tools={"query_inventory"},
        now=NOW,
    )
    assert result.status == "failed"
    assert "not allowed" in result.answer.lower()
