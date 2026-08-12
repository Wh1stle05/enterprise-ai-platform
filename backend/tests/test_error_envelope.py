"""Standardized error envelope and Request-ID contract tests."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select

from app.models import User
from app.services.embedding_service import (
    EmbeddingConfigurationError,
    EmbeddingResponseError,
)
from app.services.llm_service import LLMConfigurationError

REGISTER_URL = "/api/v1/auth/register"
CONVERSATIONS_URL = "/api/v1/chat/conversations"
KNOWLEDGE_BASES_URL = "/api/v1/knowledge-bases"


async def _register(client: AsyncClient, username: str) -> dict:
    resp = await client.post(
        REGISTER_URL,
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "secret123",
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _headers(token: str, request_id: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    if request_id:
        headers["X-Request-ID"] = request_id
    return headers


class TestRequestId:
    async def test_missing_request_id_is_generated(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        request_id = resp.headers.get("X-Request-ID")
        assert request_id
        assert len(request_id) == 32
        # uuid4 hex — must parse as hexadecimal.
        int(request_id, 16)

    async def test_incoming_request_id_is_echoed(self, client: AsyncClient):
        resp = await client.get("/health", headers={"X-Request-ID": "caller-123"})
        assert resp.status_code == 200
        assert resp.headers["X-Request-ID"] == "caller-123"

    async def test_too_long_request_id_is_regenerated(self, client: AsyncClient):
        resp = await client.get("/health", headers={"X-Request-ID": "x" * 200})
        assert resp.status_code == 200
        request_id = resp.headers["X-Request-ID"]
        assert request_id != "x" * 200
        assert len(request_id) == 32

    async def test_non_printable_request_id_is_regenerated(self, client: AsyncClient):
        resp = await client.get("/health", headers={"X-Request-ID": "bad\x00id"})
        assert resp.status_code == 200
        assert len(resp.headers["X-Request-ID"]) == 32

    async def test_request_id_with_space_is_regenerated(self, client: AsyncClient):
        resp = await client.get("/health", headers={"X-Request-ID": "bad id"})
        assert resp.status_code == 200
        request_id = resp.headers["X-Request-ID"]
        assert request_id != "bad id"
        assert len(request_id) == 32

    async def test_request_id_with_leading_trailing_whitespace_is_regenerated(
        self, client: AsyncClient
    ):
        # 不 strip：原值含首尾空格同样非法，必须重新生成而不是回显裁剪后的值。
        resp = await client.get("/health", headers={"X-Request-ID": "  padded  "})
        assert resp.status_code == 200
        request_id = resp.headers["X-Request-ID"]
        assert request_id != "padded"
        assert len(request_id) == 32

    async def test_unicode_request_id_is_regenerated(self, client: AsyncClient):
        # HTTP header 按 latin-1 传输；café 的 é 解码后 ord=233 > 126，属于非 ASCII，
        # 必须重新生成。
        resp = await client.get("/health", headers={"X-Request-ID": "café".encode("latin-1")})
        assert resp.status_code == 200
        request_id = resp.headers["X-Request-ID"]
        assert request_id != "café"
        assert len(request_id) == 32

    async def test_success_response_echoes_request_id(self, client: AsyncClient):
        resp = await client.post(
            REGISTER_URL,
            json={
                "username": "rid-echo",
                "email": "rid-echo@example.com",
                "password": "secret123",
            },
            headers={"X-Request-ID": "echo-me"},
        )
        assert resp.status_code == 201
        assert resp.headers["X-Request-ID"] == "echo-me"

    async def test_error_response_echoes_incoming_request_id(self, client: AsyncClient):
        resp = await client.get(CONVERSATIONS_URL, headers={"X-Request-ID": "caller-401"})
        assert resp.status_code == 401
        assert resp.headers["X-Request-ID"] == "caller-401"
        assert resp.json()["error"]["request_id"] == "caller-401"

    async def test_error_response_request_id_matches_header_when_generated(
        self, client: AsyncClient
    ):
        resp = await client.get(CONVERSATIONS_URL)
        assert resp.status_code == 401
        body = resp.json()
        assert body["error"]["request_id"] == resp.headers["X-Request-ID"]
        assert len(body["error"]["request_id"]) == 32


class TestErrorEnvelope:
    async def test_401_unauthorized_envelope(self, client: AsyncClient):
        resp = await client.get(CONVERSATIONS_URL, headers={"X-Request-ID": "req-401"})
        assert resp.status_code == 401
        body = resp.json()
        assert set(body) == {"error"}
        assert body["error"]["code"] == "unauthorized"
        assert body["error"]["message"]
        assert body["error"]["request_id"] == "req-401"

    async def test_403_forbidden_envelope(self, client: AsyncClient, db_session):
        registered = await _register(client, "viewer-env")
        user = (
            await db_session.execute(select(User).where(User.username == "viewer-env"))
        ).scalar_one()
        user.role = "viewer"
        await db_session.commit()
        resp = await client.post(
            CONVERSATIONS_URL,
            json={},
            headers=_headers(registered["access_token"], "req-403"),
        )
        assert resp.status_code == 403
        body = resp.json()
        assert body["error"]["code"] == "forbidden"
        assert body["error"]["request_id"] == "req-403"

    async def test_404_not_found_envelope(self, client: AsyncClient):
        owner = (await _register(client, "owner-404"))["access_token"]
        other = (await _register(client, "other-404"))["access_token"]
        conv_id = (await client.post(CONVERSATIONS_URL, json={}, headers=_headers(owner))).json()[
            "id"
        ]
        resp = await client.delete(
            f"{CONVERSATIONS_URL}/{conv_id}",
            headers=_headers(other, "req-404"),
        )
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "not_found"
        assert body["error"]["request_id"] == "req-404"

    async def test_422_invalid_request_envelope(self, client: AsyncClient):
        resp = await client.post(
            REGISTER_URL,
            json={"username": "bad-422", "email": "not-an-email", "password": "secret123"},
            headers={"X-Request-ID": "req-422"},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert set(body) == {"error"}
        assert body["error"]["code"] == "invalid_request"
        assert body["error"]["message"] == "Invalid request"
        assert body["error"]["request_id"] == "req-422"
        # Field-level validation details must not leak to the client.
        assert "detail" not in body
        assert "loc" not in body["error"]["message"]

    async def test_409_conflict_envelope(self, client: AsyncClient):
        await _register(client, "dup-409")
        resp = await client.post(
            REGISTER_URL,
            json={"username": "dup-409", "email": "other@example.com", "password": "secret123"},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "conflict"

    async def test_502_upstream_error_envelope(self, client: AsyncClient):
        token = (await _register(client, "upstream-502"))["access_token"]
        conv_id = (await client.post(CONVERSATIONS_URL, json={}, headers=_headers(token))).json()[
            "id"
        ]
        with patch(
            "app.api.v1.endpoints.chat.start_agent_turn",
            new=AsyncMock(side_effect=RuntimeError("provider boom")),
        ):
            resp = await client.post(
                f"{CONVERSATIONS_URL}/{conv_id}/messages",
                json={"content": "hi"},
                headers=_headers(token, "req-502"),
            )
        assert resp.status_code == 502
        body = resp.json()
        assert body["error"]["code"] == "upstream_error"
        assert body["error"]["request_id"] == "req-502"

    async def test_503_service_unavailable_envelope(self, client: AsyncClient):
        token = (await _register(client, "svc-503"))["access_token"]
        conv_id = (await client.post(CONVERSATIONS_URL, json={}, headers=_headers(token))).json()[
            "id"
        ]
        with patch(
            "app.api.v1.endpoints.chat.start_agent_turn",
            new=AsyncMock(side_effect=LLMConfigurationError("missing key")),
        ):
            resp = await client.post(
                f"{CONVERSATIONS_URL}/{conv_id}/messages",
                json={"content": "hi"},
                headers=_headers(token, "req-503"),
            )
        assert resp.status_code == 503
        body = resp.json()
        assert body["error"]["code"] == "service_unavailable"
        assert body["error"]["request_id"] == "req-503"

    async def test_404_message_is_controlled(self, client: AsyncClient):
        # 非法 conversation UUID 走受控的 404 信封，不暴露内部细节。
        resp = await client.get(f"{CONVERSATIONS_URL}/{uuid4()}/tool-calls")
        assert resp.status_code == 401  # unauthenticated first
        token = (await _register(client, "ctrl-404"))["access_token"]
        resp = await client.get(
            f"{CONVERSATIONS_URL}/{uuid4()}/tool-calls", headers=_headers(token)
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "not_found"

    async def test_framework_404_uses_standard_envelope(self, client: AsyncClient):
        # 未匹配路由的 404 由 Starlette 框架抛出，必须同样走标准信封并透传 Request-ID。
        resp = await client.get("/route-that-does-not-exist", headers={"X-Request-ID": "route-404"})
        assert resp.status_code == 404
        body = resp.json()
        assert set(body) == {"error"}
        assert body["error"]["code"] == "not_found"
        assert body["error"]["request_id"] == "route-404"
        assert resp.headers["X-Request-ID"] == body["error"]["request_id"]


class TestEmbeddingBoundary:
    async def _create_kb(self, client: AsyncClient, token: str, name: str) -> str:
        resp = await client.post(
            KNOWLEDGE_BASES_URL,
            json={"name": name, "description": ""},
            headers=_headers(token),
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    async def test_embedding_configuration_error_maps_to_503(self, client: AsyncClient):
        token = (await _register(client, "emb-cfg"))["access_token"]
        kb_id = await self._create_kb(client, token, "emb-cfg-kb")
        with patch(
            "app.api.v1.endpoints.knowledge_base.answer_question",
            new=AsyncMock(side_effect=EmbeddingConfigurationError("no key")),
        ):
            resp = await client.post(
                f"{KNOWLEDGE_BASES_URL}/{kb_id}/ask",
                json={"question": "hi"},
                headers=_headers(token, "req-emb-cfg"),
            )
        assert resp.status_code == 503
        body = resp.json()
        assert body["error"]["code"] == "service_unavailable"
        assert body["error"]["request_id"] == "req-emb-cfg"

    async def test_embedding_response_error_maps_to_502(self, client: AsyncClient):
        token = (await _register(client, "emb-resp"))["access_token"]
        kb_id = await self._create_kb(client, token, "emb-resp-kb")
        with patch(
            "app.api.v1.endpoints.knowledge_base.answer_question",
            new=AsyncMock(side_effect=EmbeddingResponseError("bad response")),
        ):
            resp = await client.post(
                f"{KNOWLEDGE_BASES_URL}/{kb_id}/ask",
                json={"question": "hi"},
                headers=_headers(token),
            )
        assert resp.status_code == 502
        body = resp.json()
        assert body["error"]["code"] == "upstream_error"
        assert "traceback" not in str(body).lower()
