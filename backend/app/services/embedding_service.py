from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings


class EmbeddingConfigurationError(RuntimeError):
    pass


class EmbeddingResponseError(RuntimeError):
    pass


class EmbeddingDimensionError(RuntimeError):
    pass


async def embed_texts(
    texts: list[str], *, client: Any = None, batch_size: int | None = None
) -> list[list[float]]:
    if not texts:
        return []
    if client is None:
        if not settings.LLM_API_KEY:
            raise EmbeddingConfigurationError("Embedding API key is not configured")
        client = AsyncOpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL or None)
    result: list[list[float]] = []
    for start in range(0, len(texts), batch_size or settings.EMBEDDING_BATCH_SIZE):
        batch = texts[start : start + (batch_size or settings.EMBEDDING_BATCH_SIZE)]
        response = await client.embeddings.create(
            model=settings.EMBEDDING_MODEL, input=batch, dimensions=settings.EMBEDDING_DIM
        )
        data = sorted(response.data, key=lambda item: item.index)
        if len(data) != len(batch):
            raise EmbeddingResponseError("Embedding response count does not match input")
        for item in data:
            vector = list(item.embedding)
            if len(vector) != settings.EMBEDDING_DIM:
                raise EmbeddingDimensionError("Embedding vector has an unexpected dimension")
            result.append(vector)
    return result
