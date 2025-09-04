import hashlib
from src.app.user.model import User
from src.app.user.repository import UserRepository
from src.config import settings
from src.package.db import connection


class UserService:
    def __init__(self, logger):
        self.logger = logger
        self.user_repository = UserRepository(logger)

    async def get_user_by_user_id(self, user_id: str):
        async with connection() as session:
            user = await self.user_repository.get_user_by_user_id(
                session=session,
                user_id=user_id,
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
            user = await self.user_repository.get_user_by_user_id(
                user_id=user.id,
                session=session
            )
            if user:
                raise Exception("이미 존재하는 유저입니다.")
        #2. 유저 등록
        hash_password = hashlib.sha256(user.password.encode()).hexdigest()
        user.password = hash_password

        async with connection() as session:
            await self.user_repository.create_user(
                session=session,
                user=user
            )


