from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, Literal, List
import pandas as pd

Timeframe = Literal[
    "days",
    "minutes:1", "minutes:3", "minutes:5", "minutes:10",
    "minutes:15", "minutes:30", "minutes:60", "minutes:240"
]

class ExchangeInterface(ABC):
    """거래소 공통 인터페이스"""

    @abstractmethod
    async def get_chart_health(self) -> Dict[str, Any]:
        """거래소 헬스체크"""
        pass

    @abstractmethod
    async def get_ohlcv_df(
        self,
        market: str,
        tf: Timeframe,
        count: int
    ) -> pd.DataFrame:
        """OHLCV 데이터 조회"""
        pass

    @abstractmethod
    def compute_indicators(
        self,
        df: pd.DataFrame,
        momentum_window: int = 20,
        vol_window: int = 20,
        rsi_period: int = 14,
        bb_period: int = 20,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9
    ) -> Dict[str, Any]:
        """기술적 지표 계산"""
        pass

    @abstractmethod
    def rule_signals(self, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """거래 신호 규칙 평가"""
        pass

    @abstractmethod
    async def get_ticker(self, market: str) -> Dict[str, Any]:
        """현재 가격 정보 조회"""
        pass

    @abstractmethod
    async def get_orderbook(self, market: str, limit: int = 20) -> Dict[str, Any]:
        """호가창 정보 조회"""
        pass

    @abstractmethod
    async def get_recent_trades(self, market: str, limit: int = 100) -> List[Dict[str, Any]]:
        """최근 거래 내역 조회"""
        pass


class ExchangeFactory:
    """거래소 팩토리 클래스"""

    @staticmethod
    def create_exchange(
        exchange_type: str,
        api_key: str | None = None,
        secret: str | None = None,
        testnet: bool = False
    ) -> ExchangeInterface:
        """
        거래소 타입에 따라 적절한 인스턴스 생성

        Args:
            exchange_type: 'upbit' 또는 'binance'
            api_key: API 키
            secret: 시크릿 키
            testnet: 테스트넷 사용 여부 (바이낸스만 해당)
        """
        if exchange_type.lower() == "upbit":
            from .upbit import PyUpbitUtils
            return PyUpbitUtils()
        elif exchange_type.lower() == "binance":
            from .binace import BinanceUtils
            return BinanceUtils(api_key=api_key, secret=secret, testnet=testnet)
        else:
            raise ValueError(f"Unsupported exchange type: {exchange_type}. Use 'upbit' or 'binance'")

    @staticmethod
    def get_supported_exchanges() -> List[str]:
        """지원하는 거래소 목록 반환"""
        return ["upbit", "binance"]

    @staticmethod
    def get_exchange_info(exchange_type: str) -> Dict[str, Any]:
        """거래소별 정보 반환"""
        info = {
            "upbit": {
                "name": "Upbit",
                "country": "Korea",
                "markets": ["KRW-BTC", "KRW-ETH", "KRW-XRP"],
                "timeframes": ["minutes:1", "minutes:3", "minutes:5", "minutes:15", "minutes:30", "minutes:60", "minutes:240", "days"],
                "features": ["public_data", "trading", "futures"]
            },
            "binance": {
                "name": "Binance",
                "country": "Global",
                "markets": ["BTC/USDT", "ETH/USDT", "BNB/USDT"],
                "timeframes": ["minutes:1", "minutes:3", "minutes:5", "minutes:15", "minutes:30", "minutes:60", "minutes:240", "days"],
                "features": ["public_data", "trading", "futures", "testnet"]
            }
        }

        if exchange_type.lower() not in info:
            raise ValueError(f"Unknown exchange type: {exchange_type}")

        return info[exchange_type.lower()]
