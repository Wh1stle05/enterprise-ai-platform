"""Lock direct-connect model defaults and verify logical names pass through verbatim.

P1 must not flip LLM_MODEL/EMBEDDING_MODEL to Gateway logical names yet:
routing for chat (T2-00) and embeddings (T2-03) is not implemented, so a
Qwen logical name set via env must reach the OpenAI-compatible SDK as-is.
"""

from types import SimpleNamespace

import pytest

from app.core.config import Settings, settings
from app.services.embedding_service import embed_texts
from app.services.llm_service import complete_chat


def test_direct_connect_defaults_are_not_logical_names(monkeypatch):
    # Ignore any local .env / env override so we lock the code defaults.
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    fresh = Settings(_env_file=None)
    assert fresh.LLM_MODEL == "gpt-4o-mini"
    assert fresh.EMBEDDING_MODEL == "text-embedding-3-small"


def test_env_override_keeps_qwen_logical_name_verbatim(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "chat/qwen2.5-1.5b")
    fresh = Settings(_env_file=None)
    assert fresh.LLM_MODEL == "chat/qwen2.5-1.5b"


class FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])


@pytest.mark.asyncio
async def test_chat_sdk_receives_qwen_logical_name_verbatim(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MODEL", "chat/qwen2.5-1.5b")
    completions = FakeCompletions()
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    result = await complete_chat([{"role": "user", "content": "hi"}], client=fake_client)

    assert result == "ok"
    assert completions.calls[0]["model"] == "chat/qwen2.5-1.5b"


class FakeEmbeddings:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        dim = settings.EMBEDDING_DIM
        return SimpleNamespace(
            data=[
                SimpleNamespace(index=i, embedding=[0.1] * dim) for i in range(len(kwargs["input"]))
            ]
        )


@pytest.mark.asyncio
async def test_embedding_sdk_receives_logical_name_verbatim(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "embed/text-embedding-3-small")
    embeddings = FakeEmbeddings()
    fake_client = SimpleNamespace(embeddings=embeddings)

    vectors = await embed_texts(["hello"], client=fake_client)

    assert len(vectors) == 1
    assert embeddings.calls[0]["model"] == "embed/text-embedding-3-small"
