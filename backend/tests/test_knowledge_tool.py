from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.agent.contracts import ToolContext
from app.agent.registry import ToolArgumentsError, ToolRegistry
from app.services.rag_service import Citation, RAGAnswer
from app.tools.knowledge import build_knowledge_tool


@pytest.fixture
def context() -> ToolContext:
    return ToolContext(db=AsyncMock(), user=SimpleNamespace(id=uuid4()))


def test_knowledge_tool_requires_knowledge_base_and_query() -> None:
    tool = build_knowledge_tool()
    registry = ToolRegistry()
    registry.register(tool)

    with pytest.raises(ToolArgumentsError):
        registry.validate("knowledge_search", {"query": "policy"})
    with pytest.raises(ToolArgumentsError):
        registry.validate("knowledge_search", {"knowledge_base_id": str(uuid4())})


@pytest.mark.asyncio
async def test_knowledge_tool_returns_serializable_citations(context: ToolContext) -> None:
    citation = Citation(
        label="[S1]",
        chunk_id=uuid4(),
        document_id=uuid4(),
        filename="leave-policy.md",
        source_locator="document:1",
        chunk_index=2,
        score=0.91,
    )
    answerer = AsyncMock(return_value=RAGAnswer("Five days [S1].", [citation], False))
    tool = build_knowledge_tool(answerer=answerer)
    knowledge_base_id = uuid4()

    result = await tool.handler(
        context,
        {
            "knowledge_base_id": str(knowledge_base_id),
            "query": "What is the leave policy?",
            "top_k": 5,
        },
    )

    assert result == {
        "answer": "Five days [S1].",
        "no_evidence": False,
        "citations": [
            {
                "label": "[S1]",
                "chunk_id": str(citation.chunk_id),
                "document_id": str(citation.document_id),
                "filename": "leave-policy.md",
                "source_locator": "document:1",
                "chunk_index": 2,
                "score": 0.91,
            }
        ],
    }
    answerer.assert_awaited_once_with(
        context.db, knowledge_base_id, context.user, "What is the leave policy?", top_k=5
    )
    assert tool.side_effect == "read"


@pytest.mark.asyncio
async def test_knowledge_tool_preserves_acl_behavior(context: ToolContext) -> None:
    answerer = AsyncMock(side_effect=HTTPException(403, "Insufficient knowledge base access"))
    tool = build_knowledge_tool(answerer=answerer)

    with pytest.raises(HTTPException) as raised:
        await tool.handler(
            context,
            {"knowledge_base_id": str(uuid4()), "query": "restricted policy"},
        )

    assert raised.value.status_code == 403
