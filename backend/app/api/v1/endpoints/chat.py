from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models import User
from app.schemas.chat import (
    ConversationCreate,
    ConversationListItem,
    ConversationResponse,
    MessageResponse,
)
from app.services.chat_service import create_conversation, list_conversations, list_messages

router = APIRouter()


@router.get("/conversations", response_model=list[ConversationListItem])
async def list_conversations_endpoint(
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_conversations(str(user.id), db, limit=limit, offset=offset)


@router.post(
    "/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED
)
async def create_conversation_endpoint(
    req: ConversationCreate,
    user: User = Depends(require_roles("admin", "user")),
    db: AsyncSession = Depends(get_db),
):
    return await create_conversation(str(user.id), req, db)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages_endpoint(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_messages(conversation_id, str(user.id), db)
