import json
from pathlib import Path
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import AuditLog, Document, DocumentChunk, User
from app.services.document_processing_service import process_document
from app.services.rag_service import RAGAnswer, answer_question
from app.services.retrieval_service import SearchHit


@pytest.mark.asyncio
async def test_m2_flow_is_acl_isolated_and_cited(
    client: AsyncClient, db_session, tmp_path: Path, monkeypatch
):
    monkeypatch.setattr("app.core.config.settings.UPLOAD_DIR", str(tmp_path))

    owner_response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "m2-owner",
            "email": "m2-owner@example.com",
            "password": "secret123",
        },
    )
    viewer_response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "m2-viewer",
            "email": "m2-viewer@example.com",
            "password": "secret123",
        },
    )
    owner_token = owner_response.json()["access_token"]
    viewer_token = viewer_response.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
    viewer_id = UUID(viewer_response.json()["user"]["id"])

    created = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "M2 Policies", "description": "End-to-end test"},
        headers=owner_headers,
    )
    assert created.status_code == 201
    kb_id = UUID(created.json()["id"])

    granted = await client.put(
        f"/api/v1/knowledge-bases/{kb_id}/acl/{viewer_id}",
        json={"access_level": "viewer"},
        headers=owner_headers,
    )
    assert granted.status_code == 200

    scheduled: list[UUID] = []

    def fake_delay(document_id: str) -> None:
        scheduled.append(UUID(document_id))

    monkeypatch.setattr(
        "app.api.v1.endpoints.knowledge_base.process_document_task.delay", fake_delay
    )
    uploaded = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files={"file": ("policy.md", b"# Leave\nFive days", "text/markdown")},
        headers=owner_headers,
    )
    assert uploaded.status_code == 202
    document_id = UUID(uploaded.json()["id"])
    assert scheduled == [document_id]

    async def fake_embedder(texts: list[str]) -> list[list[float]]:
        return [[0.1] * 1536 for _ in texts]

    processing_sessions = async_sessionmaker(
        db_session.bind, class_=AsyncSession, expire_on_commit=False
    )
    await process_document(
        document_id,
        db_factory=processing_sessions,
        embedder=fake_embedder,
    )

    document = await db_session.get(Document, document_id)
    assert document is not None
    assert document.status == "ready"
    assert document.parser_version == "m2-1"
    assert document.embedding_dim == 1536
    assert document.chunk_count > 0

    chunk = await db_session.scalar(
        select(DocumentChunk).where(DocumentChunk.document_id == document.id)
    )
    assert chunk is not None
    hit = SearchHit(
        chunk_id=chunk.id,
        document_id=document.id,
        filename=document.filename,
        chunk_index=0,
        content="Five days of annual leave are provided.",
        source_locator="document",
        score=0.95,
    )

    async def fake_searcher(*args, **kwargs) -> list[SearchHit]:
        return [hit]

    async def fake_completer(messages) -> str:
        return "Employees receive five days of annual leave [S1]."

    owner = await db_session.scalar(select(User).where(User.username == "m2-owner"))
    assert owner is not None
    answer = await answer_question(
        db_session,
        kb_id,
        owner,
        "How much leave?",
        searcher=fake_searcher,
        completer=fake_completer,
    )
    assert isinstance(answer, RAGAnswer)
    assert "[S1]" in answer.answer
    assert [citation.label for citation in answer.citations] == ["[S1]"]

    audit_rows = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action_type == "knowledge_query")
        )
    ).scalars().all()
    assert audit_rows
    audit_output = json.loads(audit_rows[-1].output)
    assert audit_output["cited_chunk_ids"] == [str(chunk.id)]
    assert audit_output["chunks"][0]["score"] == 0.95

    viewer_upload = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files={"file": ("other.md", b"No upload", "text/markdown")},
        headers=viewer_headers,
    )
    assert viewer_upload.status_code == 403
    viewer_delete = await client.delete(
        f"/api/v1/knowledge-bases/{kb_id}", headers=viewer_headers
    )
    assert viewer_delete.status_code == 403
