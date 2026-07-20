from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.rag_service import NO_EVIDENCE_MESSAGE, answer_question
from app.services.retrieval_service import SearchHit


class FakeDB:
    def add(self, _entry):
        pass

    async def flush(self):
        pass


@pytest.mark.asyncio
async def test_rag_does_not_call_llm_without_evidence():
    llm = AsyncMock()
    answer = await answer_question(
        FakeDB(), uuid4(), SimpleNamespace(id=uuid4()), "leave",
        searcher=AsyncMock(return_value=[]), completer=llm,
    )
    assert answer.answer == NO_EVIDENCE_MESSAGE and answer.citations == []
    llm.assert_not_awaited()


@pytest.mark.asyncio
async def test_rag_validates_citations():
    hit = SearchHit(uuid4(), uuid4(), "policy.md", 0, "Five days", "document", 0.9)
    answer = await answer_question(
        FakeDB(), uuid4(), SimpleNamespace(id=uuid4()), "leave",
        searcher=AsyncMock(return_value=[hit]), completer=AsyncMock(return_value="Five days [S1]"),
    )
    assert answer.citations[0].label == "[S1]"
