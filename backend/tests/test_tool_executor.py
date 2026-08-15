import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.agent.contracts import PlannedToolCall, ToolContext, ToolDefinition
from app.agent.executor import decide_tool_call, propose_or_execute
from app.agent.registry import ToolRegistry
from app.models import AgentRun, AuditLog, Conversation, User

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def build_registry(calls: list[dict]) -> ToolRegistry:
    async def handler(context: ToolContext, arguments: dict) -> dict:
        calls.append(arguments)
        return {"ok": True, "arguments": arguments}

    async def failing_handler(context: ToolContext, arguments: dict) -> dict:
        calls.append(arguments)
        raise RuntimeError("handler exploded")

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="read_item",
            description="Read an item.",
            parameters={
                "type": "object",
                "properties": {"item": {"type": "string"}, "token": {"type": "string"}},
                "required": ["item"],
                "additionalProperties": False,
            },
            side_effect="read",
            handler=handler,
            impact=lambda args: f"Read item {args['item']}.",
        )
    )
    registry.register(
        ToolDefinition(
            name="write_item",
            description="Write an item.",
            parameters={
                "type": "object",
                "properties": {"item": {"type": "string"}, "token": {"type": "string"}},
                "required": ["item"],
                "additionalProperties": False,
            },
            side_effect="write",
            handler=handler,
            impact=lambda args: f"Write item {args['item']}.",
        )
    )
    registry.register(
        ToolDefinition(
            name="fail_item",
            description="Fail an item.",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            side_effect="write",
            handler=failing_handler,
            impact=lambda args: "Fail an item.",
        )
    )
    return registry


async def make_run(db_session, *, allowed_tools=("read_item", "write_item", "fail_item")):
    user = User(
        id=uuid4(),
        username=f"u-{uuid4().hex[:8]}",
        email=f"{uuid4().hex[:8]}@example.com",
        hashed_password="hash",
    )
    conversation = Conversation(id=uuid4(), user_id=user.id, title="test")
    run = AgentRun(
        id=uuid4(),
        conversation_id=conversation.id,
        user_id=user.id,
        allowed_tools=json.dumps(list(allowed_tools)),
        status="running",
    )
    db_session.add_all([user, conversation, run])
    await db_session.flush()
    return user, run


async def audit_events(db_session):
    rows = (await db_session.execute(select(AuditLog).order_by(AuditLog.created_at))).scalars()
    return list(rows)


@pytest.mark.asyncio
async def test_immediate_read_executes_with_exact_arguments_and_audit(db_session):
    calls = []
    registry = build_registry(calls)
    user, run = await make_run(db_session)
    arguments = {"item": "A-1", "token": "secret-value"}

    call = await propose_or_execute(
        db_session,
        registry,
        run_id=run.id,
        user_id=user.id,
        planned_call=PlannedToolCall("provider-1", "read_item", arguments),
        step_number=3,
        now=NOW,
    )

    assert call.status == "succeeded"
    assert calls == [arguments]
    assert json.loads(call.arguments) == arguments
    events = await audit_events(db_session)
    assert [event.action_type for event in events] == ["tool_call_requested", "tool_call_succeeded"]
    assert "secret-value" not in (events[0].input or "")
    assert '"token": "[REDACTED]"' in (events[0].input or "")


@pytest.mark.asyncio
async def test_write_pauses_without_handler_and_persists_exact_impact_and_expiry(db_session):
    calls = []
    registry = build_registry(calls)
    user, run = await make_run(db_session)
    arguments = {"item": "A-1"}

    call = await propose_or_execute(
        db_session,
        registry,
        run_id=run.id,
        user_id=user.id,
        planned_call=PlannedToolCall("provider-2", "write_item", arguments),
        step_number=4,
        now=NOW,
        confirmation_ttl=timedelta(minutes=5),
    )

    assert call.status == "pending_confirmation"
    assert calls == []
    assert call.side_effect == "write"
    assert call.impact == "Write item A-1."
    assert call.expires_at == NOW + timedelta(minutes=5)
    assert run.status == "waiting_confirmation"


