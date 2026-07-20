import json
from datetime import datetime
from uuid import UUID

from typing import Any, Literal

from pydantic import BaseModel, Field, StrictBool


class ConversationCreate(BaseModel):
    title: str = Field(default="New Conversation", max_length=256)


class ConversationResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationListItem(BaseModel):
    id: UUID
    title: str
    message_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ToolCallResponse(BaseModel):
    id: UUID
    run_id: UUID
    provider_call_id: str
    tool_name: str
    arguments: dict[str, Any]
    side_effect: Literal["read", "write"]
    impact: str
    status: str
    result: Any | None = None
    error: str | None = None
    expires_at: datetime | None = None


class AgentTurnResponse(BaseModel):
    run_id: UUID
    status: str
    answer: str | None = None
    tool_call: ToolCallResponse | None = None
    step_count: int = 0
    elapsed_ms: int = 0


class ToolDecisionRequest(BaseModel):
    confirm: StrictBool


def _json_object(value: Any) -> dict[str, Any]:
    if not isinstance(value, str):
        return value if isinstance(value, dict) else {}
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _json_value(value: Any) -> Any | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def map_message(message: Any) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
    )


def map_tool_call(call: Any) -> ToolCallResponse:
    return ToolCallResponse(
        id=call.id,
        run_id=call.run_id,
        provider_call_id=call.provider_call_id,
        tool_name=call.tool_name,
        arguments=_json_object(call.arguments),
        side_effect=call.side_effect,
        impact=call.impact,
        status=call.status,
        result=_json_value(call.result),
        error=call.error,
        expires_at=call.expires_at,
    )


def map_agent_turn(turn: Any) -> AgentTurnResponse:
    return AgentTurnResponse(
        run_id=turn.run_id,
        status=turn.status,
        answer=turn.answer,
        tool_call=map_tool_call(turn.tool_call) if turn.tool_call is not None else None,
        step_count=turn.step_count,
        elapsed_ms=turn.elapsed_ms,
    )


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=16_000)


class MessageSendResponse(BaseModel):
    messages: list[MessageResponse]
