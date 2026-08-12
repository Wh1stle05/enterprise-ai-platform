import asyncio
import logging
from contextlib import asynccontextmanager
from uuid import uuid4

import redis.asyncio
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import api_router
from app.core.audit import purge_expired_logs
from app.core.config import settings
from app.core.database import async_session_factory, engine
from app.middleware.audit import AuditMiddleware
from app.services.embedding_service import (
    EmbeddingConfigurationError,
    EmbeddingDimensionError,
    EmbeddingResponseError,
)
from app.services.errors import build_error_payload
from app.services.llm_service import LLMConfigurationError

api_logger = logging.getLogger("app.api")

REQUEST_ID_HEADER = "X-Request-ID"
MAX_REQUEST_ID_LENGTH = 128
READY_REDIS_TIMEOUT_SECONDS = 2.0


def sanitize_request_id(value: str | None) -> str | None:
    """只信任“看起来安全”的调用方 request id。

    非空、长度 1..128、每个字符必须在 ASCII 0x21..0x7e（不含空格/控制字符/Unicode）；
    不 strip 原值：含首尾空白视为非法。不符合条件的值一律丢弃，
    由中间件重新生成 uuid4 hex。
    """
    if not value:
        return None
    if not 1 <= len(value) <= MAX_REQUEST_ID_LENGTH:
        return None
    if not all(33 <= ord(char) <= 126 for char in value):
        return None
    return value


async def check_database() -> None:
    """DB readiness：执行 SELECT 1，失败时抛异常由 /ready 兜底。"""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def check_redis() -> None:
    """Redis readiness：ping 带 2 秒有界超时，确保关闭连接。"""
    client = redis.asyncio.Redis.from_url(settings.REDIS_URL)
    try:
        await asyncio.wait_for(client.ping(), timeout=READY_REDIS_TIMEOUT_SECONDS)
    finally:
        await client.aclose()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_session_factory() as db:
        try:
            await purge_expired_logs(db)
            await db.commit()
        except Exception:
            await db.rollback()
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuditMiddleware)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    # 优先透传调用方携带的 X-Request-ID；缺失或非法（超长、含不可打印字符等）时
    # 生成 uuid4 hex。写入 request.state 供异常处理器与下游中间件读取。
    request_id = sanitize_request_id(request.headers.get(REQUEST_ID_HEADER)) or uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(request: Request, exc: StarletteHTTPException):
    request_id = getattr(request.state, "request_id", None)
    headers = dict(exc.headers or {})
    if request_id:
        headers[REQUEST_ID_HEADER] = request_id
    detail = exc.detail
    if isinstance(detail, dict):
        # 受控 detail：{"code": ..., "message": ...} 允许显式错误码，
        # message 仍然只取受控字段，不把内部细节暴露给客户端。
        code = detail.get("code")
        message = detail.get("message", "Request failed")
    else:
        code = None
        message = detail if isinstance(detail, str) else "Request failed"
    if exc.status_code in {204, 304}:
        return Response(status_code=exc.status_code, headers=headers or None)
    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_payload(exc.status_code, message, request_id, code=code),
        headers=headers or None,
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError):
    # 422 统一走 invalid_request 信封，不把字段级校验细节暴露给客户端。
    request_id = getattr(request.state, "request_id", None)
    api_logger.warning(
        "request validation failed: path=%s request_id=%s errors=%d",
        request.url.path,
        request_id,
        len(exc.errors()),
    )
    return JSONResponse(
        status_code=422,
        content=build_error_payload(422, "Invalid request", request_id),
        headers={REQUEST_ID_HEADER: request_id} if request_id else None,
    )


@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception):
    # 通用兜底：不向客户端暴露 traceback / 内部细节，只记录 request_id 便于关联日志。
    request_id = getattr(request.state, "request_id", None)
    api_logger.error(
        "unhandled exception: path=%s request_id=%s",
        request.url.path,
        request_id,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content=build_error_payload(500, "Internal server error", request_id),
        headers={REQUEST_ID_HEADER: request_id} if request_id else None,
    )


@app.exception_handler(LLMConfigurationError)
async def handle_llm_configuration_error(request: Request, exc: LLMConfigurationError):
    request_id = getattr(request.state, "request_id", None)
    api_logger.error(
        "llm configuration error: path=%s request_id=%s error=%r",
        request.url.path,
        request_id,
        exc,
    )
    return JSONResponse(
        status_code=503,
        content=build_error_payload(503, "LLM service is not configured", request_id),
        headers={REQUEST_ID_HEADER: request_id} if request_id else None,
    )


@app.exception_handler(EmbeddingConfigurationError)
async def handle_embedding_configuration_error(request: Request, exc: EmbeddingConfigurationError):
    request_id = getattr(request.state, "request_id", None)
    api_logger.error(
        "embedding configuration error: path=%s request_id=%s error=%r",
        request.url.path,
        request_id,
        exc,
    )
    return JSONResponse(
        status_code=503,
        content=build_error_payload(503, "Embedding service is not configured", request_id),
        headers={REQUEST_ID_HEADER: request_id} if request_id else None,
    )


@app.exception_handler(EmbeddingResponseError)
async def handle_embedding_response_error(request: Request, exc: EmbeddingResponseError):
    request_id = getattr(request.state, "request_id", None)
    api_logger.error(
        "embedding response error: path=%s request_id=%s error=%r",
        request.url.path,
        request_id,
        exc,
    )
    return JSONResponse(
        status_code=502,
        content=build_error_payload(
            502, "Embedding provider returned an invalid response", request_id
        ),
        headers={REQUEST_ID_HEADER: request_id} if request_id else None,
    )


@app.exception_handler(EmbeddingDimensionError)
async def handle_embedding_dimension_error(request: Request, exc: EmbeddingDimensionError):
    request_id = getattr(request.state, "request_id", None)
    api_logger.error(
        "embedding dimension error: path=%s request_id=%s error=%r",
        request.url.path,
        request_id,
        exc,
    )
    return JSONResponse(
        status_code=502,
        content=build_error_payload(
            502, "Embedding provider returned an unexpected dimension", request_id
        ),
        headers={REQUEST_ID_HEADER: request_id} if request_id else None,
    )


app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health():
    # liveness 探针：只表示进程还活着，不依赖数据库 / Redis / provider。
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/ready")
async def ready():
    # readiness 探针：数据库与 Redis 全部可用才返回 200；任一失败返回 503，
    # 结构与成功一致（{"status", "checks"}），绝不抛 500。
    checks: dict[str, str] = {}
    for name, check in (("database", check_database), ("redis", check_redis)):
        try:
            await check()
            checks[name] = "ok"
        except Exception:
            checks[name] = "error"
    all_ok = all(value == "ok" for value in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ready" if all_ok else "not_ready", "checks": checks},
    )
