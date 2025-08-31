import os
from pathlib import Path

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    STAGE: str = os.getenv('STAGE', "development")

    ERR_LOG_PATH: str = os.getenv('ERR_LOG_PATH', "./logs/error")
    TMP_FILE_PATH: str = os.getenv('TMP_FILE_PATH', "./tmp")
    DEFAULT_LOGGING_PATH: str = os.getenv('DEFAULT_LOGGING_PATH', "./logs")
    OPENAI_API_KEY: str = os.getenv('OPENAI_API_KEY', "")

    BINANCE_BASE_URL: str = os.getenv('BINANCE_BASE_URL', "https://api.binance.com")
    TA_WINDOW: int = int(os.getenv('TA_WINDOW', "20"))
    TA_INTERVAL: str = os.getenv('TA_INTERVAL', "1d")
    TA_LIMIT: int = int(os.getenv('TA_LIMIT', "200"))

    BEAR_PERIOD_IN_DAYS: int = int(os.getenv('BEAR_PERIOD_IN_DAYS', "21"))
    BULL_PERIOD_IN_DAYS: int = int(os.getenv('BULL_PERIOD_IN_DAYS', "3"))
    HOLD_PERIOD_IN_DAYS: int = int(os.getenv('HOLD_PERIOD_IN_DAYS', "7"))
    START_DATE: str = os.getenv('START_DATE', "2020-01-01")
    END_DATE: str = os.getenv('END_DATE', "2025-01-01")

    RISK_PER_TRADE: float = float(os.getenv('RISK_PER_TRADE', "0.01"))
    STOP_LOSS_PERCENT: float = float(os.getenv('STOP_LOSS_PERCENT', "0.02"))
    TAKE_PROFIT_PERCENT: float = float(os.getenv('TAKE_PROFIT_PERCENT', "0.05"))

    # MongoDB 설정 추가
    MONGODB_URL: str = os.getenv('MONGODB_URL', "mongodb://localhost:27017")
    MONGODB_DATABASE: str = os.getenv('MONGODB_DATABASE', "autotrading")

    # Binance

    # Binance 설정 추가
    BINANCE_URL: str = os.getenv('BINANCE_URL', "https://api.binance.com")
    BINANCE_API_KEY: str = os.getenv('BINANCE_API_KEY', "")
    BINANCE_SECRET_KEY: str = os.getenv('BINANCE_SECRET_KEY', "")

    # Binance Testnet 설정 추가
    BINANCE_TESTNET_URL: str = os.getenv('BINANCE_TESTNET_URL', "https://testnet.binance.vision")
    BINANCE_TESTNET_API_KEY: str = os.getenv('BINANCE_TESTNET_API_KEY', "")
    BINANCE_TESTNET_SECRET_KEY: str = os.getenv('BINANCE_TESTNET_SECRET_KEY', "")

    # 업비트 API 설정 추가
    UPBIT_BASE_URL: str = os.getenv('UPBIT_BASE_URL', "https://api.upbit.com")

    class Config:
        # .env 파일 경로를 현재 작업 디렉토리 기준으로 수정
        config_path = Path(__file__)
        print(f"config_path: {config_path}")
        env_file = f"{config_path.parent.parent}/.env"


settings = Settings()


