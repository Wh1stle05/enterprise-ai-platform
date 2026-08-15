from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeBaseACL, User

ACCESS_RANK = {"viewer": 10, "editor": 20, "owner": 30}


async def get_kb_access(db: AsyncSession, kb_id: UUID, user_id: UUID) -> str | None:
    return (
        await db.execute(
            select(KnowledgeBaseACL.access_level).where(
                KnowledgeBaseACL.knowledge_base_id == kb_id,
                KnowledgeBaseACL.subject_id == user_id,
            )
        )
    ).scalar_one_or_none()


async def require_kb_access(db: AsyncSession, kb_id: UUID, user_id: UUID, minimum: str) -> str:
    access = await get_kb_access(db, kb_id, user_id)
    if access is None:
        raise HTTPException(404, "Knowledge base not found")
    if ACCESS_RANK[access] < ACCESS_RANK[minimum]:
        raise HTTPException(403, "Insufficient knowledge base access")
    return access


async def list_acl(db: AsyncSession, kb_id: UUID, actor_id: UUID):
    await require_kb_access(db, kb_id, actor_id, "owner")
    return (
        await db.execute(
            select(KnowledgeBaseACL, User.username)
            .join(User, User.id == KnowledgeBaseACL.subject_id)
            .where(KnowledgeBaseACL.knowledge_base_id == kb_id)
            .order_by(KnowledgeBaseACL.created_at)
        )
    ).all()


async def upsert_acl(
    db: AsyncSession, kb_id: UUID, actor_id: UUID, subject_id: UUID, access_level: str
):
    await require_kb_access(db, kb_id, actor_id, "owner")
    subject = await db.get(User, subject_id)
    if not subject:
        raise HTTPException(404, "User not found")
    entry = await db.get(KnowledgeBaseACL, (kb_id, subject_id))
    if entry is None:
        entry = KnowledgeBaseACL(
            knowledge_base_id=kb_id, subject_id=subject_id, access_level=access_level
        )
        db.add(entry)
    elif subject_id == actor_id and entry.access_level == "owner" and access_level != "owner":
        raise HTTPException(409, "An owner cannot remove their own owner access")
    else:
        entry.access_level = access_level
    await db.flush()
    return entry, subject.username


async def delete_acl(db: AsyncSession, kb_id: UUID, actor_id: UUID, subject_id: UUID) -> None:
    await require_kb_access(db, kb_id, actor_id, "owner")
    entry = await db.get(KnowledgeBaseACL, (kb_id, subject_id))
    if entry is None:
        raise HTTPException(404, "ACL entry not found")
    if subject_id == actor_id and entry.access_level == "owner":
        raise HTTPException(409, "An owner cannot remove their own owner access")
    await db.delete(entry)
