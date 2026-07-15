from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message
from app.schemas.chat import (
    ConversationCreate,
    ConversationListItem,
    ConversationResponse,
    MessageResponse,
)


async def list_conversations(
    user_id: str,
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> list[ConversationListItem]:
    uid = UUID(user_id)
    subq = (
        select(Message.conversation_id, func.count().label("cnt"))
        .group_by(Message.conversation_id)
        .subquery()
    )
    result = await db.execute(
        select(Conversation, subq.c.cnt)
        .outerjoin(subq, Conversation.id == subq.c.conversation_id)
        .where(Conversation.user_id == uid)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = result.all()
    return [
        ConversationListItem(
            id=str(conv.id),
            title=conv.title,
            message_count=cnt or 0,
            created_at=conv.created_at,
        )
        for conv, cnt in rows
    ]


async def create_conversation(
    user_id: str,
    req: ConversationCreate,
    db: AsyncSession,
) -> ConversationResponse:
    uid = UUID(user_id)
    conv = Conversation(user_id=uid, title=req.title)
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    return ConversationResponse.model_validate(conv)


async def list_messages(
    conversation_id: str,
    user_id: str,
    db: AsyncSession,
) -> list[MessageResponse]:
    uid = UUID(user_id)
    cid = UUID(conversation_id)
    result = await db.execute(
        select(Message)
        .join(Conversation)
        .where(Conversation.id == cid, Conversation.user_id == uid)
        .order_by(Message.created_at)
    )
    msgs = result.scalars().all()
    return [MessageResponse.model_validate(m) for m in msgs]
