from types import SimpleNamespace

import pytest

import app.services.embedding_service as embedding_service
from app.core.config import settings
from app.services.embedding_service import (
    EmbeddingConfigurationError,
    EmbeddingDimensionError,
    embed_texts,
    get_embedding_client,
)


class FakeEmbeddings:
    def __init__(self):
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        value = 0.1 + (len(self.calls) - 1) * 0.1
        return SimpleNamespace(
            data=[SimpleNamespace(index=0, embedding=[value] * settings.EMBEDDING_DIM)]
        )


class FakeClient:
    def __init__(self):
        self.embeddings = FakeEmbeddings()


@pytest.mark.asyncio
async def test_embeddings_batch_in_order_and_validate_dimension():
    fake = FakeClient()
    vectors = await embed_texts(["first", "second"], client=fake, batch_size=1)
    assert vectors == [[0.1] * 1536, [0.2] * 1536]
    assert [call["input"] for call in fake.embeddings.calls] == [["first"], ["second"]]
    assert all(call["dimensions"] == 1536 for call in fake.embeddings.calls)


@pytest.mark.asyncio
async def test_empty_embeddings_make_no_call():
    fake = FakeClient()
    assert await embed_texts([], client=fake) == []
    assert fake.embeddings.calls == []


@pytest.mark.asyncio
async def test_embedding_dimension_error():
    class Bad:
        async def create(self, **kwargs):
            return SimpleNamespace(data=[SimpleNamespace(index=0, embedding=[1, 2])])

    with pytest.raises(EmbeddingDimensionError):
        await embed_texts(["bad"], client=SimpleNamespace(embeddings=Bad()))


class RecordingOpenAI:
    """Replaces AsyncOpenAI in the service module and records constructor kwargs."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.embeddings = FakeEmbeddings()


def _patch_openai(monkeypatch, captured):
    def factory(**kwargs):
        captured.update(kwargs)
        return RecordingOpenAI(**kwargs)

    monkeypatch.setattr(embedding_service, "AsyncOpenAI", factory)


def test_get_embedding_client_falls_back_to_llm_config(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_API_KEY", None)
    monkeypatch.setattr(settings, "EMBEDDING_BASE_URL", None)
    monkeypatch.setattr(settings, "LLM_API_KEY", "llm-key")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://llm.example/v1")
    captured: dict = {}
    _patch_openai(monkeypatch, captured)

    client = get_embedding_client()

    assert client.kwargs["api_key"] == "llm-key"
    assert client.kwargs["base_url"] == "https://llm.example/v1"
    assert captured == {"api_key": "llm-key", "base_url": "https://llm.example/v1"}


def test_get_embedding_client_prefers_embedding_config(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_API_KEY", "embed-key")
    monkeypatch.setattr(settings, "EMBEDDING_BASE_URL", "https://embed.example/v1")
    monkeypatch.setattr(settings, "LLM_API_KEY", "llm-key")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://llm.example/v1")
    captured: dict = {}
    _patch_openai(monkeypatch, captured)

    client = get_embedding_client()

    assert client.kwargs["api_key"] == "embed-key"
    assert client.kwargs["base_url"] == "https://embed.example/v1"
    assert captured == {"api_key": "embed-key", "base_url": "https://embed.example/v1"}


def test_get_embedding_client_raises_when_all_keys_are_empty(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_API_KEY", None)
    monkeypatch.setattr(settings, "LLM_API_KEY", None)

    with pytest.raises(EmbeddingConfigurationError):
        get_embedding_client()


def test_get_embedding_client_returns_injected_client_without_reading_settings(
    monkeypatch,
):
    # Even with no key configured at all, an injected client is used as-is.
    monkeypatch.setattr(settings, "EMBEDDING_API_KEY", None)
    monkeypatch.setattr(settings, "LLM_API_KEY", None)
    fake = FakeClient()

    assert get_embedding_client(fake) is fake


@pytest.mark.asyncio
async def test_embed_texts_uses_embedding_config_without_injection(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_API_KEY", "embed-key")
    monkeypatch.setattr(settings, "EMBEDDING_BASE_URL", "https://embed.example/v1")
    captured: dict = {}
    _patch_openai(monkeypatch, captured)

    vectors = await embed_texts(["hello"])

    assert vectors == [[0.1] * settings.EMBEDDING_DIM]
    assert captured == {"api_key": "embed-key", "base_url": "https://embed.example/v1"}


@pytest.mark.asyncio
async def test_embed_texts_without_injection_raises_when_no_key(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_API_KEY", None)
    monkeypatch.setattr(settings, "LLM_API_KEY", None)

    with pytest.raises(EmbeddingConfigurationError):
        await embed_texts(["hello"])
