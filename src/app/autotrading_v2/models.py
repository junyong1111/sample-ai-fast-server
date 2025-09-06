"""
Autotrading V2 데이터 모델
Pydantic 기반 데이터 검증 및 직렬화
"""

from typing import Dict, Any, Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field, validator
import numpy as np


class QuantitativeRequest(BaseModel):
    """정량지표 분석 요청 모델"""
    market: str = Field(..., description="거래 마켓 (예: BTC/USDT)")
    timeframe: Literal["minutes:1", "minutes:5", "minutes:15", "minutes:30", "minutes:60", "minutes:240", "days"] = Field("minutes:60", description="시간프레임")
    count: int = Field(200, description="캔들 개수 (기본값: 200)")
    exchange: Literal["binance", "upbit"] = Field("binance", description="거래소")
    testnet: bool = Field(True, description="테스트넷 사용 여부")

    @validator('count')
    def validate_count(cls, v):
        if v < 50:
            raise ValueError('count는 최소 50 이상이어야 합니다')
        if v > 1000:
            raise ValueError('count는 최대 1000 이하여야 합니다')
        return v


class QuantitativeResponse(BaseModel):
    """정량지표 분석 응답 모델"""
    status: str = Field(..., description="상태 (success/error)")
    market: str = Field(..., description="거래 마켓")
    timeframe: str = Field(..., description="시간프레임")
    timestamp: str = Field(..., description="분석 시간")

    # === 인간 친화적 분석 결과 ===
    analysis: Dict[str, Any] = Field(..., description="인간 친화적 분석 결과")

    # === 상세 데이터 (AI/시스템용) ===
    detailed_data: Dict[str, Any] = Field(..., description="상세 데이터 (AI/시스템용)")

    # 메타데이터
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")


class OnchainRequest(BaseModel):
    """온체인 지표 분석 요청 모델"""
    market: str = Field(..., description="거래 마켓 (예: BTC)")
    timeframe: Literal["1h", "4h", "1d"] = Field("1d", description="시간프레임")
    days_back: int = Field(30, description="조회 기간 (일)")

    @validator('days_back')
    def validate_days_back(cls, v):
        if v < 7:
            raise ValueError('days_back은 최소 7일 이상이어야 합니다')
        if v > 365:
            raise ValueError('days_back은 최대 365일 이하여야 합니다')
        return v


class OnchainResponse(BaseModel):
    """온체인 지표 분석 응답 모델"""
    status: str = Field(..., description="상태 (success/error)")
    market: str = Field(..., description="거래 마켓")
    timestamp: str = Field(..., description="분석 시간")

    # 온체인 지표
    indicators: Dict[str, Any] = Field(..., description="온체인 지표 값들")

    # 점수 정보
    onchain_score: float = Field(..., description="온체인 종합 점수 (-1 ~ +1)")

    # 거래 신호
    signal: str = Field(..., description="거래 신호 (BULLISH/BEARISH/NEUTRAL)")
    confidence: float = Field(..., description="신호 신뢰도 (0-1)")

    # 메타데이터
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")


class OffchainRequest(BaseModel):
    """오프체인 지표 분석 요청 모델"""
    keywords: List[str] = Field(..., description="분석할 키워드 목록")
    timeframe: Literal["1h", "4h", "1d"] = Field("1d", description="시간프레임")
    sources: List[Literal["news", "social", "macro"]] = Field(["news", "social"], description="분석 소스")

    @validator('keywords')
    def validate_keywords(cls, v):
        if len(v) == 0:
            raise ValueError('키워드는 최소 1개 이상이어야 합니다')
        if len(v) > 10:
            raise ValueError('키워드는 최대 10개 이하여야 합니다')
        return v


class OffchainResponse(BaseModel):
    """오프체인 지표 분석 응답 모델"""
    status: str = Field(..., description="상태 (success/error)")
    keywords: List[str] = Field(..., description="분석된 키워드 목록")
    timestamp: str = Field(..., description="분석 시간")

    # 오프체인 지표
    sentiment: Dict[str, Any] = Field(..., description="감성 분석 결과")

    # 점수 정보
    offchain_score: float = Field(..., description="오프체인 종합 점수 (-1 ~ +1)")

    # 거래 신호
    signal: str = Field(..., description="거래 신호 (BULLISH/BEARISH/NEUTRAL)")
    confidence: float = Field(..., description="신호 신뢰도 (0-1)")

    # 메타데이터
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")


