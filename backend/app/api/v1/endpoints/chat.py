from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models import User
from app.services.llm_service import LLMConfigurationError
from app.schemas.chat import (
    ConversationCreate,
    ConversationListItem,
    ConversationResponse,
    MessageCreate,
    MessageSendResponse,
    MessageResponse,
)
from app.services.chat_service import (
    create_conversation,
    delete_conversation,
    list_conversations,
    list_messages,
    send_message,
)

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


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageSendResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message_endpoint(
    conversation_id: str,
    req: MessageCreate,
    user: User = Depends(require_roles("admin", "user")),
    db: AsyncSession = Depends(get_db),
):
    try:
        messages = await send_message(conversation_id, str(user.id), req.content, db)
    except LLMConfigurationError:
        raise HTTPException(status_code=503, detail="LLM service is not configured")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="LLM provider request failed")
    return MessageSendResponse(messages=messages)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation_endpoint(
    conversation_id: str,
    user: User = Depends(require_roles("admin", "user")),
    db: AsyncSession = Depends(get_db),
):
    await delete_conversation(conversation_id, str(user.id), db)
