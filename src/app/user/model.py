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
    binance_api_key: str | None = None
    binance_api_secret: str | None = None
    upbit_api_key: str | None = None
    upbit_api_secret: str | None = None

