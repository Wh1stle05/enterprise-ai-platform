from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse


async def register(req: RegisterRequest, db: AsyncSession) -> TokenResponse:
    result = await db.execute(
        select(User).where((User.username == req.username) | (User.email == req.email))
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        )

    user = User(
        username=req.username,
        email=req.email,
        hashed_password=hash_password(req.password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    token = create_access_token(sub=str(user.id), role=user.role)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


async def login(req: LoginRequest, db: AsyncSession) -> TokenResponse:
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_access_token(sub=str(user.id), role=user.role)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


async def get_user_by_id(user_id: str, db: AsyncSession) -> User | None:
    uid = UUID(user_id)
    result = await db.execute(select(User).where(User.id == uid))
    return result.scalar_one_or_none()
