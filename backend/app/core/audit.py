"""Redacted audit persistence and retention helpers."""

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import AuditLog

_SENSITIVE = re.compile(r"password|secret|token|api[_-]?key|authorization", re.IGNORECASE)
_MAX_LENGTH = 4000


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if _SENSITIVE.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str):
        return value[:_MAX_LENGTH]
    return value


def serialize(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value[:_MAX_LENGTH]
    return json.dumps(redact(value), default=str)[:_MAX_LENGTH]


async def record_audit(
    db: AsyncSession,
    *,
    action_type: str,
    user_id=None,
    input_data: Any = None,
    output: Any = None,
    tool_used: str | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        action_type=action_type[:32],
        input=serialize(input_data),
        output=serialize(output),
        tool_used=tool_used[:128] if tool_used else None,
        ip_address=ip_address,
        retention_days=settings.AUDIT_RETENTION_DAYS,
    )
    db.add(entry)
    await db.flush()
    return entry


async def purge_expired_logs(db: AsyncSession, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    rows = (await db.execute(select(AuditLog))).scalars().all()
    expired = []
    for row in rows:
        created_at = row.created_at
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if created_at and created_at < now - timedelta(days=row.retention_days):
            expired.append(row.id)
    if expired:
        result = await db.execute(delete(AuditLog).where(AuditLog.id.in_(expired)))
        return result.rowcount or 0
    return 0
