from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Document, DocumentChunk
from app.services.embedding_service import embed_texts
from app.services.knowledge_acl_service import require_kb_access


@dataclass(frozen=True)
class SearchHit:
    chunk_id: UUID
    document_id: UUID
    filename: str
    chunk_index: int
    content: str
    source_locator: str
    score: float


async def search_chunks(
    db: AsyncSession,
    kb_id: UUID,
    user_id: UUID,
    query: str,
    *,
    top_k: int,
    embedder=embed_texts,
) -> list[SearchHit]:
    await require_kb_access(db, kb_id, user_id, "viewer")
    if not 1 <= top_k <= settings.RETRIEVAL_MAX_TOP_K:
        raise ValueError("top_k must be between 1 and RETRIEVAL_MAX_TOP_K")
    query_vector = (await embedder([query]))[0]
    distance = DocumentChunk.embedding.cosine_distance(query_vector)
    rows = (
        await db.execute(
            select(DocumentChunk, Document.filename, distance.label("distance"))
            .join(Document)
            .where(Document.knowledge_base_id == kb_id, Document.status == "ready")
            .order_by(distance.asc())
            .limit(top_k)
        )
    ).all()
    return [
        SearchHit(
            c.id,
            c.document_id,
            filename,
            c.chunk_index,
            c.content,
            c.source_locator,
            max(-1.0, min(1.0, 1.0 - float(distance_value))),
        )
        for c, filename, distance_value in rows
    ]
