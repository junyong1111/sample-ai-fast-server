from fastapi import APIRouter, Depends, Request
from src.app.user.model import User
from src.app.user.service import UserService
from src.common.utils.logger import set_logger

router = APIRouter(prefix="/users")
logger = set_logger("users")

# 의존성 함수 정의
def get_user_service():
    return UserService(logger)

@router.get(
    "/ping",
    tags=["Users"],
    summary="User Router Ping",
    description="User Router Ping"
)
async def ping():
    return {"status": "pong"}

@router.post(
    '/register',
    tags=["Users"],
    summary="사용자 등록",
    description="사용자를 등록합니다."
)
async def register(
    user: User,
    user_service: UserService = Depends(get_user_service)
):
    return await user_service.create_user(user)