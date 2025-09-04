from src.app.user.model import User


class UserRepository:
    def __init__(self, logger):
        self.logger = logger
        pass

    async def get_user_by_id(
            self, id: str, session):
        return await session.get(User, id)

    def create_user(self, user: User):
        pass