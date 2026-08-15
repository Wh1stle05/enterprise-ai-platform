from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, KnowledgeBase, KnowledgeBaseACL, User
from app.schemas.knowledge import KnowledgeBaseCreate
from app.services.knowledge_acl_service import require_kb_access


async def create_knowledge_base(user: User, request: KnowledgeBaseCreate, db: AsyncSession):
    kb = KnowledgeBase(user_id=user.id, name=request.name, description=request.description)
    db.add(kb)
    await db.flush()
    db.add(KnowledgeBaseACL(knowledge_base_id=kb.id, subject_id=user.id, access_level="owner"))
    await db.flush()
    return kb


async def list_knowledge_bases(user: User, db: AsyncSession):
    count = func.count(Document.id).label("document_count")
    return (
        await db.execute(
            select(KnowledgeBase, KnowledgeBaseACL.access_level, count)
            .join(KnowledgeBaseACL, KnowledgeBaseACL.knowledge_base_id == KnowledgeBase.id)
            .outerjoin(Document, Document.knowledge_base_id == KnowledgeBase.id)
            .where(KnowledgeBaseACL.subject_id == user.id)
            .group_by(KnowledgeBase.id, KnowledgeBaseACL.access_level)
            .order_by(KnowledgeBase.updated_at.desc())
        )
    ).all()


async def get_knowledge_base(kb_id: UUID, user: User, db: AsyncSession):
    access = await require_kb_access(db, kb_id, user.id, "viewer")
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if kb is None:
        raise ValueError("Knowledge base not found")
    count = (
        await db.execute(select(func.count(Document.id)).where(Document.knowledge_base_id == kb_id))
    ).scalar_one()
    return kb, access, count


async def delete_knowledge_base(kb_id: UUID, user: User, db: AsyncSession):
    await require_kb_access(db, kb_id, user.id, "owner")
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise ValueError("Knowledge base not found")
    await db.delete(kb)
