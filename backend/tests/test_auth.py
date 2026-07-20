from httpx import AsyncClient

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"


class TestRegister:
    async def test_register_success(self, client: AsyncClient):
        payload = {"username": "testuser", "email": "test@example.com", "password": "secret123"}
        resp = await client.post(REGISTER_URL, json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "testuser"
        assert data["user"]["email"] == "test@example.com"
        assert data["user"]["role"] == "user"
        assert "access_token" in data
        assert "id" in data["user"]

    async def test_register_duplicate_username(self, client: AsyncClient):
        payload = {"username": "dupuser", "email": "dup1@example.com", "password": "secret123"}
        resp1 = await client.post(REGISTER_URL, json=payload)
        assert resp1.status_code == 201

        payload2 = {"username": "dupuser", "email": "dup2@example.com", "password": "secret123"}
        resp2 = await client.post(REGISTER_URL, json=payload2)
        assert resp2.status_code == 409

    async def test_register_duplicate_email(self, client: AsyncClient):
        payload = {"username": "user1", "email": "same@example.com", "password": "secret123"}
        await client.post(REGISTER_URL, json=payload)

        payload2 = {"username": "user2", "email": "same@example.com", "password": "secret123"}
        resp2 = await client.post(REGISTER_URL, json=payload2)
        assert resp2.status_code == 409

    async def test_register_invalid_email(self, client: AsyncClient):
        payload = {"username": "baduser", "email": "not-an-email", "password": "secret123"}
        resp = await client.post(REGISTER_URL, json=payload)
        assert resp.status_code == 422

    async def test_register_short_password(self, client: AsyncClient):
        payload = {"username": "shortpw", "email": "short@example.com", "password": "12"}
        resp = await client.post(REGISTER_URL, json=payload)
        assert resp.status_code == 422

    async def test_register_short_username(self, client: AsyncClient):
        payload = {"username": "ab", "email": "ab@example.com", "password": "secret123"}
        resp = await client.post(REGISTER_URL, json=payload)
        assert resp.status_code == 422


class TestLogin:
    async def _register_user(self, client: AsyncClient) -> dict:
        payload = {"username": "loginuser", "email": "login@example.com", "password": "secret123"}
        resp = await client.post(REGISTER_URL, json=payload)
        assert resp.status_code == 201
        return resp.json()

    async def test_login_success(self, client: AsyncClient):
        await self._register_user(client)
        resp = await client.post(LOGIN_URL, json={"username": "loginuser", "password": "secret123"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "loginuser"
        assert "access_token" in data

    async def test_login_wrong_password(self, client: AsyncClient):
        await self._register_user(client)
        resp = await client.post(LOGIN_URL, json={"username": "loginuser", "password": "wrongpass"})
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        resp = await client.post(LOGIN_URL, json={"username": "nobody", "password": "secret123"})
        assert resp.status_code == 401

    async def test_login_missing_field(self, client: AsyncClient):
        resp = await client.post(LOGIN_URL, json={"username": "test"})
        assert resp.status_code == 422


class TestMe:
    async def _register_and_get_token(self, client: AsyncClient) -> str:
        payload = {"username": "meuser", "email": "me@example.com", "password": "secret123"}
        resp = await client.post(REGISTER_URL, json=payload)
        assert resp.status_code == 201
        return resp.json()["access_token"]

    async def test_me_success(self, client: AsyncClient):
        token = await self._register_and_get_token(client)
        resp = await client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "meuser"
        assert data["email"] == "me@example.com"

    async def test_me_no_token(self, client: AsyncClient):
        resp = await client.get(ME_URL)
        assert resp.status_code == 401

    async def test_me_invalid_token(self, client: AsyncClient):
        resp = await client.get(ME_URL, headers={"Authorization": "Bearer invalidtoken"})
        assert resp.status_code == 401