@pytest.mark.asyncio
async def test_whitelist_and_validation_errors_are_rejected(db_session):
    registry = build_registry([])
    user, run = await make_run(db_session, allowed_tools=("read_item",))

    with pytest.raises(HTTPException) as unknown:
        await propose_or_execute(
            db_session,
            registry,
            run_id=run.id,
            user_id=user.id,
            planned_call=PlannedToolCall("x", "write_item", {"item": "A"}),
            now=NOW,
        )
    assert unknown.value.status_code == 403

    with pytest.raises(HTTPException) as invalid:
        await propose_or_execute(
            db_session,
            registry,
            run_id=run.id,
            user_id=user.id,
            planned_call=PlannedToolCall("x", "read_item", {"extra": True}),
            now=NOW,
        )
    assert invalid.value.status_code == 422


@pytest.mark.asyncio
async def test_owner_foreign_ids_are_404(db_session):
    registry = build_registry([])
    user, run = await make_run(db_session)
    other = uuid4()

    with pytest.raises(HTTPException) as error:
        await propose_or_execute(
            db_session,
            registry,
            run_id=run.id,
            user_id=other,
            planned_call=PlannedToolCall("x", "read_item", {"item": "A"}),
            now=NOW,
        )
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_confirm_claims_exactly_once_and_repeat_is_conflict(db_session):
    calls = []
    registry = build_registry(calls)
    user, run = await make_run(db_session)
    pending = await propose_or_execute(
        db_session,
        registry,
        run_id=run.id,
        user_id=user.id,
        planned_call=PlannedToolCall("x", "write_item", {"item": "A"}),
        now=NOW,
    )

    executed = await decide_tool_call(
        db_session,
        registry,
        tool_call_id=pending.id,
        user_id=user.id,
        confirm=True,
        now=NOW,
    )
    assert executed.status == "succeeded"
    assert calls == [{"item": "A"}]
    with pytest.raises(HTTPException) as conflict:
        await decide_tool_call(
            db_session,
            registry,
            tool_call_id=pending.id,
            user_id=user.id,
            confirm=True,
            now=NOW,
        )
    assert conflict.value.status_code == 409


@pytest.mark.asyncio
async def test_deny_expiry_and_handler_failure_are_terminal_and_audited(db_session):
    registry = build_registry([])
    user, run = await make_run(db_session)
    denied = await propose_or_execute(
        db_session,
        registry,
        run_id=run.id,
        user_id=user.id,
        planned_call=PlannedToolCall("deny", "write_item", {"item": "D"}),
        now=NOW,
    )
    denied = await decide_tool_call(
        db_session,
        registry,
        tool_call_id=denied.id,
        user_id=user.id,
        confirm=False,
        now=NOW,
    )
    assert denied.status == "denied"

    expired = await propose_or_execute(
        db_session,
        registry,
        run_id=run.id,
        user_id=user.id,
        planned_call=PlannedToolCall("expire", "write_item", {"item": "E"}),
        step_number=2,
        now=NOW,
        confirmation_ttl=timedelta(seconds=1),
    )
    expired = await decide_tool_call(
        db_session,
        registry,
        tool_call_id=expired.id,
        user_id=user.id,
        confirm=True,
        now=NOW + timedelta(seconds=2),
    )
    assert expired.status == "expired"

    failing = await propose_or_execute(
        db_session,
        registry,
        run_id=run.id,
        user_id=user.id,
        planned_call=PlannedToolCall("fail", "fail_item", {}),
        step_number=3,
        now=NOW,
    )
    failing = await decide_tool_call(
        db_session,
        registry,
        tool_call_id=failing.id,
        user_id=user.id,
        confirm=True,
        now=NOW,
    )
    assert failing.status == "failed"
    assert failing.error == "handler exploded"
    assert [event.action_type for event in await audit_events(db_session)] == [
        "tool_call_requested",
        "tool_call_denied",
        "tool_call_requested",
        "tool_call_expired",
        "tool_call_requested",
        "tool_call_confirmed",
        "tool_call_failed",
    ]
