"""
리스크 분석 에이전트 데이터 모델
Pydantic 기반 데이터 검증 및 직렬화
"""

from typing import Dict, Any, Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field, validator
import numpy as np


class RiskAnalysisRequest(BaseModel):
    """리스크 분석 요청 모델 (웹훅 호환)"""
    market: str = Field(..., description="분석할 마켓 (예: BTC/USDT)")
    timeframe: str = Field("1d", description="시간프레임 (minutes:5, 1h, 4h, 1d 등)")
    count: int = Field(200, description="데이터 포인트 수 (웹훅 파라미터)")
    personality: Literal["conservative", "neutral", "aggressive"] = Field("neutral", description="투자 성향")
    include_analysis: bool = Field(True, description="AI 분석 포함 여부")
    days_back: int = Field(30, description="조회 기간 (일) - 자동 계산됨")

    @validator('count')
    def validate_count(cls, v):
        if v < 50:
            raise ValueError('count는 최소 50 이상이어야 합니다')
        if v > 1000:
            raise ValueError('count는 최대 1000 이하여야 합니다')
        return v

    @validator('timeframe')
    def validate_timeframe(cls, v, values):
        # timeframe을 days_back으로 변환하는 로직
        count = values.get('count', 200)
        if v.startswith('minutes:'):
            # 5분봉의 경우, count * 5분을 일수로 변환
            minutes = int(v.split(':')[1])
            days = (minutes * count) / (24 * 60)  # 분을 일로 변환
            values['days_back'] = max(7, int(days))  # 최소 7일
        elif v == "1h":
            values['days_back'] = max(7, count // 24)  # 시간봉 기준
        elif v == "4h":
            values['days_back'] = max(7, count // 6)   # 4시간봉 기준
        elif v == "1d":
            values['days_back'] = max(7, count)        # 일봉 기준
        else:
            values['days_back'] = 30  # 기본값
        return v


class RiskAnalysisResponse(BaseModel):
    """리스크 분석 응답 모델"""
    status: str = Field(..., description="상태 (success/error)")
    market: str = Field(..., description="분석 마켓")
    timestamp: str = Field(..., description="분석 시간")

    # === 시장 데이터 ===
    market_data: Dict[str, Any] = Field(..., description="시장 데이터")

    # === 리스크 지표 ===
    risk_indicators: Dict[str, Any] = Field(..., description="리스크 지표")

    # === 상관관계 분석 ===
    correlation_analysis: Dict[str, Any] = Field(..., description="상관관계 분석")

    # === AI 분석 및 요약 ===
    ai_analysis: Optional[Dict[str, Any]] = Field(None, description="AI 분석 결과")

    # === 최종 리스크 레벨 ===
    market_risk_level: str = Field(..., description="시장 리스크 레벨 (LOW/MEDIUM/HIGH/CRITICAL)")
    risk_off_signal: bool = Field(..., description="Risk-Off 신호 여부")
    confidence: float = Field(..., description="신뢰도 (0-1)")

    # === 권장사항 (리스크 에이전트에서는 제공하지 않음) ===
    recommendations: Optional[Dict[str, Any]] = Field(None, description="투자 권장사항 (마스터 에이전트 담당)")

    # 메타데이터
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")


class MarketData(BaseModel):
    """시장 데이터 모델"""
    btc_price: float = Field(..., description="비트코인 현재 가격")
    btc_change_24h: float = Field(..., description="비트코인 24시간 변화율")
    btc_volatility: float = Field(..., description="비트코인 변동성")

    nasdaq_price: float = Field(..., description="나스닥 현재 가격")
    nasdaq_change_24h: float = Field(..., description="나스닥 24시간 변화율")

    dxy_price: float = Field(..., description="달러 인덱스 현재 가격")
    dxy_change_24h: float = Field(..., description="달러 인덱스 24시간 변화율")

    vix_price: float = Field(..., description="VIX 현재 가격")
    vix_change_24h: float = Field(..., description="VIX 24시간 변화율")

    gold_price: float = Field(..., description="금 현재 가격")
    gold_change_24h: float = Field(..., description="금 24시간 변화율")


class RiskIndicators(BaseModel):
    """리스크 지표 모델"""
    # 비트코인 변동성 지표
    btc_volatility_7d: float = Field(..., description="7일 변동성")
    btc_volatility_30d: float = Field(..., description="30일 변동성")
    btc_volatility_percentile: float = Field(..., description="변동성 백분위수")

    # 시장 스트레스 지표
    vix_level: float = Field(..., description="VIX 레벨")
    vix_percentile: float = Field(..., description="VIX 백분위수")

    # 달러 강도
    dxy_level: float = Field(..., description="달러 인덱스 레벨")
    dxy_percentile: float = Field(..., description="달러 인덱스 백분위수")

    # 금 시장
    gold_volatility: float = Field(..., description="금 변동성")
    gold_percentile: float = Field(..., description="금 가격 백분위수")

    # 종합 리스크 점수
    overall_risk_score: float = Field(..., description="종합 리스크 점수 (0-100)")


class CorrelationAnalysis(BaseModel):
    """상관관계 분석 모델"""
    # 비트코인과 주요 자산의 상관관계
    btc_nasdaq_correlation: float = Field(..., description="BTC-나스닥 상관관계")
    btc_dxy_correlation: float = Field(..., description="BTC-달러인덱스 상관관계")
    btc_vix_correlation: float = Field(..., description="BTC-VIX 상관관계")
    btc_gold_correlation: float = Field(..., description="BTC-금 상관관계")

    # 주요 자산 간 상관관계
    nasdaq_dxy_correlation: float = Field(..., description="나스닥-달러인덱스 상관관계")
    nasdaq_vix_correlation: float = Field(..., description="나스닥-VIX 상관관계")
    dxy_vix_correlation: float = Field(..., description="달러인덱스-VIX 상관관계")

    # 상관관계 해석
    correlation_summary: str = Field(..., description="상관관계 요약")
    risk_off_indicators: List[str] = Field(..., description="Risk-Off 신호 지표들")


class AIAnalysis(BaseModel):
    """AI 분석 결과 모델"""
    market_summary: str = Field(..., description="시장 상황 요약")
    risk_assessment: str = Field(..., description="리스크 평가")
    key_risks: List[str] = Field(..., description="주요 리스크 요인들")
    opportunities: List[str] = Field(..., description="투자 기회")
    recommendations: str = Field(..., description="투자 권장사항")
    confidence: float = Field(..., description="AI 분석 신뢰도")


class Recommendations(BaseModel):
    """투자 권장사항 모델"""
    position_size: str = Field(..., description="권장 포지션 크기 (FULL/HALF/MINIMAL/HOLD)")
    position_percentage: float = Field(..., description="권장 포지션 비율 (0-100)")
    risk_level: str = Field(..., description="권장 리스크 레벨 (LOW/MEDIUM/HIGH)")
    stop_loss: Optional[float] = Field(None, description="권장 손절가")
    take_profit: Optional[float] = Field(None, description="권장 익절가")
    timeframe: str = Field(..., description="권장 투자 기간")
    reasoning: str = Field(..., description="권장사항 근거")
