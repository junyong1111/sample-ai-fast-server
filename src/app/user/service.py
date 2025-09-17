from src.common.error import JSendError
from src.common.utils.response import JSendResponse
from src.common.error import ErrorCode
from src.common.utils.auth import get_md5_hash
from src.app.user.model import User
from src.app.user.repository import UserRepository
from src.config import settings
from src.package.db import connection


class UserService:
    def __init__(self, logger):
        self.logger = logger
        self.user_repository = UserRepository(logger)

    async def get_user_by_user_idx(self, user_idx: int):
        async with connection() as session:
            user = await self.user_repository.get_user_by_user_idx(
                session=session,
                user_idx=user_idx,
            )
        self.logger.info(f"유저 조회 결과: {user}")
        return user

    async def get_user_by_user_id(self, user_id: str):
        async with connection() as session:
            user = await self.user_repository.get_user_by_user_id(
                session=session,
                user_id=user_id,
            )
        self.logger.info(f"유저 조회 결과: {user}")
        return user

    async def get_user_by_user_id_and_password(self, user_id: str, user_password: str):
            hash_password = await get_md5_hash(user_password)
            async with connection() as session:
                user = await self.user_repository.get_user_by_user_id_and_password(
                    session=session,
                    user_id=user_id,
                    user_password=hash_password,
                )
            self.logger.info(f"유저 조회 결과: {user}")
            return user

    async def create_user(self, user: User):
        self.logger.info(
            f"""
                [유저 등록 요청]
                id: {user.id}
                name: {user.name}
                role: {user.role}
            """
        )
        #1. 해당 유저 중복 확인
        async with connection() as session:
            user_obj = await self.user_repository.get_user_by_user_id(
                user_id=user.id,
                session=session
            )
            if user_obj:
                raise Exception("이미 존재하는 유저입니다.")
        #2. 유저 등록
        hash_password = await get_md5_hash(user.password)
        user.password = hash_password

        async with connection() as session:
            ret = await self.user_repository.create_user(
                session=session,
                user=user
            )
        if not ret :
            self.logger.error("유저 등록 실패")
            raise JSendError(
                code=ErrorCode.User.USER_CREATE_FAIL[0],
                message=ErrorCode.User.USER_CREATE_FAIL[1],
            )
        self.logger.info("유저 등록 성공")
        return user

    async def login(self, user_id: str, password: str):
        user_obj = await self.get_user_by_user_id_and_password(user_id, password)
        if not user_obj:
            self.logger.error("유저 로그인 실패")
            raise JSendError(
                code=ErrorCode.User.USER_NOT_FOUND[0],
                message=ErrorCode.User.USER_NOT_FOUND[1],
            )
        self.logger.info("유저 로그인 성공")
        return user_obj

    async def get_user_trading_info(self, user_idx: int) -> JSendResponse:
        async with connection() as session:
            user_obj = await self.user_repository.get_user_trading_by_user_idx(
                session=session,
                user_idx=user_idx,
            )
        if not user_obj:
            self.logger.error("유저 트레이딩 정보 조회 실패")
            raise JSendError(
                code=ErrorCode.User.USER_NOT_FOUND[0],
                message=ErrorCode.User.USER_NOT_FOUND[1],
            )
        self.logger.info("유저 트레이딩 정보 조회 성공")
        result = dict(user_obj) if user_obj else None
        # Record 객체를 딕셔너리로 변환하고 Decimal을 float로 변환
        return JSendResponse(
            status="success",
            message="유저 트레이딩 정보 조회 성공",
            data=result,
        )
    async def get_user_exchange_by_user_idx(self, user_idx: int):
        async with connection() as session:
            user_obj = await self.user_repository.get_user_exchange_by_user_idx(
                session=session,
                user_idx=user_idx,
            )
        return user_obj