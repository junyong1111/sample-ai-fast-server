from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal
from enum import Enum

# ===== 거래소 타입 =====
class ExchangeType(str, Enum):
    """지원하는 거래소 타입"""
    BINANCE = "binance"
    UPBIT = "upbit"

# ===== 데이터 수집 모델 =====
class KlineData(BaseModel):
    """K라인 데이터 (거래소 공통)"""
    open_time: datetime = Field(..., description="시작 시간 (UTC)")
    open: Decimal = Field(..., description="시가")
    high: Decimal = Field(..., description="고가")
    low: Decimal = Field(..., description="저가")
    close: Decimal = Field(..., description="종가")
    volume: Decimal = Field(..., description="거래량")
    close_time: datetime = Field(..., description="종료 시간 (UTC)")
    quote_volume: Optional[Decimal] = Field(None, description="기준화폐 거래량 (바이낸스만)")
    trades: Optional[int] = Field(None, description="거래 횟수 (바이낸스만)")
    taker_buy_base: Optional[Decimal] = Field(None, description="테이커 매수 기준화폐 (바이낸스만)")
    taker_buy_quote: Optional[Decimal] = Field(None, description="테이커 매수 기준화폐 (바이낸스만)")
    exchange: ExchangeType = Field(..., description="거래소")
    symbol: str = Field(..., description="거래 심볼")

class MarketDataRequest(BaseModel):
    """시장 데이터 요청"""
    symbol: str = Field(
        ...,
        description="거래 심볼",
        examples=[
            "BTCUSDT",  # 바이낸스
            "KRW-BTC",  # 업비트
            "ETHUSDT",
            "KRW-ETH"
        ]
    )
    interval: str = Field(
        ...,
        description="시간 간격",
        examples=[
            "1m", "5m", "15m", "30m",  # 분봉
            "1h", "4h", "6h", "12h",   # 시간봉
            "1d", "3d", "1w", "1M"     # 일봉, 주봉, 월봉
        ]
    )
    limit: int = Field(
        200,
        ge=50,
        le=1000,
        description="데이터 개수 (최소 50, 최대 1000)"
    )
    exchange: ExchangeType = Field(
        ...,
        description="거래소 선택",
        examples=["binance", "upbit"]
    )

    class Config:
        schema_extra = {
            "example": {
                "symbol": "BTCUSDT",
                "interval": "1d",
                "limit": 200,
                "exchange": "binance"
            }
        }

class MarketDataResponse(BaseModel):
    """시장 데이터 응답"""
    exchange: ExchangeType = Field(..., description="거래소")
    symbol: str = Field(..., description="거래 심볼")
    interval: str = Field(..., description="시간 간격")
    klines: List[KlineData] = Field(..., description="K라인 데이터 리스트")
    count: int = Field(..., description="데이터 개수")
    timestamp: datetime = Field(..., description="응답 생성 시간")

# ===== 기술적 지표 모델 (요구사항 완벽 충족) =====
class TechnicalIndicators(BaseModel):
    """기술적 지표 결과"""
    # 1. 모멘텀 기반
    momentum_cumret: Optional[float] = Field(None, description="20일 누적 수익률 (예: 0.15 = 15%)")
    momentum_sharpe_like: Optional[float] = Field(None, description="Sharpe ratio 유사 지표 (수익률/변동성)")

    # 2. 거래량 증가
    volume_z: Optional[float] = Field(None, description="거래량 Z-score (1.0 이상이면 거래량 급증)")

    # 3. 변동성 대비 수익률
    return_over_vol: Optional[float] = Field(None, description="수익률/변동성 (1.0 이상이면 매수 신호)")

    # 4. RSI
    rsi_14: Optional[float] = Field(None, description="RSI(14) 지표 (30 이하면 과매도, 70 이상이면 과매수)")

    # 5. 볼린저 밴드
    bb_pct_b: Optional[float] = Field(None, description="볼린저 밴드 %B (0.1 이하면 매수, 0.9 이상이면 매도)")
    bb_bandwidth: Optional[float] = Field(None, description="볼린저 밴드 대역폭 (0.06 이상이면 신뢰도 높음)")
    bb_upper: Optional[float] = Field(None, description="볼린저 밴드 상단선")
    bb_lower: Optional[float] = Field(None, description="볼린저 밴드 하단선")
    bb_middle: Optional[float] = Field(None, description="볼린저 밴드 중간선 (20일 이동평균)")

    # 6. MACD
    macd: Optional[float] = Field(None, description="MACD 라인")
    macd_signal: Optional[float] = Field(None, description="MACD 시그널 라인")
    macd_hist: Optional[float] = Field(None, description="MACD 히스토그램")
    macd_cross: Optional[str] = Field(None, description="MACD 크로스 (bullish/bearish/none)")

    # 기본 지표들
    sma_20: Optional[float] = Field(None, description="20일 단순이동평균")
    ema_12: Optional[float] = Field(None, description="12일 지수이동평균")
    ema_26: Optional[float] = Field(None, description="26일 지수이동평균")
    volume_sma: Optional[float] = Field(None, description="20일 거래량 이동평균")

# ===== 신호 생성 모델 =====
class TradingSignal(BaseModel):
    """거래 신호"""
    action: Literal["BUY", "SELL", "HOLD"] = Field(..., description="거래 액션")
    confidence: float = Field(..., ge=0.0, le=1.0, description="신뢰도 (0.0~1.0)")
    score: float = Field(..., ge=-1.0, le=1.0, description="종합 점수 (-1.0~1.0)")
    timestamp: datetime = Field(..., description="신호 생성 시간")
    symbol: str = Field(..., description="거래 심볼")
    interval: str = Field(..., description="시간 간격")
    exchange: ExchangeType = Field(..., description="거래소")

