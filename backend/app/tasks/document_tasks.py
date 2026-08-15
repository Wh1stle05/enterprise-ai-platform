import asyncio
from uuid import UUID

from app.services.document_processing_service import mark_document_failed, process_document
from app.worker import celery_app


@celery_app.task(bind=True, name="documents.process", max_retries=3)
def process_document_task(self, document_id: str) -> None:
    try:
        asyncio.run(process_document(UUID(document_id)))
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            asyncio.run(mark_document_failed(UUID(document_id), exc))
            raise
        raise self.retry(exc=exc, countdown=2**self.request.retries)
