from types import SimpleNamespace

import pytest

from app.agent.contracts import PlannedToolCall, ToolDefinition
from app.agent.planner import plan_next_step
from app.agent.registry import ToolRegistry
from app.services.llm_service import LLMConfigurationError


class FakeCompletions:
    def __init__(self, contents):
        self.contents = iter(contents)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        content = next(self.contents)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def make_client(*contents):
    completions = FakeCompletions(contents)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions


def make_registry():
    async def handler(context, arguments):
        return arguments

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="lookup",
            description="Look up an item.",
            parameters={"type": "object", "properties": {"sku": {"type": "string"}}},
            side_effect="read",
            handler=handler,
            impact=lambda arguments: "lookup",
        )
    )
    registry.register(
        ToolDefinition(
            name="blocked",
            description="Should not be sent.",
            parameters={"type": "object"},
            side_effect="read",
            handler=handler,
            impact=lambda arguments: "blocked",
        )
    )
    return registry


@pytest.mark.asyncio
async def test_plan_next_step_returns_final_answer():
    client, completions = make_client('{"type":"final","content":"done"}')

    decision = await plan_next_step(
        [{"role": "user", "content": "hello"}], make_registry(), {"lookup"}, client=client
    )

    assert decision.final_answer == "done"
    assert decision.tool_call is None
    assert len(completions.calls) == 1


@pytest.mark.asyncio
async def test_plan_next_step_returns_one_tool_call():
    client, _ = make_client(
        '{"type":"tool_call","call_id":"call-1","name":"lookup","arguments":{"sku":"A-1"}}'
    )

    decision = await plan_next_step([], make_registry(), {"lookup"}, client=client)

    assert decision.tool_call == PlannedToolCall("call-1", "lookup", {"sku": "A-1"})


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["not json", "", "   "])
async def test_plan_next_step_rejects_malformed_or_empty_output(content):
    client, _ = make_client(content)

    with pytest.raises(LLMConfigurationError):
        await plan_next_step([], make_registry(), {"lookup"}, client=client)


@pytest.mark.asyncio
async def test_plan_next_step_rejects_multiple_tool_calls():
    client, _ = make_client(
        '[{"type":"tool_call","call_id":"1","name":"lookup","arguments":{}},'
        '{"type":"tool_call","call_id":"2","name":"lookup","arguments":{}}]'
    )

    with pytest.raises(LLMConfigurationError):
        await plan_next_step([], make_registry(), {"lookup"}, client=client)


@pytest.mark.asyncio
async def test_plan_next_step_sends_only_server_allowed_tools_and_exact_settings(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")
    client, completions = make_client('{"type":"final","content":"done"}')

    await plan_next_step(
        [{"role": "user", "content": "hello"}], make_registry(), {"lookup"}, client=client
    )

    call = completions.calls[0]
    assert call["model"] == settings.LLM_MODEL
    assert call["messages"] == [{"role": "user", "content": "hello"}]
    assert call["max_tokens"] == settings.LLM_MAX_TOKENS
    assert call["temperature"] == 0.2
    assert call["response_format"] == {"type": "json_object"}
    assert [tool["function"]["name"] for tool in call["tools"]] == ["lookup"]
