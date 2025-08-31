from __future__ import annotations

from typing import Dict, Any, List, Literal, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class TradingSignal(BaseModel):
    """거래 신호 데이터 모델"""

    # 기본 정보
    exchange: str = Field(..., description="거래소 (upbit/binance)")
    market: str = Field(..., description="거래 시장 (예: KRW-BTC, BTC/USDT)")
    timeframe: str = Field(..., description="시간프레임 (예: minutes:60)")

    # 타임스탬프
    timestamp: datetime = Field(..., description="신호 생성 시간")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="DB 저장 시간")

    # 가격 정보
    current_price: float = Field(..., description="현재 가격")
    price_change_24h: Optional[float] = Field(None, description="24시간 가격 변동률")
    volume_24h: Optional[float] = Field(None, description="24시간 거래량")

    # 기술적 지표
    rsi: Optional[float] = Field(None, description="RSI 값")
    rsi_period: Optional[int] = Field(None, description="RSI 계산 기간")
    macd_cross: Optional[str] = Field(None, description="MACD 크로스오버 신호")
    bollinger_bands: Optional[Dict[str, float]] = Field(None, description="볼린저 밴드 정보")

    # 거래 신호
    overall_signal: str = Field(..., description="종합 거래 신호 (BUY/SELL/HOLD)")
    signal_strength: Optional[float] = Field(None, description="신호 강도 (0-100)")

    # 개별 규칙 신호
    rule_signals: Dict[str, str] = Field(default_factory=dict, description="개별 규칙별 신호")

    # 추가 메타데이터
    parameters: Dict[str, Any] = Field(default_factory=dict, description="사용된 파라미터들")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TradingSignalCreate(BaseModel):
    """거래 신호 생성용 모델"""

    exchange: str
    market: str
    timeframe: str
    current_price: float
    overall_signal: str

    # 선택적 필드들
    rsi: Optional[float] = None
    rsi_period: Optional[int] = None
    macd_cross: Optional[str] = None
    bollinger_bands: Optional[Dict[str, float]] = None
    signal_strength: Optional[float] = None
    rule_signals: Optional[Dict[str, str]] = None
    parameters: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class TradingSignalResponse(BaseModel):
    """거래 신호 응답 모델"""

    # 기본 응답
    exchange: str
    market: str
    current_price: float
    overall_signal: str
    timeframe: str
    timestamp: datetime

    # 상세 지표 데이터 (에이전트용)
    indicators: Dict[str, Any] = Field(..., description="모든 기술적 지표 데이터")
    rule_evaluation: Dict[str, Any] = Field(..., description="규칙 평가 결과")
    signal_details: Dict[str, Any] = Field(..., description="신호 상세 정보")

    # 파라미터 정보
    parameters_used: Dict[str, Any] = Field(..., description="사용된 파라미터들")

    # 메타데이터
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TradingSignalQuery(BaseModel):
    """거래 신호 조회용 쿼리 모델"""

    exchange: Optional[str] = Field(None, description="거래소 필터")
    market: Optional[str] = Field(None, description="시장 필터")
    timeframe: Optional[str] = Field(None, description="시간프레임 필터")
    signal: Optional[str] = Field(None, description="신호 타입 필터 (BUY/SELL/HOLD)")
    start_date: Optional[datetime] = Field(None, description="시작 날짜")
    end_date: Optional[datetime] = Field(None, description="종료 날짜")
    limit: int = Field(default=100, description="조회 개수 제한")
    skip: int = Field(default=0, description="건너뛸 개수")


class TradingSignalStats(BaseModel):
    """거래 신호 통계 모델"""

    total_signals: int = Field(..., description="총 신호 개수")
    signal_distribution: Dict[str, int] = Field(..., description="신호별 분포")
    exchange_distribution: Dict[str, int] = Field(..., description="거래소별 분포")
    market_distribution: Dict[str, int] = Field(..., description="시장별 분포")
    timeframe_distribution: Dict[str, int] = Field(..., description="시간프레임별 분포")

    # 성공률 통계
    success_rate: Optional[float] = Field(None, description="예측 성공률")
    avg_signal_strength: Optional[float] = Field(None, description="평균 신호 강도")

    # 시간별 통계
    hourly_distribution: Optional[Dict[str, int]] = Field(None, description="시간대별 분포")
    daily_distribution: Optional[Dict[str, int]] = Field(None, description="일별 분포")


