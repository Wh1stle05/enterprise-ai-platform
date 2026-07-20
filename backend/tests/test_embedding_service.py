from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services.embedding_service import EmbeddingDimensionError, embed_texts


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
