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

class AutotradingConfig:
    # 기술적 분석 설정
    TA_WINDOW: Final[int] = int(getenv('TA_WINDOW', "20"))
    TA_INTERVAL: Final[str] = getenv('TA_INTERVAL', "1d")
    TA_LIMIT: Final[int] = int(getenv('TA_LIMIT', "200"))

    # 거래 기간 설정
    BEAR_PERIOD_IN_DAYS: Final[int] = int(getenv('BEAR_PERIOD_IN_DAYS', "21"))
    BULL_PERIOD_IN_DAYS: Final[int] = int(getenv('BULL_PERIOD_IN_DAYS', "3"))
    HOLD_PERIOD_IN_DAYS: Final[int] = int(getenv('HOLD_PERIOD_IN_DAYS', "7"))
    START_DATE: Final[str] = getenv('START_DATE', "2020-01-01")
    END_DATE: Final[str] = getenv('END_DATE', "2025-01-01")

    # 리스크 관리 설정
    RISK_PER_TRADE: Final[float] = float(getenv('RISK_PER_TRADE', "0.01"))
    STOP_LOSS_PERCENT: Final[float] = float(getenv('STOP_LOSS_PERCENT', "0.02"))
    TAKE_PROFIT_PERCENT: Final[float] = float(getenv('TAKE_PROFIT_PERCENT', "0.05"))

    # Binance 설정
    # BINANCE_BASE_URL: Final[str] = getenv('BINANCE_BASE_URL', "https://api.binance.com")
    # BINANCE_URL: Final[str] = getenv('BINANCE_URL', "https://api.binance.com")
    # BINANCE_API_KEY: Final[str] = getenv('BINANCE_API_KEY', "")
    # BINANCE_SECRET_KEY: Final[str] = getenv('BINANCE_SECRET_KEY', "")

    # # Binance Testnet 설정
    # BINANCE_TESTNET_URL: Final[str] = getenv('BINANCE_TESTNET_URL', "https://testnet.binance.vision")
    # BINANCE_TESTNET_API_KEY: Final[str] = getenv('BINANCE_TESTNET_API_KEY', "")
    # BINANCE_TESTNET_SECRET_KEY: Final[str] = getenv('BINANCE_TESTNET_SECRET_KEY', "")

    # # 업비트 API 설정
    # UPBIT_BASE_URL: Final[str] = getenv('UPBIT_BASE_URL', "https://api.upbit.com")

# 인스턴스 생성
autotrading_config = AutotradingConfig()
