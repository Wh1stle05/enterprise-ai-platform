from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services.llm_service import LLMConfigurationError, complete_chat


class FakeCompletions:
    def __init__(self):
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=" pong "))])


@pytest.mark.asyncio
async def test_complete_chat_uses_model_and_history(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")
    completions = FakeCompletions()
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    result = await complete_chat([{"role": "user", "content": "ping"}], client=fake_client)
    assert result == "pong"
    assert completions.calls[0]["model"] == settings.LLM_MODEL
    assert completions.calls[0]["messages"] == [{"role": "user", "content": "ping"}]


@pytest.mark.asyncio
async def test_missing_key_is_deterministic():
    with pytest.raises(LLMConfigurationError):
        await complete_chat([{"role": "user", "content": "ping"}])
