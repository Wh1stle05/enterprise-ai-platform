from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.defaults import build_default_registry
from app.agent.loop import resume_agent_run, start_agent_turn
from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models import AgentRun, Conversation, Message, ToolCall, User
from app.schemas.chat import (
    AgentTurnResponse,
    ConversationCreate,
    ConversationListItem,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
    ToolCallResponse,
    ToolDecisionRequest,
    map_agent_turn,
    map_tool_call,
)
from app.services.chat_service import (
    create_conversation,
    delete_conversation,
    list_conversations,
    list_messages,
)
from app.services.llm_service import LLMConfigurationError

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
    response_model=AgentTurnResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message_endpoint(
    conversation_id: str,
    req: MessageCreate,
    user: User = Depends(require_roles("admin", "user")),
    db: AsyncSession = Depends(get_db),
):
    try:
        conversation_uuid = UUID(conversation_id)
        conversation = (
            await db.execute(
                select(Conversation).where(
                    Conversation.id == conversation_uuid, Conversation.user_id == user.id
                )
            )
        ).scalar_one_or_none()
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        history_rows = (
            (
                await db.execute(
                    select(Message)
                    .where(Message.conversation_id == conversation_uuid)
                    .order_by(Message.created_at.desc(), Message.id.desc())
                    .limit(20)
                )
            )
            .scalars()
            .all()
        )
        db.add(Message(conversation_id=conversation_uuid, role="user", content=req.content))
        await db.flush()
        # History passed to the agent must include the current user message as the
        # last entry and never exceed 20 messages: at most 19 prior messages + current.
        prior_messages = list(reversed(history_rows))
        history = [
            {"role": message.role, "content": message.content} for message in prior_messages[-19:]
        ]
        history.append({"role": "user", "content": req.content})
        result = await start_agent_turn(
            db,
            build_default_registry(),
            conversation_uuid,
            user.id,
            req.content,
            history=history,
        )
        if result.answer:
            db.add(
                Message(conversation_id=conversation_uuid, role="assistant", content=result.answer)
            )
        conversation.updated_at = datetime.now(timezone.utc)
        await db.flush()
    except LLMConfigurationError:
        raise HTTPException(status_code=503, detail="LLM service is not configured")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="LLM provider request failed")
    return map_agent_turn(result)


@router.get("/conversations/{conversation_id}/tool-calls", response_model=list[ToolCallResponse])
async def list_tool_calls_endpoint(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        conversation_uuid = UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation = (
        await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_uuid, Conversation.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    calls = (
        await db.execute(
            select(ToolCall)
            .join(AgentRun, AgentRun.id == ToolCall.run_id)
            .where(AgentRun.conversation_id == conversation_uuid, AgentRun.user_id == user.id)
            .order_by(ToolCall.step_number)
        )
    ).scalars()
    return [map_tool_call(call) for call in calls]


async def _run_id_for_tool_call(db: AsyncSession, tool_call_id: UUID, user_id: UUID) -> UUID:
    run_id = (
        await db.execute(
            select(AgentRun.id)
            .join(ToolCall, ToolCall.run_id == AgentRun.id)
            .where(ToolCall.id == tool_call_id, AgentRun.user_id == user_id)
        )
    ).scalar_one_or_none()
    if run_id is None:
        raise HTTPException(status_code=404, detail="Tool call not found")
    return run_id


@router.post("/tool-calls/{tool_call_id}/decision", response_model=AgentTurnResponse)
async def decide_tool_call_endpoint(
    tool_call_id: str,
    req: ToolDecisionRequest,
    user: User = Depends(require_roles("admin", "user")),
    db: AsyncSession = Depends(get_db),
):
    try:
        tool_call_uuid = UUID(tool_call_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Tool call not found")
    try:
        run_id = await _run_id_for_tool_call(db, tool_call_uuid, user.id)
        result = await resume_agent_run(
            db,
            build_default_registry(),
            run_id,
            str(user.id),
            confirm=req.confirm,
        )
    except LLMConfigurationError:
        raise HTTPException(status_code=503, detail="LLM service is not configured")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="LLM provider request failed")
    return map_agent_turn(result)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation_endpoint(
    conversation_id: str,
    user: User = Depends(require_roles("admin", "user")),
    db: AsyncSession = Depends(get_db),
):
    await delete_conversation(conversation_id, str(user.id), db)
