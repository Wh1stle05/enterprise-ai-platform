"""Fail-open request audit middleware."""

import logging
from uuid import UUID

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.audit import record_audit
from app.core.config import settings
from app.core.database import async_session_factory

logger = logging.getLogger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
        except Exception:
            raise
        try:
            user_id = None
            authorization = request.headers.get("authorization", "")
            if authorization.lower().startswith("bearer "):
                token = authorization[7:]
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                user_id = UUID(payload["sub"])
            action = (
                "query"
                if request.method == "GET"
                else "admin"
                if "/users" in request.url.path
                else "request"
            )
            factory = getattr(request.app.state, "audit_session_factory", async_session_factory)
            async with factory() as db:
                await record_audit(
                    db,
                    action_type=action,
                    user_id=user_id,
                    input_data={"method": request.method, "path": request.url.path},
                    output={"status_code": response.status_code},
                    ip_address=request.client.host if request.client else None,
                )
                await db.commit()
        except (JWTError, KeyError, ValueError):
            pass
        except Exception:
            logger.exception("Audit persistence failed")
        return response
