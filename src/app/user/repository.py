from src.app.user.model import User


class UserRepository:
    def __init__(self, logger):
        self.logger = logger
        pass

    async def get_user_by_user_id(
            self,
            session,
            user_id: str,
            status: bool = True
    ):
        query = """
            SELECT id, user_id
            FROM user_master
            WHERE user_id = $1
                AND status = $2
        """
        return await session.fetchrow(query, user_id, status)
    async def get_user_by_user_id_and_password(self, session, user_id: str, user_password: str, status: bool = True):
        query = """
            SELECT id, user_id
            FROM user_master
            WHERE user_id = $1
                AND password = $2
                AND status = $3
        """
        return await session.fetchrow(query, user_id, user_password, status)


    async def create_user(self, session, user: User):
        query = """
            INSERT INTO user_master (user_id, password, name, memo, role, created_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
        """
        return await session.execute(query, user.id, user.password, user.name, user.memo, user.role)