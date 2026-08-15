"""Bounded, durable, and resumable agent execution."""

import inspect
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.contracts import AgentDecision, PlannedToolCall
from app.agent.executor import decide_tool_call, propose_or_execute
from app.agent.planner import plan_next_step
from app.agent.registry import ToolRegistry
from app.core.config import settings
from app.models import AgentRun, Conversation, ToolCall


@dataclass(frozen=True)
class AgentTurnResult:
    run_id: UUID
    status: str
    answer: str | None = None
    tool_call: ToolCall | None = None
    step_count: int = 0
    elapsed_ms: int = 0
    model_context: str = "[]"


def _utc(value: datetime | None) -> datetime:
    value = value or datetime.now(timezone.utc)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _call_message(call: PlannedToolCall) -> dict[str, Any]:
    return {
        "role": "assistant",
        "tool_calls": [
            {
                "id": call.call_id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments, sort_keys=True),
                },
            }
        ],
    }


def _observation(call_id: str, content: Any) -> dict[str, str]:
    if not isinstance(content, str):
        content = json.dumps(content, sort_keys=True, default=str)
    return {"role": "tool", "tool_call_id": call_id, "content": content}


def _call_observation(call: ToolCall) -> dict[str, str]:
    if call.status == "succeeded":
        content = call.result or "{}"
    elif call.status in {"denied", "expired"}:
        content = f"Tool call {call.status}."
    else:
        content = call.error or f"Tool call {call.status}."
    return _observation(call.provider_call_id, content)


def build_turn_result(
    run: AgentRun, *, answer: str | None = None, tool_call: ToolCall | None = None
) -> AgentTurnResult:
    return AgentTurnResult(
        run_id=run.id,
        status=run.status,
        answer=answer,
        tool_call=tool_call,
        step_count=run.step_count,
        elapsed_ms=run.elapsed_ms,
        model_context=run.model_context,
    )


async def _load_run(db: AsyncSession, run_id: UUID, user_id: UUID) -> AgentRun:
    result = await db.execute(
        select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == user_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent run not found")
    return run


async def _drive(
    db: AsyncSession,
    registry: ToolRegistry,
    run: AgentRun,
    user_id: UUID,
    *,
    max_steps: int,
    max_active_seconds: float,
    now: datetime | None = None,
) -> AgentTurnResult:
    context = json.loads(run.model_context)
    started = time.monotonic()
    if max_active_seconds <= 0:
        run.status = "limit_reached"
        run.elapsed_ms = max(run.elapsed_ms, 0)
        await db.flush()
        return build_turn_result(run)

    while run.step_count < max_steps:
        if time.monotonic() - started >= max_active_seconds:
            run.status = "limit_reached"
            break
        run.step_count += 1
        try:
            planned_result = plan_next_step(context, registry, set(json.loads(run.allowed_tools)))
            decision: AgentDecision = (
                await planned_result if inspect.isawaitable(planned_result) else planned_result
            )
        except Exception as exc:
            run.status = "failed"
            await db.flush()
            return build_turn_result(run, answer=str(exc))

        if decision.final_answer is not None:
            run.status = "completed"
            run.model_context = json.dumps(
                context + [{"role": "assistant", "content": decision.final_answer}]
            )
            run.elapsed_ms = max(run.elapsed_ms, int((time.monotonic() - started) * 1000))
            await db.flush()
            return build_turn_result(run, answer=decision.final_answer)

        planned = decision.tool_call
        assert planned is not None
        context.append(_call_message(planned))
        try:
            call = await propose_or_execute(
                db,
                registry,
                run_id=run.id,
                user_id=user_id,
                planned_call=planned,
                step_number=run.step_count,
                now=now,
            )
        except HTTPException as exc:
            feedback = exc.detail or "Tool call failed"
            context.append(_observation(planned.call_id, str(feedback)))
            run.model_context = json.dumps(context)
            if exc.status_code == status.HTTP_403_FORBIDDEN:
                run.status = "failed"
                await db.flush()
                return build_turn_result(run, answer=str(feedback))
            continue

        await db.refresh(run)
        run.model_context = json.dumps(context)
        if call.status == "pending_confirmation":
            run.status = "waiting_confirmation"
            run.elapsed_ms = max(run.elapsed_ms, int((time.monotonic() - started) * 1000))
            await db.flush()
            return build_turn_result(run, tool_call=call)
        context.append(_call_observation(call))
        run.model_context = json.dumps(context)

    if run.status == "running":
        run.status = "limit_reached"
    run.elapsed_ms = max(run.elapsed_ms, int((time.monotonic() - started) * 1000))
    await db.flush()
    return build_turn_result(run)


async def start_agent_turn(
    db: AsyncSession,
    registry: ToolRegistry,
    conversation_id: UUID | str,
    user_id: UUID | str,
    content: str,
    *,
    history: list[dict[str, Any]] | None = None,
    allowed_tools: set[str] | None = None,
    max_steps: int = settings.AGENT_MAX_STEPS,
    max_active_seconds: float = settings.AGENT_MAX_ACTIVE_SECONDS,
    now: datetime | None = None,
) -> AgentTurnResult:
    cid, uid = UUID(str(conversation_id)), UUID(str(user_id))
    conversation = (
        await db.execute(
            select(Conversation).where(Conversation.id == cid, Conversation.user_id == uid)
        )
    ).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    requested = allowed_tools if allowed_tools is not None else set(settings.AGENT_TOOL_WHITELIST)
    effective = set(requested) & set(settings.AGENT_TOOL_WHITELIST) & registry.names
    run = AgentRun(
        conversation_id=cid,
        user_id=uid,
        status="running",
        allowed_tools=json.dumps(sorted(effective)),
        model_context=json.dumps(
            history if history is not None else [{"role": "user", "content": content}]
        ),
    )
    db.add(run)
    await db.flush()
    return await _drive(
        db, registry, run, uid, max_steps=max_steps, max_active_seconds=max_active_seconds, now=now
    )


async def resume_agent_run(
    db: AsyncSession,
    registry: ToolRegistry,
    run_id: UUID | str,
    user_id: UUID | str,
    *,
    confirm: bool | None = None,
    max_steps: int = settings.AGENT_MAX_STEPS,
    max_active_seconds: float = settings.AGENT_MAX_ACTIVE_SECONDS,
    now: datetime | None = None,
) -> AgentTurnResult:
    uid = UUID(str(user_id))
    run = await _load_run(db, UUID(str(run_id)), uid)
    if run.status != "waiting_confirmation":
        return build_turn_result(run)
    pending = (
        (
            await db.execute(
                select(ToolCall)
                .where(ToolCall.run_id == run.id, ToolCall.status == "pending_confirmation")
                .order_by(ToolCall.step_number)
            )
        )
        .scalars()
        .first()
    )
    if pending is None or confirm is None:
        return build_turn_result(run, tool_call=pending)
    call = await decide_tool_call(
        db, registry, tool_call_id=pending.id, user_id=uid, confirm=confirm, now=now
    )
    context = json.loads(run.model_context)
    if call.status in {"denied", "expired"}:
        context.append(_call_observation(call))
        run.model_context = json.dumps(context)
        run.status = "completed"
        answer = f"Tool call {call.status}."
        await db.flush()
        return build_turn_result(run, answer=answer, tool_call=call)
    context.append(_call_observation(call))
    run.model_context = json.dumps(context)
    run.status = "running"
    await db.flush()
    return await _drive(
        db, registry, run, uid, max_steps=max_steps, max_active_seconds=max_active_seconds, now=now
    )
