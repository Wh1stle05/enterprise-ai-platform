from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings
from app.services.metrics import EMBEDDING_BATCH_SIZE


class EmbeddingConfigurationError(RuntimeError):
    pass


class EmbeddingResponseError(RuntimeError):
    pass


class EmbeddingDimensionError(RuntimeError):
    pass


def get_embedding_client(client: Any | None = None) -> Any:
    """Return the embedding client, honoring an injected fake first.

    When no client is injected, the embedding upstream is selected from
    EMBEDDING_API_KEY/EMBEDDING_BASE_URL with a fallback to the LLM
    configuration, so direct-connect mode keeps working without new env vars.
    """
    if client is not None:
        return client
    api_key = settings.EMBEDDING_API_KEY or settings.LLM_API_KEY
    if not api_key:
        raise EmbeddingConfigurationError("Embedding API key is not configured")
    base_url = settings.EMBEDDING_BASE_URL or settings.LLM_BASE_URL
    return AsyncOpenAI(api_key=api_key, base_url=base_url or None)


async def embed_texts(
    texts: list[str], *, client: Any = None, batch_size: int | None = None
) -> list[list[float]]:
    if not texts:
        return []
    client = get_embedding_client(client)
    result: list[list[float]] = []
    batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
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
