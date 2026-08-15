from uuid import UUID

from app.agent.contracts import ToolContext, ToolDefinition
from app.services.rag_service import answer_question


def build_knowledge_tool(answerer=answer_question) -> ToolDefinition:
    async def knowledge_search(context: ToolContext, args: dict) -> dict:
        answer = await answerer(
            context.db,
            UUID(args["knowledge_base_id"]),
            context.user,
            args["query"],
            top_k=args.get("top_k", 5),
        )
        return {
            "answer": answer.answer,
            "no_evidence": answer.no_evidence,
            "citations": [
                {
                    "label": citation.label,
                    "chunk_id": str(citation.chunk_id),
                    "document_id": str(citation.document_id),
                    "filename": citation.filename,
                    "source_locator": citation.source_locator,
                    "chunk_index": citation.chunk_index,
                    "score": citation.score,
                }
                for citation in answer.citations
            ],
        }

    return ToolDefinition(
        name="knowledge_search",
        description=(
            "Search one accessible knowledge base and answer from retrieved evidence. "
            "Use this before a business tool when policy or procedure evidence is needed."
        ),
        parameters={
            "type": "object",
            "properties": {
                "knowledge_base_id": {"type": "string", "format": "uuid"},
                "query": {"type": "string", "minLength": 1, "maxLength": 8000},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
            },
            "required": ["knowledge_base_id", "query"],
            "additionalProperties": False,
        },
        side_effect="read",
        handler=knowledge_search,
        impact=lambda args: f"Search knowledge base {args['knowledge_base_id']}.",
    )
