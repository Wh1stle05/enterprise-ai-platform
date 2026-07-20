from typing import Any

import pytest

from app.agent.contracts import AgentDecision, PlannedToolCall, ToolDefinition
from app.agent.registry import (
    DuplicateToolError,
    ToolArgumentsError,
    ToolRegistry,
    UnknownToolError,
)


async def fake_handler(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    return arguments


def make_definition(name: str = "lookup", **overrides: Any) -> ToolDefinition:
    values = {
        "name": name,
        "description": "Look up one item",
        "side_effect": "read",
        "parameters": {
            "type": "object",
            "properties": {"sku": {"type": "string"}},
            "required": ["sku"],
            "additionalProperties": False,
        },
        "handler": fake_handler,
        "impact": lambda arguments: f"Reads {arguments['sku']}",
    }
    values.update(overrides)
    return ToolDefinition(**values)


def test_registry_rejects_duplicate_tool_names() -> None:
    registry = ToolRegistry()
    registry.register(make_definition())

    with pytest.raises(DuplicateToolError):
        registry.register(make_definition())


def test_registry_rejects_unknown_tools() -> None:
    registry = ToolRegistry()

    with pytest.raises(UnknownToolError):
        registry.get("missing", set())

    with pytest.raises(UnknownToolError):
        registry.validate("missing", {})


def test_registry_applies_server_whitelist_to_lookup_and_export() -> None:
    registry = ToolRegistry()
    registry.register(make_definition("allowed"))
    registry.register(make_definition("blocked"))

    assert registry.get("allowed", {"allowed"}).name == "allowed"
    with pytest.raises(UnknownToolError):
        registry.get("blocked", {"allowed"})

    exported = registry.openai_tools({"allowed"})
    assert [tool["function"]["name"] for tool in exported] == ["allowed"]


def test_registry_validates_valid_arguments() -> None:
    registry = ToolRegistry()
    registry.register(make_definition())

    arguments = {"sku": "A-1"}

    assert registry.validate("lookup", arguments) == arguments


def test_registry_rejects_missing_required_arguments() -> None:
    registry = ToolRegistry()
    registry.register(make_definition())

    with pytest.raises(ToolArgumentsError):
        registry.validate("lookup", {})


def test_registry_rejects_extra_arguments() -> None:
    registry = ToolRegistry()
    registry.register(make_definition())

    with pytest.raises(ToolArgumentsError):
        registry.validate("lookup", {"sku": "A-1", "hidden": True})


def test_registry_rejects_invalid_json_schema() -> None:
    registry = ToolRegistry()

    with pytest.raises(ToolArgumentsError):
        registry.register(make_definition(parameters={"type": "not-a-schema-type"}))


def test_registry_exports_openai_function_schema() -> None:
    registry = ToolRegistry()
    registry.register(make_definition())

    assert registry.openai_tools({"lookup"}) == [
        {
            "type": "function",
            "function": {
                "name": "lookup",
                "description": "Look up one item",
                "parameters": {
                    "type": "object",
                    "properties": {"sku": {"type": "string"}},
                    "required": ["sku"],
                    "additionalProperties": False,
                },
            },
        }
    ]


def test_agent_decision_requires_exactly_one_outcome() -> None:
    with pytest.raises(ValueError):
        AgentDecision()
    with pytest.raises(ValueError):
        AgentDecision(final_answer="done", tool_call=PlannedToolCall("1", "lookup", {}))

    decision = AgentDecision(tool_call=PlannedToolCall("1", "lookup", {"sku": "A-1"}))
    assert decision.tool_call is not None
