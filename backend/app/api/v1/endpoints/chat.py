"""Chat endpoints — conversations and messages."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Conversation, Message

router = APIRouter()


@router.get("/conversations")
async def list_conversations(
    limit: int = 50,
    offset: int = 0,
    payload: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List conversations for the current user, newest first."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == payload["sub"])
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    convos = result.scalars().all()
    return [
        {"id": str(c.id), "title": c.title, "message_count": 0, "created_at": c.created_at.isoformat()}
        for c in convos
    ]


@router.post("/conversations")
async def create_conversation(
    title: str = "New Conversation",
    payload: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new conversation."""
    conv = Conversation(user_id=payload["sub"], title=title)
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    return {"id": str(conv.id), "title": conv.title, "created_at": conv.created_at.isoformat()}


@router.get("/conversations/{conversation_id}/messages")
async def list_messages(
    conversation_id: str,
    payload: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all messages in a conversation."""
    result = await db.execute(
        select(Message)
        .join(Conversation)
        .where(Conversation.id == conversation_id, Conversation.user_id == payload["sub"])
        .order_by(Message.created_at)
    )
    msgs = result.scalars().all()
    return [
        {"id": str(m.id), "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
        for m in msgs
    ]
