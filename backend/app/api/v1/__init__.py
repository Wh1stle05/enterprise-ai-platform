"""V1 API router — aggregate all endpoint modules."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, chat, knowledge_base, users

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
api_router.include_router(
    knowledge_base.router, prefix="/knowledge-bases", tags=["Knowledge Bases"]
)
