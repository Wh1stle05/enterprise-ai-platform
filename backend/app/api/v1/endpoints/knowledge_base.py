"""Knowledge base endpoints — CRUD + upload + search."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import KnowledgeBase, Document

router = APIRouter()


@router.get("/")
async def list_knowledge_bases(
    payload: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all knowledge bases for the current user."""
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.user_id == payload["sub"]).order_by(KnowledgeBase.updated_at.desc())
    )
    kbs = result.scalars().all()
    return [
        {"id": str(kb.id), "name": kb.name, "description": kb.description, "document_count": 0, "created_at": kb.created_at.isoformat()}
        for kb in kbs
    ]


@router.post("/")
async def create_knowledge_base(
    name: str,
    description: str = "",
    payload: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new knowledge base."""
    kb = KnowledgeBase(user_id=payload["sub"], name=name, description=description)
    db.add(kb)
    await db.flush()
    await db.refresh(kb)
    return {"id": str(kb.id), "name": kb.name, "description": kb.description}


@router.post("/{kb_id}/documents")
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    payload: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a document to a knowledge base."""
    # Verify KB exists and belongs to user
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id, KnowledgeBase.user_id == payload["sub"])
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")

    content = await file.read()
    doc = Document(
        knowledge_base_id=kb.id,
        filename=file.filename or "unknown",
        file_type=file.content_type or "application/octet-stream",
        file_size=len(content),
        status="pending",
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    # Save file to disk
    import aiofiles
    import os
    from app.core.config import settings

    upload_path = os.path.join(settings.UPLOAD_DIR, str(kb.id))
    os.makedirs(upload_path, exist_ok=True)
    file_path = os.path.join(upload_path, f"{doc.id}_{file.filename}")
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    return {"id": str(doc.id), "filename": doc.filename, "status": doc.status, "file_size": doc.file_size}
