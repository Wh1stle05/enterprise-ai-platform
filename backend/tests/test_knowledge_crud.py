from httpx import AsyncClient


async def test_create_knowledge_base_uses_json_body(client: AsyncClient):
    registered = await client.post(
        "/api/v1/auth/register",
        json={"username": "alice-kb", "email": "alice-kb@example.com", "password": "secret123"},
    )
    response = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "HR", "description": "Policies"},
        headers={"Authorization": f"Bearer {registered.json()['access_token']}"},
    )
    assert response.status_code == 201
    assert response.json()["access_level"] == "owner"
