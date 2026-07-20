from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.database import async_session_factory
from app.core.audit import purge_expired_logs
from app.middleware.audit import AuditMiddleware


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

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}
