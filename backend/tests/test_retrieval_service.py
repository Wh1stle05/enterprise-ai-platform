import pytest

from app.core.config import settings


def test_retrieval_top_k_bounds():
    assert settings.RETRIEVAL_MAX_TOP_K == 20
    assert settings.RETRIEVAL_MIN_SCORE == 0.35


@pytest.mark.asyncio
async def test_retrieval_rejects_invalid_top_k():
    from app.services.retrieval_service import search_chunks

    class DB:
        pass

    with pytest.raises(Exception):
        await search_chunks(DB(), None, None, "query", top_k=0)
