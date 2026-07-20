import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete

from app.core.config import settings
from app.core.database import async_session_factory
from app.models import Document, DocumentChunk
from app.services.chunking_service import chunk_sections
from app.services.document_parser import parse_document
from app.services.embedding_service import embed_texts
from app.services.file_storage import LocalFileStorage


class DocumentAlreadyProcessing(RuntimeError):  # noqa: N818
    pass


def _safe_error(exc: Exception) -> str:
    return re.sub(r"/(?:[^\s/]+/)+", "[path]/", str(exc))[:500]


async def mark_document_failed(
    document_id: UUID, exc: Exception, *, db_factory=async_session_factory
):
    async with db_factory() as db:
        document = await db.get(Document, document_id)
        if document:
            document.status = "failed"
            document.error_message = _safe_error(exc)
            document.processed_at = None
            await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
            document.chunk_count = 0
            await db.commit()


async def process_document(
    document_id: UUID, *, db_factory=async_session_factory, parser=parse_document,
    chunker=chunk_sections, embedder=embed_texts,
):
    async with db_factory() as db:
        document = await db.get(Document, document_id)
        if document is None:
            return
        if document.status == "ready":
            return
        if document.status == "processing":
            raise DocumentAlreadyProcessing(str(document_id))
        document.status = "processing"
        document.error_message = None
        await db.commit()
        source_uri = document.storage_uri

    try:
        path = LocalFileStorage(
            Path(settings.UPLOAD_DIR), settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        ).resolve(source_uri)
        sections = parser(path)
        chunks = chunker(
            sections, chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP
        )
        vectors = await embedder([chunk.content for chunk in chunks])
        async with db_factory() as db:
            document = await db.get(Document, document_id)
            if document is None:
                return
            await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
            db.add_all([
                DocumentChunk(
                    document_id=document_id,
                    chunk_index=chunk.index,
                    content=chunk.content,
                    source_locator=chunk.source_locator,
                    embedding=vector,
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            ])
            document.content_text = "\n\n".join(section.text for section in sections)
            document.chunk_count = len(chunks)
            document.status = "ready"
            document.processed_at = datetime.now(timezone.utc)
            await db.commit()
    except Exception as exc:
        async with db_factory() as db:
            document = await db.get(Document, document_id)
            if document:
                document.status = "pending"
                document.error_message = _safe_error(exc)
                await db.commit()
        raise
