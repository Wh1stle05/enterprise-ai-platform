import hashlib

from httpx import AsyncClient


async def test_upload_returns_pending_provenance(client: AsyncClient, tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(
        "app.api.v1.endpoints.knowledge_base.process_document_task.delay", lambda _: None
    )
    registered = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "upload-owner",
            "email": "upload-owner@example.com",
            "password": "secret123",
        },
    )
    token = registered.json()["access_token"]
    created = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "HR", "description": "Policies"},
        headers={"Authorization": f"Bearer {token}"},
    )
    response = await client.post(
        f"/api/v1/knowledge-bases/{created.json()['id']}/documents",
        files={"file": ("../../policy.md", b"# Leave\nFive days", "text/markdown")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["checksum"] == hashlib.sha256(b"# Leave\nFive days").hexdigest()
    assert ".." not in body["storage_uri"]
