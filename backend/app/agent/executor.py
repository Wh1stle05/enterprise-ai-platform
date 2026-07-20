"""Durable, audited execution and confirmation of agent tool calls."""

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.contracts import PlannedToolCall, ToolContext
from app.agent.registry import ToolArgumentsError, ToolRegistry, UnknownToolError
from app.core.audit import record_audit
from app.models import AgentRun, ToolCall, User

DEFAULT_CONFIRMATION_TTL = timedelta(minutes=10)


def _utc(value: datetime | None) -> datetime:
    value = value or datetime.now(timezone.utc)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _allowed_tools(run: AgentRun) -> set[str]:
    try:
        values = json.loads(run.allowed_tools)
    except (TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Invalid run tool policy"
        ) from exc
    return set(values) if isinstance(values, list) else set()


async def _load_run_and_user(
    db: AsyncSession, run_id: UUID, user_id: UUID
) -> tuple[AgentRun, User]:
    result = await db.execute(
        select(AgentRun, User)
        .join(User, User.id == AgentRun.user_id)
        .where(AgentRun.id == run_id, AgentRun.user_id == user_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent run not found")
    return row


def _tool_or_error(registry: ToolRegistry, name: str, allowed: set[str]):
    try:
        return registry.get(name, allowed)
    except UnknownToolError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Tool is not allowed") from exc


def _validate(registry: ToolRegistry, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        return registry.validate(name, arguments)
    except (UnknownToolError, ToolArgumentsError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid tool arguments") from exc


def _audit_input(call: ToolCall, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "tool_call_id": str(call.id),
        "provider_call_id": call.provider_call_id,
        "tool_name": call.tool_name,
        "arguments": arguments if arguments is not None else json.loads(call.arguments),
        "impact": call.impact,
    }


async def _claim_pending(
    db: AsyncSession, call_id: UUID, *, now: datetime, require_unexpired: bool = False
) -> bool:
    conditions = [ToolCall.id == call_id, ToolCall.status == "pending_confirmation"]
    if require_unexpired:
        conditions.append(ToolCall.expires_at > now)
    result = await db.execute(update(ToolCall).where(*conditions).values(status="running"))
    return result.rowcount == 1


async def propose_or_execute(
    db: AsyncSession,
    registry: ToolRegistry,
    *,
    run_id: UUID,
    user_id: UUID,
    planned_call: PlannedToolCall,
    step_number: int = 1,
    now: datetime | None = None,
    confirmation_ttl: timedelta = DEFAULT_CONFIRMATION_TTL,
) -> ToolCall:
    now = _utc(now)
    run, user = await _load_run_and_user(db, run_id, user_id)
    tool = _tool_or_error(registry, planned_call.name, _allowed_tools(run))
    arguments = _validate(registry, planned_call.name, planned_call.arguments)
    call = ToolCall(
        run_id=run.id,
        step_number=step_number,
        provider_call_id=planned_call.call_id,
        tool_name=tool.name,
        arguments=json.dumps(arguments, sort_keys=True, separators=(",", ":")),
        side_effect=tool.side_effect,
        impact=tool.impact(arguments),
        status="pending_confirmation",
        expires_at=now + confirmation_ttl if tool.side_effect == "write" else None,
    )
    db.add(call)
    await db.flush()
    await record_audit(
        db, action_type="tool_proposed", user_id=user.id, input_data=_audit_input(call, arguments),
        tool_used=tool.name,
    )
    if tool.side_effect == "write":
        run.status = "waiting_confirmation"
        await db.commit()
        return call

    await db.commit()
    if not await _claim_pending(db, call.id, now=now):
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Tool call is no longer pending")
    await db.commit()
    return await _execute_claimed(db, registry, call.id, user.id)


async def _execute_claimed(
    db: AsyncSession, registry: ToolRegistry, call_id: UUID, user_id: UUID
) -> ToolCall:
    result = await db.execute(
        select(ToolCall, User)
        .join(AgentRun, AgentRun.id == ToolCall.run_id)
        .join(User, User.id == AgentRun.user_id)
        .where(ToolCall.id == call_id, AgentRun.user_id == user_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tool call not found")
    call, user = row
    tool = _tool_or_error(registry, call.tool_name, registry.names)
    arguments = json.loads(call.arguments)
    try:
        output = await tool.handler(ToolContext(db=db, user=user), arguments)
    except Exception as exc:
        await db.rollback()
        failed = await db.execute(select(ToolCall).where(ToolCall.id == call_id))
        call = failed.scalar_one()
        await db.refresh(call)
        audit_input = _audit_input(call, arguments)
        call.status = "failed"
        call.error = str(exc)
        await record_audit(
            db, action_type="tool_failed", user_id=user_id, input_data=audit_input,
            output={"error": str(exc)}, tool_used=call.tool_name,
        )
        await db.commit()
        return call

    call.status = "succeeded"
    call.result = json.dumps(output, sort_keys=True, default=str)
    await record_audit(
        db, action_type="tool_executed", user_id=user.id, input_data=_audit_input(call, arguments),
        output=output, tool_used=call.tool_name,
    )
    await db.commit()
    return call


async def decide_tool_call(
    db: AsyncSession,
    registry: ToolRegistry,
    *,
    tool_call_id: UUID,
    user_id: UUID,
    confirm: bool,
    now: datetime | None = None,
) -> ToolCall:
    now = _utc(now)
    result = await db.execute(
        select(ToolCall, AgentRun, User)
        .join(AgentRun, AgentRun.id == ToolCall.run_id)
        .join(User, User.id == AgentRun.user_id)
        .where(ToolCall.id == tool_call_id, AgentRun.user_id == user_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tool call not found")
    call, run, user = row
    if call.status != "pending_confirmation":
        raise HTTPException(status.HTTP_409_CONFLICT, "Tool call is no longer pending")

    if call.expires_at and _utc(call.expires_at) <= now:
        result = await db.execute(
            update(ToolCall)
            .where(ToolCall.id == call.id, ToolCall.status == "pending_confirmation")
            .values(status="expired")
        )
        if result.rowcount == 1:
            call.status = "expired"
            run.status = "running"
            await record_audit(
                db, action_type="tool_expired", user_id=user.id, input_data=_audit_input(call),
                tool_used=call.tool_name,
            )
            await db.commit()
            return call
        raise HTTPException(status.HTTP_409_CONFLICT, "Tool call is no longer pending")

    target = "running" if confirm else "denied"
    result = await db.execute(
        update(ToolCall)
        .where(ToolCall.id == call.id, ToolCall.status == "pending_confirmation")
        .values(status=target)
    )
    if result.rowcount != 1:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Tool call is no longer pending")
    call.status = target
    run.status = "running"
    event = "tool_confirmed" if confirm else "tool_denied"
    await record_audit(
        db,
        action_type=event,
        user_id=user.id,
        input_data=_audit_input(call),
        tool_used=call.tool_name,
    )
    await db.commit()
    if not confirm:
        return call
    return await _execute_claimed(db, registry, call.id, user.id)
