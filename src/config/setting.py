import os
from pathlib import Path
from typing import Final
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

def getenv(key: str, default: str = None) -> str:
    v: str | None = os.getenv(key)
    if v is None and default is not None:
        return default
    assert v is not None, f"Setting {key} is not found"
    return v

class Settings(BaseSettings):
    # 기본 앱 설정
    STAGE: Final[str] = getenv('STAGE', "development")

    # 로그 및 파일 경로 설정
    ERR_LOG_PATH: Final[str] = getenv('ERR_LOG_PATH', "./logs/error")
    TMP_FILE_PATH: Final[str] = getenv('TMP_FILE_PATH', "./tmp")
    DEFAULT_LOGGING_PATH: Final[str] = getenv('DEFAULT_LOGGING_PATH', "./logs")

    # 외부 API 키 설정
    OPENAI_API_KEY: Final[str] = getenv('OPENAI_API_KEY', "")

    # MongoDB 설정 (기존 코드 호환성을 위해)
    MONGODB_URL: Final[str] = getenv('MONGODB_URL', "mongodb://localhost:27017")
    MONGODB_DATABASE: Final[str] = getenv('MONGODB_DATABASE', "autotrading")

    # PostgreSQL 설정 (기존 코드 호환성을 위해)
    POSTGRESQL_DB_HOST: Final[str] = getenv('POSTGRESQL_DB_HOST', "localhost")
    POSTGRESQL_DB_PORT: Final[str] = getenv('POSTGRESQL_DB_PORT', "5432")
    POSTGRESQL_DB_DATABASE: Final[str] = getenv('POSTGRESQL_DB_DATABASE', "autotrading")
    POSTGRESQL_DB_USER: Final[str] = getenv('POSTGRESQL_DB_USER', "devjun")
    POSTGRESQL_DB_PASSWORD: Final[str] = getenv('POSTGRESQL_DB_PASSWORD', "X7pQa9Lm!")

    #JWT 설정
    JWT_SECRET_KEY: Final[str] = getenv('JWT_SECRET_KEY', "mpTLtWzsJ9G5KRCzIr1BRsJ3kWifMaHE3GIlPS6ttmk")
    JWT_ALGORITHM: Final[str] = getenv('JWT_ALGORITHM', "HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: Final[int] = getenv('JWT_ACCESS_TOKEN_EXPIRE_MINUTES', 30)
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: Final[int] = getenv('JWT_REFRESH_TOKEN_EXPIRE_DAYS', 7)

    #Reddit 설정
    REDDIT_CLIENT_ID: Final[str] = getenv('REDDIT_CLIENT_ID', "")
    REDDIT_CLIENT_SECRET: Final[str] = getenv('REDDIT_CLIENT_SECRET', "")
    REDDIT_USER_AGENT: Final[str] = getenv('REDDIT_USER_AGENT', "QuantumInsight/1.0 by YourUsername")

    #Perplexity 설정
    PERPLEXITY_API_KEY: Final[str] = getenv('PERPLEXITY_API_KEY', "")

    # 데이터베이스 설정 (PoolCreate 클래스와 호환되도록 수정)
    @property
    def DATABASES(self):
        return {
            "DATABASE": {
                "default": {
                    "DB_HOST": getenv("POSTGRESQL_DB_HOST", "localhost"),
                    "DB_PORT": int(getenv("POSTGRESQL_DB_PORT", "5432")),
                    "DB_NAME": getenv("POSTGRESQL_DB_DATABASE", "autotrading"),
                    "DB_USER": getenv("POSTGRESQL_DB_USER", "devjun"),
                    "DB_PASSWORD": getenv("POSTGRESQL_DB_PASSWORD", "X7pQa9Lm!"),
                }
            },
            "default": "default"
        }

    # 각 설정 모듈을 속성으로 가져오기
    @property
    def database(self):
        from .database import database_config
        return database_config

    @property
    def autotrading(self):
        from .autotrading import autotrading_config
        return autotrading_config

    model_config = {
        "extra": "allow",  # 추가 필드 허용
        "env_file": f"{Path(__file__).parent.parent}/.env"
    }

# 인스턴스 생성
settings = Settings()


