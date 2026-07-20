from httpx import AsyncClient

REGISTER_URL = "/api/v1/auth/register"
CONVERSATIONS_URL = "/api/v1/chat/conversations"


async def test_viewer_cannot_create_conversation(client: AsyncClient, db_session):
    response = await client.post(
        REGISTER_URL,
        json={"username": "viewer1", "email": "viewer1@example.com", "password": "secret123"},
    )
    token = response.json()["access_token"]
    response = await client.post(CONVERSATIONS_URL, json={}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