class SignalAnalysis(BaseModel):
    """신호 분석 결과 (6가지 규칙 완벽 구현)"""
    # 1. 모멘텀 기반
    rule1_momentum: Literal["buy", "neutral"] = Field("neutral", description="모멘텀 규칙 신호")
    momentum_score: float = Field(0.0, description="모멘텀 점수")

    # 2. 거래량 증가
    rule2_volume: Literal["buy", "neutral"] = Field("neutral", description="거래량 규칙 신호")
    volume_score: float = Field(0.0, description="거래량 점수")

    # 3. 변동성 대비 수익률
    rule3_ret_over_vol: Literal["buy", "sell", "neutral"] = Field("neutral", description="수익률/변동성 규칙 신호")
    ret_vol_score: float = Field(0.0, description="수익률/변동성 점수")

    # 4. RSI
    rule4_rsi: Literal["buy", "sell", "neutral"] = Field("neutral", description="RSI 규칙 신호")
    rsi_score: float = Field(0.0, description="RSI 점수")

    # 5. 볼린저 밴드
    rule5_bollinger: Literal["buy", "buy_strong", "sell", "sell_strong", "neutral"] = Field("neutral", description="볼린저 밴드 규칙 신호")
    bollinger_score: float = Field(0.0, description="볼린저 밴드 점수")

    # 6. MACD
    rule6_macd: Literal["buy", "sell", "neutral"] = Field("neutral", description="MACD 규칙 신호")
    macd_score: float = Field(0.0, description="MACD 점수")

    # 종합 점수
    overall_score: float = Field(0.0, description="종합 점수 (-1.0~1.0)")
    recommendation: Literal["BUY", "SELL", "HOLD"] = Field("HOLD", description="최종 추천")
    confidence: float = Field(0.0, description="전체 신뢰도")

class SignalResponse(BaseModel):
    """신호 응답"""
    exchange: ExchangeType = Field(..., description="거래소")
    symbol: str = Field(..., description="거래 심볼")
    interval: str = Field(..., description="시간 간격")
    timestamp: datetime = Field(..., description="응답 생성 시간")
    signal: TradingSignal = Field(..., description="거래 신호")
    analysis: SignalAnalysis = Field(..., description="신호 분석 결과")
    indicators: TechnicalIndicators = Field(..., description="기술적 지표")

# ===== 거래 실행 모델 =====
class TradeOrder(BaseModel):
    """거래 주문"""
    exchange: ExchangeType = Field(..., description="거래소")
    symbol: str = Field(..., description="거래 심볼")
    side: Literal["BUY", "SELL"] = Field(..., description="거래 방향")
    quantity: Decimal = Field(..., description="거래 수량")
    price: Optional[Decimal] = Field(None, description="거래 가격 (None이면 시장가)")
    order_type: Literal["MARKET", "LIMIT"] = Field("MARKET", description="주문 타입")
    timestamp: datetime = Field(..., description="주문 시간")

    class Config:
        schema_extra = {
            "example": {
                "exchange": "binance",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "quantity": "0.001",
                "price": "50000",
                "order_type": "LIMIT",
                "timestamp": "2024-01-01T00:00:00Z"
            }
        }

class TradeResult(BaseModel):
    """거래 결과"""
    order_id: str = Field(..., description="주문 ID")
    exchange: ExchangeType = Field(..., description="거래소")
    status: Literal["PENDING", "FILLED", "CANCELLED", "REJECTED"] = Field(..., description="주문 상태")
    filled_quantity: Optional[Decimal] = Field(None, description="체결 수량")
    filled_price: Optional[Decimal] = Field(None, description="체결 가격")
    commission: Optional[Decimal] = Field(None, description="수수료")
    timestamp: datetime = Field(..., description="거래 시간")

# ===== 데이터 저장 모델 =====
class StoredKlineData(BaseModel):
    """저장된 K라인 데이터"""
    id: Optional[str] = Field(None, description="MongoDB ObjectId")
    exchange: ExchangeType = Field(..., description="거래소")
    symbol: str = Field(..., description="거래 심볼")
    interval: str = Field(..., description="시간 간격")
    open_time: datetime = Field(..., description="시작 시간")
    open: Decimal = Field(..., description="시가")
    high: Decimal = Field(..., description="고가")
    low: Decimal = Field(..., description="저가")
    close: Decimal = Field(..., description="종가")
    volume: Decimal = Field(..., description="거래량")
    close_time: datetime = Field(..., description="종료 시간")
    created_at: datetime = Field(default_factory=datetime.now, description="저장 시간")

class StoredSignal(BaseModel):
    """저장된 신호 데이터"""
    id: Optional[str] = Field(None, description="MongoDB ObjectId")
    exchange: ExchangeType = Field(..., description="거래소")
    symbol: str = Field(..., description="거래 심볼")
    interval: str = Field(..., description="시간 간격")
    timestamp: datetime = Field(..., description="신호 생성 시간")
    signal_data: SignalResponse = Field(..., description="신호 데이터")
    created_at: datetime = Field(default_factory=datetime.now, description="저장 시간")

# ===== API 응답 모델 =====
class HealthResponse(BaseModel):
    """헬스 체크 응답"""
    status: str = Field(..., description="서비스 상태")
    timestamp: datetime = Field(..., description="체크 시간")
    version: str = Field(..., description="API 버전")
    exchanges: List[ExchangeType] = Field(..., description="지원하는 거래소 목록")

class ExchangeStatus(BaseModel):
    """거래소별 상태"""
    exchange: ExchangeType = Field(..., description="거래소")
    status: str = Field(..., description="거래소 상태")
    last_update: datetime = Field(..., description="마지막 업데이트 시간")
    symbols_count: int = Field(..., description="지원 심볼 개수")


