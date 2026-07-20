
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth_service import get_user_by_id, login, register

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_endpoint(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    return await register(req, db)


@router.post("/login", response_model=TokenResponse)
async def login_endpoint(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await login(req, db)


@router.get("/me", response_model=UserResponse)
async def get_me(
    user = Depends(get_current_user),
):
    return UserResponse.model_validate(user)
