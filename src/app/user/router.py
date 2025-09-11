from fastapi import APIRouter, Depends, Request
from src.app.user.model import User, UserLoginRequest
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

@router.post(
    '/login',
    tags=["Users"],
    summary="사용자 로그인",
    description="사용자를 로그인합니다."
)
async def login(
    user: UserLoginRequest,
    user_service: UserService = Depends(get_user_service)
):
    return await user_service.login(user.user_id, user.password)

@router.get(
    "/users/{user_idx}/state}",
    tags=["Users - Trading"],
    summary="트레이딩에 필요한 특정 유저의 계좌 상태를 조회합니다.",
    description="트레이딩에 필요한 특정 유저의 계좌 상태를 조회합니다.",
)
async def get_user_account_state(
        user_idx: int,
        user_service: UserService = Depends(get_user_service)
    ):
    return await user_service.get_user_account_state(user_idx)

