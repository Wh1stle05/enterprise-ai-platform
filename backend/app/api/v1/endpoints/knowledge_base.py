"""Knowledge base CRUD and resource ACL endpoints."""

from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models import Document, User
from app.schemas.knowledge import (
    ACLResponse,
    ACLUpsert,
    DocumentResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    SearchHitResponse,
    SearchRequest,
    AnswerResponse,
    CitationResponse,
    QuestionRequest,
)
from app.services.file_storage import (
    EmptyUploadError,
    LocalFileStorage,
    UnsupportedFileTypeError,
    UploadTooLargeError,
)
from app.services.knowledge_acl_service import delete_acl, list_acl, require_kb_access, upsert_acl
from app.services.knowledge_service import (
    create_knowledge_base,
    delete_knowledge_base,
    get_knowledge_base,
    list_knowledge_bases,
)
from app.tasks.document_tasks import process_document_task
from app.services.retrieval_service import search_chunks
from app.services.rag_service import answer_question

router = APIRouter()


def _response(kb, access, count):
    return KnowledgeBaseResponse(
        id=kb.id, name=kb.name, description=kb.description or "", access_level=access,
        document_count=count, created_at=kb.created_at, updated_at=kb.updated_at,
    )


@router.post("", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
async def create_endpoint(
    request: KnowledgeBaseCreate,
    user: User = Depends(require_roles("admin", "user")),
    db: AsyncSession = Depends(get_db),
):
    kb = await create_knowledge_base(user, request, db)
    return _response(kb, "owner", 0)


@router.get("", response_model=list[KnowledgeBaseResponse])
async def list_endpoint(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await list_knowledge_bases(user, db)
    return [_response(kb, access, count) for kb, access, count in rows]


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_endpoint(
    kb_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    kb, access, count = await get_knowledge_base(kb_id, user, db)
    return _response(kb, access, count)


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_endpoint(
    kb_id: UUID,
    user: User = Depends(require_roles("admin", "user")),
    db: AsyncSession = Depends(get_db),
):
    await delete_knowledge_base(kb_id, user, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{kb_id}/acl", response_model=list[ACLResponse])
async def acl_list_endpoint(
    kb_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return [
        ACLResponse(
            subject_id=e.subject_id,
            username=username,
            access_level=e.access_level,
            created_at=e.created_at,
        )
        for e, username in await list_acl(db, kb_id, user.id)
    ]


@router.put("/{kb_id}/acl/{subject_id}", response_model=ACLResponse)
async def acl_upsert_endpoint(
    kb_id: UUID, subject_id: UUID, request: ACLUpsert,
    user: User = Depends(require_roles("admin", "user")), db: AsyncSession = Depends(get_db),
):
    entry, username = await upsert_acl(db, kb_id, user.id, subject_id, request.access_level)
    return ACLResponse(
        subject_id=entry.subject_id,
        username=username,
        access_level=entry.access_level,
        created_at=entry.created_at,
    )


@router.delete("/{kb_id}/acl/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def acl_delete_endpoint(
    kb_id: UUID,
    subject_id: UUID,
    user: User = Depends(require_roles("admin", "user")),
    db: AsyncSession = Depends(get_db),
):
    await delete_acl(db, kb_id, user.id, subject_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{kb_id}/documents", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED
)
async def upload_endpoint(
    kb_id: UUID,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_kb_access(db, kb_id, user.id, "editor")
    document_id = uuid4()
    document = Document(
        id=document_id,
        knowledge_base_id=kb_id, filename=file.filename or "unknown",
        file_type=file.content_type, storage_uri="", checksum="",
        parser_version=settings.PARSER_VERSION, embedding_model=settings.EMBEDDING_MODEL,
        embedding_dim=settings.EMBEDDING_DIM, status="pending",
    )
    storage = LocalFileStorage(Path(settings.UPLOAD_DIR), settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024)
    try:
        stored = await storage.save(kb_id, document.id, document.filename, file)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(415, f"Unsupported file type: {exc}") from exc
    except EmptyUploadError as exc:
        raise HTTPException(422, "Upload cannot be empty") from exc
    except UploadTooLargeError as exc:
        raise HTTPException(413, "Upload exceeds the configured size limit") from exc
    document.storage_uri = stored.uri
    document.file_size = stored.size
    document.checksum = stored.checksum
    db.add(document)
    try:
        await db.flush()
    except IntegrityError as exc:
        await storage.delete(stored.uri)
        if "uq_documents_kb_checksum" in str(exc.orig):
            raise HTTPException(409, "This file already exists in the knowledge base") from exc
        raise
    await db.commit()
    try:
        process_document_task.delay(str(document.id))
    except Exception as exc:
        document.status = "failed"
        document.error_message = "Task queue unavailable"
        await db.commit()
        raise HTTPException(503, "Task queue unavailable") from exc
    await db.refresh(document)
    return document


@router.get("/{kb_id}/documents", response_model=list[DocumentResponse])
async def list_documents_endpoint(
    kb_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await require_kb_access(db, kb_id, user.id, "viewer")
    result = await db.execute(
        select(Document)
        .where(Document.knowledge_base_id == kb_id)
        .order_by(Document.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{kb_id}/documents/{document_id}", response_model=DocumentResponse)
async def get_document_endpoint(
    kb_id: UUID, document_id: UUID,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await require_kb_access(db, kb_id, user.id, "viewer")
    document = await db.get(Document, document_id)
    if document is None or document.knowledge_base_id != kb_id:
        raise HTTPException(404, "Document not found")
    return document


@router.post("/{kb_id}/search", response_model=list[SearchHitResponse])
async def search_endpoint(
    kb_id: UUID, request: SearchRequest,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    hits = await search_chunks(db, kb_id, user.id, request.query, top_k=request.top_k)
    return [SearchHitResponse(**hit.__dict__) for hit in hits]


@router.post("/{kb_id}/ask", response_model=AnswerResponse)
async def ask_endpoint(
    kb_id: UUID, request: QuestionRequest,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    answer = await answer_question(db, kb_id, user, request.question, top_k=request.top_k)
    return AnswerResponse(
        answer=answer.answer,
        no_evidence=answer.no_evidence,
        citations=[CitationResponse(**citation.__dict__) for citation in answer.citations],
    )
