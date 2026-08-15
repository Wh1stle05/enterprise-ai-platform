from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User

SideEffect = Literal["read", "write"]
RunStatus = Literal["running", "waiting_confirmation", "completed", "limit_reached", "failed"]
ToolCallStatus = Literal[
    "pending_confirmation", "running", "succeeded", "denied", "expired", "failed"
]


@dataclass(frozen=True)
class ToolContext:
    db: AsyncSession
    user: User


ToolHandler = Callable[[ToolContext, dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: Mapping[str, Any]
    side_effect: SideEffect
    handler: ToolHandler
    impact: Callable[[dict[str, Any]], str]


@dataclass(frozen=True)
class PlannedToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class AgentDecision:
    final_answer: str | None = None
    tool_call: PlannedToolCall | None = None

    def __post_init__(self) -> None:
        if (self.final_answer is None) == (self.tool_call is None):
            raise ValueError("Decision must contain exactly one final answer or tool call")
