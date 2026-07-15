from httpx import AsyncClient

REGISTER_URL = "/api/v1/auth/register"
CONVERSATIONS_URL = "/api/v1/chat/conversations"


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
