"""Single-step planner for the bounded agent loop."""

import json
from collections.abc import Sequence
from typing import Any

from app.agent.contracts import AgentDecision, PlannedToolCall
from app.agent.registry import ToolRegistry, UnknownToolError
from app.core.config import settings
from app.services.llm_service import LLMConfigurationError, get_llm_client


async def plan_next_step(
    messages: Sequence[dict[str, str]],
    registry: ToolRegistry,
    allowed_tools: set[str],
    *,
    client: Any | None = None,
) -> AgentDecision:
    response = await get_llm_client(client).chat.completions.create(
        model=settings.LLM_MODEL,
        messages=list(messages),
        tools=registry.openai_tools(allowed_tools),
        max_tokens=settings.LLM_MAX_TOKENS,
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content if response.choices else None
    if not content or not content.strip():
        raise LLMConfigurationError("LLM returned an empty completion")

    try:
        payload = json.loads(content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise LLMConfigurationError("LLM returned malformed planner JSON") from exc

    if not isinstance(payload, dict):
        raise LLMConfigurationError("Planner must return exactly one decision")

    decision_type = payload.get("type")
    if decision_type == "final":
        answer = payload.get("content")
        if not isinstance(answer, str) or not answer.strip():
            raise LLMConfigurationError("Planner returned an invalid final answer")
        return AgentDecision(final_answer=answer.strip())

    if decision_type == "tool_call":
        call_id = payload.get("call_id")
        name = payload.get("name")
        arguments = payload.get("arguments")
        if not isinstance(call_id, str) or not call_id:
            raise LLMConfigurationError("Planner returned an invalid tool call id")
        if not isinstance(name, str) or not isinstance(arguments, dict):
            raise LLMConfigurationError("Planner returned an invalid tool call")
        try:
            registry.get(name, allowed_tools)
            registry.validate(name, arguments)
        except (UnknownToolError, ValueError) as exc:
            raise LLMConfigurationError("Planner returned an unavailable or invalid tool") from exc
        return AgentDecision(tool_call=PlannedToolCall(call_id, name, arguments))

    raise LLMConfigurationError("Planner returned an unknown decision type")
