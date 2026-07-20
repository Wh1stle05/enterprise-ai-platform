from sqlalchemy import inspect

from app.models import AgentRun, ToolCall


def test_m3_model_contract():
    assert {column.key for column in inspect(AgentRun).columns} == {
        "id", "conversation_id", "user_id", "status", "allowed_tools",
        "model_context", "step_count", "elapsed_ms", "created_at", "updated_at",
    }
    assert {column.key for column in inspect(ToolCall).columns} == {
        "id", "run_id", "step_number", "provider_call_id", "tool_name", "arguments", "side_effect",
        "impact", "status", "result", "error", "expires_at", "created_at", "updated_at",
    }