class IntegrationRequest(BaseModel):
    """통합 분석 요청 모델"""
    market: str = Field(..., description="거래 마켓 (예: BTC/USDT)")
    quantitative_data: Optional[Dict[str, Any]] = Field(None, description="정량지표 데이터")
    onchain_data: Optional[Dict[str, Any]] = Field(None, description="온체인 데이터")
    offchain_data: Optional[Dict[str, Any]] = Field(None, description="오프체인 데이터")

    # 가중치 설정
    quant_weight: float = Field(0.5, description="정량지표 가중치")
    onchain_weight: float = Field(0.3, description="온체인 가중치")
    offchain_weight: float = Field(0.2, description="오프체인 가중치")

    @validator('quant_weight', 'onchain_weight', 'offchain_weight')
    def validate_weights(cls, v):
        if not 0 <= v <= 1:
            raise ValueError('가중치는 0-1 사이의 값이어야 합니다')
        return v

    @validator('offchain_weight')
    def validate_total_weight(cls, v, values):
        total = values.get('quant_weight', 0) + values.get('onchain_weight', 0) + v
        if abs(total - 1.0) > 0.01:
            raise ValueError('모든 가중치의 합은 1.0이어야 합니다')
        return v


class IntegrationResponse(BaseModel):
    """통합 분석 응답 모델"""
    status: str = Field(..., description="상태 (success/error)")
    market: str = Field(..., description="거래 마켓")
    timestamp: str = Field(..., description="분석 시간")

    # 개별 점수
    quantitative_score: float = Field(..., description="정량지표 점수")
    onchain_score: float = Field(..., description="온체인 점수")
    offchain_score: float = Field(..., description="오프체인 점수")

    # 가중치
    weights: Dict[str, float] = Field(..., description="적용된 가중치")

    # 최종 결과
    final_score: float = Field(..., description="최종 통합 점수 (-1 ~ +1)")
    position_size: float = Field(..., description="포지션 크기 (0-1)")
    action: str = Field(..., description="거래 액션 (BUY/SELL/HOLD)")

    # 리스크 관리
    stop_loss: Optional[float] = Field(None, description="손절 가격")
    take_profit: Optional[float] = Field(None, description="익절 가격")

    # 신뢰도
    confidence: float = Field(..., description="종합 신뢰도 (0-1)")

    # 메타데이터
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")


class DashboardRequest(BaseModel):
    """대시보드 요청 모델"""
    market: str = Field(..., description="거래 마켓")
    timeframe: Literal["1h", "4h", "1d"] = Field("1d", description="시간프레임")
    include_history: bool = Field(True, description="히스토리 포함 여부")
    history_days: int = Field(7, description="히스토리 기간 (일)")


class DashboardResponse(BaseModel):
    """대시보드 응답 모델"""
    status: str = Field(..., description="상태 (success/error)")
    market: str = Field(..., description="거래 마켓")
    timestamp: str = Field(..., description="생성 시간")

    # 현재 상태
    current_status: Dict[str, Any] = Field(..., description="현재 시장 상태")

    # 지표 현황
    indicators_status: Dict[str, Any] = Field(..., description="지표별 현황")

    # 거래 신호
    trading_signals: Dict[str, Any] = Field(..., description="거래 신호 현황")

    # 성과 분석
    performance: Dict[str, Any] = Field(..., description="성과 분석")

    # 알림
    alerts: List[Dict[str, Any]] = Field(default_factory=list, description="알림 목록")

    # 히스토리 (선택사항)
    history: Optional[Dict[str, Any]] = Field(None, description="히스토리 데이터")

    # 메타데이터
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")


class HealthCheckResponse(BaseModel):
    """헬스체크 응답 모델"""
    status: str = Field(..., description="상태 (healthy/unhealthy)")
    service: str = Field(..., description="서비스 이름")
    timestamp: str = Field(..., description="체크 시간")
    version: str = Field(..., description="서비스 버전")
    details: Dict[str, Any] = Field(default_factory=dict, description="상세 정보")
    error: Optional[str] = Field(None, description="에러 메시지")


class ErrorResponse(BaseModel):
    """에러 응답 모델"""
    status: str = Field("error", description="상태")
    error: str = Field(..., description="에러 메시지")
    error_code: Optional[str] = Field(None, description="에러 코드")
    timestamp: str = Field(..., description="에러 발생 시간")
    details: Optional[Dict[str, Any]] = Field(None, description="에러 상세 정보")
