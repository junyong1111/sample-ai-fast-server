from src.app.user.model import User
from src.app.user.repository import UserRepository
from src.config import settings


class UserService:
    def __init__(self, logger):
        self.logger = logger
        self.user_repository = UserRepository(logger)



    # async def get_user_by_id(self, id: str):
    #     return await self.user_repository.get_user_by_id(
    #         id=id,
    #         # session=session
    #     )

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

