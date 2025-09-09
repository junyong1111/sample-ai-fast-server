"""
Autotrading V2 API 라우터
N8n 에이전트 호환 엔드포인트 제공
"""

from fastapi import APIRouter, HTTPException, Query, Body, Depends
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from .quantitative_service import QuantitativeServiceV2
from .risk_service import RiskAnalysisService
from .balance_service import BalanceService
from .trading_service import TradingService
from .models import (
    HealthCheckResponse, QuantitativeRequest, QuantitativeResponse,
    RiskAnalysisRequest, RiskAnalysisResponse,
    BalanceRequest, BalanceResponse,
    TradeExecutionRequest, TradeExecutionResponse
)

# 라우터 생성
router = APIRouter()

# 서비스 인스턴스
quantitative_service = QuantitativeServiceV2()
risk_service = None  # 지연 초기화
balance_service = BalanceService()
trading_service = TradingService()

def get_risk_service():
    """리스크 분석 서비스 지연 초기화"""
    global risk_service
    if risk_service is None:
        risk_service = RiskAnalysisService()
    return risk_service


# ===== 1단계: 정량지표 (차트기반) =====

@router.post(
    "/quantitative/analyze",
    tags=["Autotrading-Quantitative"],
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
    tags=["Autotrading-Quantitative"],
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
    tags=["Autotrading-Quantitative"],
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
    tags=["Autotrading-Risk"],
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
        # 디버깅: result 구조 확인
        print(f"DEBUG: result keys = {result.keys() if isinstance(result, dict) else 'Not a dict'}")
        print(f"DEBUG: result = {result}")

        return RiskAnalysisResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"리스크 분석 실패: {str(e)}"
        )



# ===== 헬스체크 및 유틸리티 =====

@router.get(
    "/health",
    tags=["Autotrading"],
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


# ===== 잔고 조회 =====

@router.post(
    "/balance",
    tags=["Autotrading-Balance"],
    response_model=BalanceResponse,
    summary="현재 잔고 조회",
    description="바이낸스 API를 통해 현재 계좌의 실시간 잔고를 조회합니다. 특정 티커를 지정하면 해당 코인만 조회합니다."
)
async def get_balance(
    request: BalanceRequest = Body(
        ...,
        example={
            "tickers": ["BTC", "ETH", "USDT"],
            "include_zero_balances": False,
            "user_id": "default_user"
        }
    )
):
    """
    현재 잔고 조회

    바이낸스 API를 통해 현재 계좌의 실시간 잔고를 조회합니다.
    - tickers: 조회할 코인 티커 목록 (None이면 모든 잔고 조회)
    - USDT는 자동으로 포함됩니다
    - include_zero_balances: 0 잔고 포함 여부
    """
    try:
        result = await balance_service.get_balance(request)
        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"잔고 조회 실패: {str(e)}"
        )

# ===== 거래 실행 =====

@router.post(
    "/trade/execute",
    tags=["Autotrading-Trade"],
    response_model=TradeExecutionResponse,
    summary="거래 실행",
    description="AI 분석 결과에 따라 바이낸스에서 실제 매수/매도 주문을 실행합니다."
)
async def execute_trade(
    request: TradeExecutionRequest = Body(
        ...,
        example={
            "action": "BUY",
            "market": "BTC/USDT",
            "amount_quote": 16.59,
            "reason": "Target is 9.00% (16.59367115 USDT) of total 184.37412389760001 USDT portfolio. Current BTC holding is 0.0 USDT. Rebalance requires buying 16.59367115 USDT worth of BTC.",
            "evidence": {
                "target_btc_percentage": 9,
                "total_portfolio_value": 184.37412389760001,
                "current_btc_value": 0,
                "target_btc_value": 16.593671150784,
                "rebalance_amount_usdt": 16.593671150784
            },
            "user_id": "default_user"
        }
    )
):
    """
    거래 실행

    AI 분석 결과에 따라 바이낸스에서 실제 매수/매도 주문을 실행합니다.
    - action: BUY (매수) 또는 SELL (매도)
    - market: 거래할 마켓 (예: BTC/USDT)
    - amount_quote: 거래할 USDT 금액
    - reason: 거래 실행 이유
    - evidence: 거래 근거 데이터
    """
    try:
        result = await trading_service.execute_trade(request)
        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"거래 실행 실패: {str(e)}"
        )

