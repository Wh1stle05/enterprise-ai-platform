from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.audit import purge_expired_logs, redact
from app.models import AuditLog

REGISTER_URL = "/api/v1/auth/register"


@pytest.mark.asyncio
async def test_authenticated_request_creates_redacted_audit_row(client, db_session):
    response = await client.post(
        REGISTER_URL,
        json={"username": "audituser", "email": "audit@example.com", "password": "secret123"},
    )
    token = response.json()["access_token"]
    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    assert rows
    assert all(token not in (row.input or "") + (row.output or "") for row in rows)


def test_redact_sensitive_values():
    value = redact({"password": "secret", "Authorization": "Bearer abc", "query": "hello"})
    assert value == {"password": "[REDACTED]", "Authorization": "[REDACTED]", "query": "hello"}


def test_redact_nested_and_truncates_strings():
    value = redact({"nested": {"api_key": "secret"}, "text": "x" * 5000})
    assert value["nested"]["api_key"] == "[REDACTED]"
    assert len(value["text"]) == 4000


@pytest.mark.asyncio
async def test_purge_expired_logs(db_session):
    now = datetime.now(timezone.utc)
    db_session.add_all([
        AuditLog(action_type="query", created_at=now - timedelta(days=91), retention_days=90),
        AuditLog(action_type="query", created_at=now - timedelta(days=1), retention_days=90),
    ])
    await db_session.commit()
    await purge_expired_logs(db_session, now=now)
    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    assert len(rows) == 1