class TradingExecution(BaseModel):
    """거래 실행 결과 모델"""

    # 기본 정보
    exchange: str = Field(..., description="거래소 (upbit/binance)")
    market: str = Field(..., description="거래 시장 (예: BTC/USDT)")
    testnet: bool = Field(..., description="테스트넷 사용 여부")

    # AI 신호 정보
    ai_signal: Dict[str, Any] = Field(..., description="AI가 보낸 거래 신호")
    signal_confidence: Optional[float] = Field(None, description="AI 신호 신뢰도")
    signal_reason: Optional[str] = Field(None, description="AI 신호 이유")

    # 거래 실행 정보
    action: str = Field(..., description="거래 방향 (BUY/SELL/HOLD)")
    quantity: float = Field(..., description="거래 수량")
    order_type: str = Field(..., description="주문 타입 (market/limit)")
    price: Optional[float] = Field(None, description="거래 가격")

    # 거래 결과
    order_id: Optional[str] = Field(None, description="주문 ID")
    order_status: Optional[str] = Field(None, description="주문 상태")
    execution_price: Optional[float] = Field(None, description="실행 가격")
    execution_time: Optional[datetime] = Field(None, description="실행 시간")

    # 타임스탬프
    timestamp: datetime = Field(..., description="거래 신호 생성 시간")
    executed_at: Optional[datetime] = Field(None, description="거래 실행 시간")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="DB 저장 시간")

    # 메타데이터
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TradingExecutionCreate(BaseModel):
    """거래 실행 결과 생성용 모델"""

    exchange: str
    market: str
    testnet: bool
    ai_signal: Dict[str, Any]
    action: str
    quantity: float
    order_type: str
    price: Optional[float] = None
    signal_confidence: Optional[float] = None
    signal_reason: Optional[str] = None


class TradingExecutionQuery(BaseModel):
    """거래 실행 결과 조회용 쿼리 모델"""

    exchange: Optional[str] = Field(None, description="거래소 필터")
    market: Optional[str] = Field(None, description="시장 필터")
    testnet: Optional[bool] = Field(None, description="테스트넷 사용 여부")
    action: Optional[str] = Field(None, description="거래 방향 필터")
    order_type: Optional[str] = Field(None, description="주문 타입 필터")
    start_date: Optional[datetime] = Field(None, description="시작 날짜")
    end_date: Optional[datetime] = Field(None, description="종료 날짜")
    limit: int = Field(default=100, description="조회 개수 제한")
    skip: int = Field(default=0, description="건너뛸 개수")


class TradingExecutionStats(BaseModel):
    """거래 실행 결과 통계 모델"""

    total_executions: int = Field(..., description="총 실행 개수")
    action_distribution: Dict[str, int] = Field(..., description="거래 방향별 분포")
    order_type_distribution: Dict[str, int] = Field(..., description="주문 타입별 분포")
    testnet_distribution: Dict[str, int] = Field(..., description="테스트넷/메인넷 분포")

    # 성공률 통계
    success_rate: Optional[float] = Field(None, description="거래 성공률")
    avg_confidence: Optional[float] = Field(None, description="평균 신뢰도")

    # 금액 통계
    total_volume: Optional[float] = Field(None, description="총 거래량")
    avg_quantity: Optional[float] = Field(None, description="평균 거래 수량")

    # 시간별 통계
    hourly_distribution: Optional[Dict[str, int]] = Field(None, description="시간대별 분포")
    daily_distribution: Optional[Dict[str, int]] = Field(None, description="일별 분포")


class TradingExecutionResponse(BaseModel):
    """거래 실행 결과 응답 모델"""

    # 기본 정보
    exchange: str
    market: str
    testnet: bool
    action: str
    quantity: float
    order_type: str

    # AI 신호 정보
    ai_signal: Dict[str, Any]
    signal_confidence: Optional[float]
    signal_reason: Optional[str]

    # 거래 결과
    order_id: Optional[str]
    order_status: Optional[str]
    execution_price: Optional[float]

    # 타임스탬프
    timestamp: datetime
    executed_at: Optional[datetime]

    # 메타데이터
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


