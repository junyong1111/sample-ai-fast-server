import os
from typing import Final
from dotenv import load_dotenv

load_dotenv()

def getenv(key: str, default: str = None) -> str:
    v: str | None = os.getenv(key)
    if v is None and default is not None:
        return default
    assert v is not None, f"Setting {key} is not found"
    return v

class DatabaseConfig:
    # PostGreSQL 설정
    POSTGRESQL_DB_HOST: Final[str] = getenv("POSTGRESQL_DB_HOST", "localhost")
    POSTGRESQL_DB_PORT: Final[str] = getenv("POSTGRESQL_DB_PORT", "5432")
    POSTGRESQL_DB_DATABASE: Final[str] = getenv("POSTGRESQL_DB_DATABASE", "autotrading")
    POSTGRESQL_DB_USER: Final[str] = getenv("POSTGRESQL_DB_USER", "devjun")
    POSTGRESQL_DB_PASSWORD: Final[str] = getenv("POSTGRESQL_DB_PASSWORD", "")

    # MongoDB 설정 추가
    MONGODB_URL: Final[str] = getenv('MONGODB_URL', "mongodb://localhost:27017")
    MONGODB_DATABASE: Final[str] = getenv('MONGODB_DATABASE', "autotrading")

# 인스턴스 생성
database_config = DatabaseConfig()