from enum import Enum
from pydantic import BaseModel

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"

class User(BaseModel):
    id: str
    password: str
    name: str
    memo: str
    role: UserRole = UserRole.USER


class UserLoginRequest(BaseModel):
    user_id: str
    password: str