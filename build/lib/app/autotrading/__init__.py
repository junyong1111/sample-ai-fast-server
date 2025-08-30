"""
자동매매 시스템 모듈 v2.0

이 모듈은 바이낸스와 업비트를 동시에 지원하는 자동매매 시스템을 제공합니다.
요구사항에 완벽하게 충족하는 6가지 규칙을 구현했습니다:

1. 모멘텀 기반: 누적 수익률 +10% 이상, Sharpe ratio > 0
2. 거래량 증가: Z-score >= 1.0
3. 변동성 대비 수익률: >= 1.0 매수, <= -1.0 매도
4. RSI(14): < 30 매수, > 70 매도
5. 볼린저 밴드: %B < 0.1 매수, > 0.9 매도, bandwidth 신뢰도
6. MACD: 시그널 선 상향/하향 돌파

도메인별로 분리된 서비스들을 포함합니다:
- MarketDataServiceFactory: 거래소별 데이터 서비스 팩토리
- BinanceMarketDataService: 바이낸스 데이터 수집
- UpbitMarketDataService: 업비트 데이터 수집
- TechnicalAnalysisService: 기술적 지표 계산
- SignalGenerationService: 거래 신호 생성
- AutotradingService: 메인 자동매매 서비스
"""

from .model import (
    # 거래소 타입
    ExchangeType,

    # 데이터 수집 모델
    KlineData, MarketDataRequest, MarketDataResponse,

    # 기술적 지표 모델
    TechnicalIndicators,

    # 신호 생성 모델
    TradingSignal, SignalAnalysis, SignalResponse,

    # 거래 실행 모델
    TradeOrder, TradeResult,

    # 데이터 저장 모델
    StoredKlineData, StoredSignal,

    # API 응답 모델
    HealthResponse, ExchangeStatus
)

from .service import (
    # 거래소별 데이터 서비스
    BaseMarketDataService, BinanceMarketDataService, UpbitMarketDataService,
    MarketDataServiceFactory,

    # 기술적 분석 서비스
    TechnicalAnalysisService,

    # 신호 생성 서비스
    SignalGenerationService,

    # 메인 자동매매 서비스
    AutotradingService
)

__all__ = [
    # 모델
    "ExchangeType",
    "KlineData", "MarketDataRequest", "MarketDataResponse",
    "TechnicalIndicators", "TradingSignal", "SignalAnalysis", "SignalResponse",
    "TradeOrder", "TradeResult", "StoredKlineData", "StoredSignal",
    "HealthResponse", "ExchangeStatus",

    # 서비스
    "BaseMarketDataService", "BinanceMarketDataService", "UpbitMarketDataService",
    "MarketDataServiceFactory", "TechnicalAnalysisService",
    "SignalGenerationService", "AutotradingService"
]
