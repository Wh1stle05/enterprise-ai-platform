from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field
from typing import Literal

Role = Literal["admin", "user", "viewer"]


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    role: Role = "user"
    display_name: str | None = None
    is_superuser: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
