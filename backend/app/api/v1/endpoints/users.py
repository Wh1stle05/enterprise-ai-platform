from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.schemas.auth import UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_profile(
    user = Depends(get_current_user),
):
    return UserResponse.model_validate(user)
