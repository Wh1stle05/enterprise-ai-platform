"""Auth endpoints: register, login, refresh."""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    get_current_user,
)
from app.core.config import settings
from app.models import User

router = APIRouter()


@router.post("/register")
async def register(username: str, email: str, password: str, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    # Check existing
    result = await db.execute(select(User).where((User.username == username) | (User.email == email)))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username or email already exists")

    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    token = create_access_token(sub=str(user.id))
    return {"access_token": token, "token_type": "bearer", "user": {"id": str(user.id), "username": user.username, "email": user.email}}


@router.post("/login")
async def login(username: str, password: str, db: AsyncSession = Depends(get_db)):
    """Login with username and password."""
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(sub=str(user.id))
    return {"access_token": token, "token_type": "bearer", "user": {"id": str(user.id), "username": user.username, "email": user.email}}


@router.get("/me")
async def get_me(payload: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get current user info."""
    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"id": str(user.id), "username": user.username, "email": user.email, "display_name": user.display_name}
