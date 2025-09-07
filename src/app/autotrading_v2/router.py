"""
Autotrading V2 API 라우터
N8n 에이전트 호환 엔드포인트 제공
"""

from fastapi import APIRouter, HTTPException, Query, Body, Depends
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from .quantitative_service import QuantitativeServiceV2
from .risk_service import RiskAnalysisService
from .models import (
    QuantitativeRequest, QuantitativeResponse,
    OnchainRequest, OnchainResponse,
    OffchainRequest, OffchainResponse,
    IntegrationRequest, IntegrationResponse,
    DashboardRequest, DashboardResponse,
    HealthCheckResponse, ErrorResponse
)
from .risk_models import RiskAnalysisRequest, RiskAnalysisResponse

# 라우터 생성
router = APIRouter(prefix="/v2", tags=["Autotrading V2"])

# 서비스 인스턴스
quantitative_service = QuantitativeServiceV2()
risk_service = None  # 지연 초기화

def get_risk_service():
    """리스크 분석 서비스 지연 초기화"""
    global risk_service
    if risk_service is None:
        risk_service = RiskAnalysisService()
    return risk_service


# ===== 1단계: 정량지표 (차트기반) =====

@router.post(
    "/quantitative/analyze",
    response_model=QuantitativeResponse,
    summary="정량지표 분석 (N8n 호환)",
    description="차트 기반 기술적 지표를 분석하여 거래 신호를 생성합니다. N8n 에이전트에서 정기적으로 호출할 수 있습니다."
)
async def analyze_quantitative_indicators(
    request: QuantitativeRequest = Body(
        ...,
        example={
            "market": "BTC/USDT",
            "timeframe": "minutes:60",
            "count": 200,
            "exchange": "binance",
        }
    )
):
    """
    정량지표 분석 실행 (POST 방식)

    N8n에서 정기적으로 호출하여 거래 신호를 생성합니다.
    """
    try:
        result = await quantitative_service.analyze_market(
            market=request.market,
            timeframe=request.timeframe,
            count=request.count,
            exchange=request.exchange,
        )

        return QuantitativeResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"정량지표 분석 실패: {str(e)}"
        )




