import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.config import settings
from app.models import User
from app.services.llm_service import complete_chat
from app.services.retrieval_service import SearchHit, search_chunks

NO_EVIDENCE_MESSAGE = (
    "No sufficient evidence found. Please add relevant documents or contact an administrator."
)
CITATION_RE = re.compile(r"\[S(\d+)\]")


@dataclass(frozen=True)
class Citation:
    label: str
    chunk_id: UUID
    document_id: UUID
    filename: str
    source_locator: str
    chunk_index: int
    score: float


@dataclass(frozen=True)
class RAGAnswer:
    answer: str
    citations: list[Citation]
    no_evidence: bool


class RAGCitationError(RuntimeError):
    pass


async def answer_question(
    db: AsyncSession,
    kb_id: UUID,
    user: User,
    question: str,
    *,
    top_k: int = 5,
    searcher=search_chunks,
    completer=complete_chat,
) -> RAGAnswer:
    hits: list[SearchHit] = await searcher(db, kb_id, user.id, question, top_k=top_k)
    evidence = [hit for hit in hits if hit.score >= settings.RETRIEVAL_MIN_SCORE]
    if not evidence:
        answer = RAGAnswer(NO_EVIDENCE_MESSAGE, [], True)
        await record_audit(
            db,
            action_type="knowledge_query",
            user_id=user.id,
            input_data=question,
            output={"kb_id": kb_id, "no_evidence": True, "citation_coverage": 0.0},
            tool_used="knowledge_rag",
        )
        return answer
    sources = "\n\n".join(
        f"[S{i}] filename={hit.filename} locator={hit.source_locator} "
        f"chunk_id={hit.chunk_id}\n{hit.content}"
        for i, hit in enumerate(evidence, 1)
    )
    answer_text = await completer(
        [
            {
                "role": "system",
                "content": (
                    "Answer only from the supplied sources. Cite every factual claim using "
                    "supplied labels. Never invent labels. If evidence is insufficient "
                    "return the exact fallback."
                ),
            },
            {"role": "user", "content": f"Question: {question}\n\nSources:\n{sources}"},
        ]
    )
    if answer_text == NO_EVIDENCE_MESSAGE:
        return RAGAnswer(answer_text, [], True)
    labels = []
    for match in CITATION_RE.finditer(answer_text):
        label = f"[S{match.group(1)}]"
        if label not in labels:
            labels.append(label)
    if not labels:
        raise RAGCitationError("Answer contains no citations")
    citations = []
    for label in labels:
        index = int(label[2:-1])
        if not 1 <= index <= len(evidence):
            raise RAGCitationError("Answer contains an unknown citation")
        hit = evidence[index - 1]
        citations.append(
            Citation(
                label,
                hit.chunk_id,
                hit.document_id,
                hit.filename,
                hit.source_locator,
                hit.chunk_index,
                hit.score,
            )
        )
    await record_audit(
        db,
        action_type="knowledge_query",
        user_id=user.id,
        input_data=question,
        output={
            "kb_id": kb_id,
            "chunks": [{"chunk_id": h.chunk_id, "score": h.score} for h in hits],
            "cited_chunk_ids": [c.chunk_id for c in citations],
            "citation_coverage": 1.0,
            "no_evidence": False,
        },
        tool_used="knowledge_rag",
    )
    return RAGAnswer(answer_text, citations, False)
