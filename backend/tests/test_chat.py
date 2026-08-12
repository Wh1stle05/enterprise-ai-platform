from unittest.mock import AsyncMock, patch
from uuid import uuid4

from httpx import AsyncClient

from app.agent.loop import AgentTurnResult

REGISTER_URL = "/api/v1/auth/register"
CONVERSATIONS_URL = "/api/v1/chat/conversations"


def _turn(answer: str = "pong") -> AgentTurnResult:
    return AgentTurnResult(run_id=uuid4(), status="completed", answer=answer, step_count=1)


class TestConversations:
    async def _register_and_get_token(self, client: AsyncClient) -> str:
        payload = {"username": "chatuser", "email": "chat@example.com", "password": "secret123"}
        resp = await client.post(REGISTER_URL, json=payload)
        assert resp.status_code == 201
        return resp.json()["access_token"]

    async def _auth_header(self, client: AsyncClient) -> dict:
        token = await self._register_and_get_token(client)
        return {"Authorization": f"Bearer {token}"}

    async def test_create_conversation(self, client: AsyncClient):
        headers = await self._auth_header(client)
        resp = await client.post(CONVERSATIONS_URL, json={"title": "My Chat"}, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "My Chat"
        assert "id" in data
        assert "created_at" in data

    async def test_create_conversation_default_title(self, client: AsyncClient):
        headers = await self._auth_header(client)
        resp = await client.post(CONVERSATIONS_URL, json={}, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["title"] == "New Conversation"

    async def test_list_conversations_empty(self, client: AsyncClient):
        headers = await self._auth_header(client)
        resp = await client.get(CONVERSATIONS_URL, headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_send_message_persists_user_and_assistant(self, client: AsyncClient):
        headers = await self._auth_header(client)
        conv_id = (await client.post(CONVERSATIONS_URL, json={}, headers=headers)).json()["id"]
        with patch(
            "app.api.v1.endpoints.chat.start_agent_turn",
            new=AsyncMock(return_value=_turn()),
        ):
            resp = await client.post(
                f"{CONVERSATIONS_URL}/{conv_id}/messages",
                json={"content": "hello"},
                headers=headers,
            )
        assert resp.status_code == 201
        # M3 contract: AgentTurnResponse, not the old MessageSendResponse.messages.
        data = resp.json()
        assert set(data) == {"run_id", "status", "answer", "tool_call", "step_count", "elapsed_ms"}
        assert data["answer"] == "pong"
        assert data["status"] == "completed"
        assert data["run_id"]
        # Both messages must be persisted and visible via GET /messages.
        messages = await client.get(f"{CONVERSATIONS_URL}/{conv_id}/messages", headers=headers)
        assert messages.status_code == 200
        assert [(m["role"], m["content"]) for m in messages.json()] == [
            ("user", "hello"),
            ("assistant", "pong"),
        ]

    async def test_list_conversations(self, client: AsyncClient):
        headers = await self._auth_header(client)
        await client.post(CONVERSATIONS_URL, json={"title": "Chat 1"}, headers=headers)
        await client.post(CONVERSATIONS_URL, json={"title": "Chat 2"}, headers=headers)
        resp = await client.get(CONVERSATIONS_URL, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    async def test_list_conversations_pagination(self, client: AsyncClient):
        headers = await self._auth_header(client)
        for i in range(5):
            await client.post(CONVERSATIONS_URL, json={"title": f"Chat {i}"}, headers=headers)
        resp = await client.get(f"{CONVERSATIONS_URL}?limit=2&offset=0", headers=headers)
        assert len(resp.json()) == 2

    async def test_conversation_with_message_count(self, client: AsyncClient):
        headers = await self._auth_header(client)
        await client.post(CONVERSATIONS_URL, json={"title": "Count Test"}, headers=headers)
        resp = await client.get(CONVERSATIONS_URL, headers=headers)
        assert resp.json()[0]["message_count"] == 0

    async def test_list_conversations_requires_auth(self, client: AsyncClient):
        resp = await client.get(CONVERSATIONS_URL)
        assert resp.status_code == 401


class TestMessages:
    async def _register_and_get_token(self, client: AsyncClient, suffix: str = "") -> str:
        payload = {
            "username": f"msger{suffix}",
            "email": f"msg{suffix}@example.com",
            "password": "secret123",
        }
        resp = await client.post(REGISTER_URL, json=payload)
        assert resp.status_code == 201
        return resp.json()["access_token"]

    async def _auth_header(self, client: AsyncClient, suffix: str = "") -> dict:
        token = await self._register_and_get_token(client, suffix)
        return {"Authorization": f"Bearer {token}"}

    async def _create_conversation(self, client: AsyncClient, headers: dict) -> str:
        resp = await client.post(CONVERSATIONS_URL, json={"title": "Msg Test"}, headers=headers)
        return resp.json()["id"]

    async def test_list_messages_empty(self, client: AsyncClient):
        headers = await self._auth_header(client)
        conv_id = await self._create_conversation(client, headers)
        resp = await client.get(f"{CONVERSATIONS_URL}/{conv_id}/messages", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_messages_unauthorized(self, client: AsyncClient):
        headers_a = await self._auth_header(client, suffix="a")
        conv_id = await self._create_conversation(client, headers_a)
        headers_b = await self._auth_header(client, suffix="b")
        resp = await client.get(
            f"{CONVERSATIONS_URL}/{conv_id}/messages",
            headers=headers_b,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_send_two_turns_passes_latest_history_to_agent(self, client: AsyncClient):
        headers = await self._auth_header(client, suffix="turns")
        conv_id = await self._create_conversation(client, headers)
        with patch(
            "app.api.v1.endpoints.chat.start_agent_turn",
            new=AsyncMock(return_value=_turn()),
        ) as agent:
            first = await client.post(
                f"{CONVERSATIONS_URL}/{conv_id}/messages",
                json={"content": "ping"},
                headers=headers,
            )
            second = await client.post(
                f"{CONVERSATIONS_URL}/{conv_id}/messages",
                json={"content": "again"},
                headers=headers,
            )
        assert first.status_code == 201
        assert second.status_code == 201
        assert agent.await_args_list[0].kwargs["history"] == [{"role": "user", "content": "ping"}]
        assert agent.await_args_list[1].kwargs["history"] == [
            {"role": "user", "content": "ping"},
            {"role": "assistant", "content": "pong"},
            {"role": "user", "content": "again"},
        ]

    async def test_send_message_caps_agent_history_at_twenty_messages(self, client: AsyncClient):
        headers = await self._auth_header(client, suffix="history-cap")
        conv_id = await self._create_conversation(client, headers)
        with patch(
            "app.api.v1.endpoints.chat.start_agent_turn",
            new=AsyncMock(return_value=_turn()),
        ) as agent:
            for index in range(11):
                response = await client.post(
                    f"{CONVERSATIONS_URL}/{conv_id}/messages",
                    json={"content": f"message-{index}"},
                    headers=headers,
                )
                assert response.status_code == 201
        history = agent.await_args_list[-1].kwargs["history"]
        assert len(history) == 20
        assert history[0] == {"role": "assistant", "content": "pong"}
        assert history[-1] == {"role": "user", "content": "message-10"}

    async def test_delete_conversation_is_owner_only(self, client: AsyncClient):
        headers_a = await self._auth_header(client, suffix="delete-a")
        conv_id = await self._create_conversation(client, headers_a)
        headers_b = await self._auth_header(client, suffix="delete-b")
        response = await client.delete(f"{CONVERSATIONS_URL}/{conv_id}", headers=headers_b)
        assert response.status_code == 404
        response = await client.delete(f"{CONVERSATIONS_URL}/{conv_id}", headers=headers_a)
        assert response.status_code == 204