@router.get(
    "/quantitative/indicators",
    summary="지원하는 기술적 지표 목록",
    description="현재 지원하는 기술적 지표들의 목록을 조회합니다."
)
async def get_supported_indicators():
    """지원하는 기술적 지표 목록"""
    return {
        "status": "success",
        "indicators": quantitative_service.get_supported_indicators(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get(
    "/quantitative/regime-weights",
    summary="레짐별 가중치 조회",
    description="추세장과 횡보장의 지표별 가중치를 조회합니다."
)
async def get_regime_weights():
    """레짐별 가중치 조회"""
    return {
        "status": "success",
        "weights": quantitative_service.get_regime_weights(),
        "description": {
            "trend_regime": "추세장에서는 모멘텀과 MACD에 높은 가중치",
            "range_regime": "횡보장에서는 RSI와 볼린저 밴드에 높은 가중치",
            "transition_regime": "전환 구간에서는 균형잡힌 가중치"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ===== 2단계: 리스크 분석 에이전트 =====

@router.post(
    "/risk/analyze",
    response_model=RiskAnalysisResponse,
    summary="리스크 분석 (N8n 호환)",
    description="yfinance, LangChain, LangGraph를 활용하여 시장 리스크를 분석하고 요약합니다."
)
async def analyze_risk(
    request: RiskAnalysisRequest = Body(
        ...,
        example={
            "market": "BTC/USDT",
            "analysis_type": "daily",
            "days_back": 90,
            "personality": "neutral",
            "include_analysis": True
        }
    )
):
    """
    리스크 분석 실행 (POST 방식)

    N8n에서 정기적으로 호출하여 시장 리스크를 분석합니다.
    """
    try:
        # 지연 초기화된 서비스 사용
        service = get_risk_service()
        result = await service.analyze_risk(
            market=request.market,
            analysis_type=request.analysis_type,
            days_back=request.days_back,
            personality=request.personality,
            include_analysis=request.include_analysis
        )

        return RiskAnalysisResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"리스크 분석 실패: {str(e)}"
        )


@router.get(
    "/risk/health",
    summary="리스크 분석 서비스 헬스체크",
    description="리스크 분석 서비스의 상태를 확인합니다."
)
async def risk_health_check():
    """리스크 분석 서비스 헬스체크"""
    try:
        # 지연 초기화된 서비스 사용
        service = get_risk_service()
        health_status = await service.health_check()

        return {
            "status": "success",
            "service": "risk_analysis",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": health_status
        }

    except Exception as e:
        return {
            "status": "error",
            "service": "risk_analysis",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e)
        }


# ===== 3단계: 온체인 지표 (준비 중) =====

@router.post(
    "/onchain/analyze",
    response_model=OnchainResponse,
    summary="온체인 지표 분석 (준비 중)",
    description="온체인 데이터를 분석하여 투자심리지표를 생성합니다."
)
async def analyze_onchain_indicators(request: OnchainRequest):
    """온체인 지표 분석 (준비 중)"""
    return {
        "status": "error",
        "market": request.market,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "indicators": {},
        "onchain_score": 0.0,
        "signal": "NEUTRAL",
        "confidence": 0.0,
        "metadata": {"message": "온체인 지표 분석은 2단계에서 구현 예정"}
    }


# ===== 3단계: 오프체인 지표 (준비 중) =====

@router.post(
    "/offchain/analyze",
    response_model=OffchainResponse,
    summary="오프체인 지표 분석 (준비 중)",
    description="뉴스, 소셜미디어, 거시경제 데이터를 분석하여 감성지표를 생성합니다."
)
async def analyze_offchain_indicators(request: OffchainRequest):
    """오프체인 지표 분석 (준비 중)"""
    return {
        "status": "error",
        "keywords": request.keywords,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sentiment": {},
        "offchain_score": 0.0,
        "signal": "NEUTRAL",
        "confidence": 0.0,
        "metadata": {"message": "오프체인 지표 분석은 3단계에서 구현 예정"}
    }


# ===== 4단계: 통합 분석 (준비 중) =====

@router.post(
    "/integration/analyze",
    response_model=IntegrationResponse,
    summary="통합 분석 (준비 중)",
    description="정량, 온체인, 오프체인 지표를 통합하여 최종 거래 신호를 생성합니다."
)
async def analyze_integration(request: IntegrationRequest):
    """통합 분석 (준비 중)"""
    return {
        "status": "error",
        "market": request.market,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "quantitative_score": 0.0,
        "onchain_score": 0.0,
        "offchain_score": 0.0,
        "weights": {
            "quant_weight": request.quant_weight,
            "onchain_weight": request.onchain_weight,
            "offchain_weight": request.offchain_weight
        },
        "final_score": 0.0,
        "position_size": 0.0,
        "action": "HOLD",
        "stop_loss": None,
        "take_profit": None,
        "confidence": 0.0,
        "metadata": {"message": "통합 분석은 4단계에서 구현 예정"}
    }


# ===== 5단계: 대시보드 (준비 중) =====

@router.post(
    "/dashboard",
    response_model=DashboardResponse,
    summary="대시보드 데이터 (준비 중)",
    description="실시간 모니터링 및 성과 분석 대시보드 데이터를 제공합니다."
)
async def get_dashboard_data(request: DashboardRequest):
    """대시보드 데이터 (준비 중)"""
    return {
        "status": "error",
        "market": request.market,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "current_status": {},
        "indicators_status": {},
        "trading_signals": {},
        "performance": {},
        "alerts": [],
        "history": None,
        "metadata": {"message": "대시보드는 5단계에서 구현 예정"}
    }


# ===== 헬스체크 및 유틸리티 =====

@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="서비스 헬스체크",
    description="Autotrading V2 서비스의 상태를 확인합니다."
)
async def health_check():
    """서비스 헬스체크"""
    try:
        # 정량지표 서비스 헬스체크
        quant_health = await quantitative_service.health_check()

        # 리스크 분석 서비스 헬스체크
        risk_service_instance = get_risk_service()
        risk_health = await risk_service_instance.health_check()

        # 통합 헬스체크 상태
        overall_status = "healthy"
        if quant_health.get("indicators_calculation") == "error" or risk_health.get("data_collection") == "error":
            overall_status = "unhealthy"

        return HealthCheckResponse(
            error=None,
            status=overall_status,
            service="autotrading_v2",
            timestamp=datetime.now(timezone.utc).isoformat(),
            version="2.0.0",
            details={
                "quantitative_service": quant_health,
                "risk_analysis_service": risk_health
            }
        )

    except Exception as e:
        return HealthCheckResponse(
            status="unhealthy",
            service="autotrading_v2",
            timestamp=datetime.now(timezone.utc).isoformat(),
            version="2.0.0",
            details={},
            error=str(e)
        )


