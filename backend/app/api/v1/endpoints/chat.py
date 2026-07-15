from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
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
    payload: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_conversations(payload["sub"], db, limit=limit, offset=offset)


@router.post(
    "/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED
)
async def create_conversation_endpoint(
    req: ConversationCreate,
    payload: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await create_conversation(payload["sub"], req, db)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages_endpoint(
    conversation_id: str,
    payload: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_messages(conversation_id, payload["sub"], db)
