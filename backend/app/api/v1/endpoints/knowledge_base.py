"""Knowledge base CRUD and resource ACL endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models import User
from app.schemas.knowledge import ACLResponse, ACLUpsert, KnowledgeBaseCreate, KnowledgeBaseResponse
from app.services.knowledge_acl_service import delete_acl, list_acl, upsert_acl
from app.services.knowledge_service import (
    create_knowledge_base,
    delete_knowledge_base,
    get_knowledge_base,
    list_knowledge_bases,
)

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
