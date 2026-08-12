from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.agent.loop import AgentTurnResult
from app.models import AuditLog


@pytest.mark.asyncio
async def test_m1_core_flow(client: AsyncClient, db_session):
    register = await client.post(
        "/api/v1/auth/register",
        json={"username": "flowuser", "email": "flow@example.com", "password": "secret123"},
    )
    assert register.status_code == 201
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    login = await client.post(
        "/api/v1/auth/login", json={"username": "flowuser", "password": "secret123"}
    )
    assert login.status_code == 200
    conversation = await client.post("/api/v1/chat/conversations", json={}, headers=headers)
    assert conversation.status_code == 201
    conversation_id = conversation.json()["id"]

    with patch(
        "app.api.v1.endpoints.chat.start_agent_turn",
        new=AsyncMock(
            return_value=AgentTurnResult(
                run_id=uuid4(), status="completed", answer="assistant reply"
            )
        ),
    ):
        for content in ("first", "second"):
            response = await client.post(
                f"/api/v1/chat/conversations/{conversation_id}/messages",
                json={"content": content},
                headers=headers,
            )
            assert response.status_code == 201
            # M3 contract: AgentTurnResponse exposes the assistant answer at top level.
            assert response.json()["answer"] == "assistant reply"

    messages = await client.get(
        f"/api/v1/chat/conversations/{conversation_id}/messages", headers=headers
    )
    assert [message["role"] for message in messages.json()] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    deleted = await client.delete(f"/api/v1/chat/conversations/{conversation_id}", headers=headers)
    assert deleted.status_code == 204
    assert (await db_session.execute(select(AuditLog))).scalars().first() is not None
