"""
Autotrading V2 API 라우터
N8n 에이전트 호환 엔드포인트 제공
"""

from fastapi import APIRouter, HTTPException, Query, Body, Depends, Path
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
    TradeExecutionRequest, TradeExecutionResponse,
    TradeExecutionDataResponse, TradeExecutionListResponse
)
# from src.scheduler.tasks.chart_analysis_task.func import ChartAnalysisFunc  # 삭제된 모듈
from src.common.utils.logger import set_logger

# 라우터 생성
router = APIRouter()

# 서비스 인스턴스
quantitative_service = QuantitativeServiceV2()
risk_service = None  # 지연 초기화
balance_service = BalanceService()
trading_service = TradingService()

# 캐시 기반 분석 서비스
chart_analysis_func = None
logger = set_logger("autotrading_v2_router")

def get_chart_analysis_func():
    """ChartAnalysisFunc 싱글톤 인스턴스 반환 - 삭제된 모듈로 인해 비활성화"""
    # global chart_analysis_func
    # if chart_analysis_func is None:
    #     chart_analysis_func = ChartAnalysisFunc(logger)
    # return chart_analysis_func
    return None  # 임시로 None 반환

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
    "/quantitative/analyze/cached",
    tags=["Autotrading-Quantitative"],
    response_model=QuantitativeResponse,
    summary="정량지표 분석 (캐시 기반)",
    description="캐시된 분석 결과를 우선 조회하고, 없으면 실시간 분석을 수행합니다."
)
async def analyze_quantitative_indicators_cached(
    market: str = Query(..., description="거래 마켓 (예: BTC/USDT)"),
    timeframe: str = Query("minutes:60", description="시간프레임"),
    count: int = Query(200, description="캔들 개수"),
    exchange: str = Query("binance", description="거래소"),
    force_refresh: bool = Query(False, description="캐시 무시하고 강제 새로고침")
):
    """
    정량지표 분석 실행 (캐시 기반)

    캐시된 분석 결과가 있으면 즉시 반환하고, 없으면 실시간 분석을 수행합니다.
    """
    try:
        logger.info(f"🔍 [캐시] 정량지표 분석 요청: {market} | {timeframe} | {count}개 | 강제새로고침: {force_refresh}")

        # Function 인스턴스 가져오기
        func = get_chart_analysis_func()

        # 삭제된 모듈로 인해 기능 비활성화
        if func is None:
            logger.warning("⚠️ [캐시] ChartAnalysisFunc가 비활성화되어 있습니다. 직접 분석을 수행합니다.")
            # 직접 분석 수행 (QuantitativeServiceV2 사용)
            result = await quantitative_service.analyze_market(
                market=market,
                timeframe=timeframe,
                count=count,
                exchange=exchange
            )
            return result

        # 캐시 확인 (강제 새로고침이 아닌 경우)
        if not force_refresh:
            cached_result = await func.get_latest_analysis(market)
            if cached_result:
                logger.info(f"✅ [캐시] 캐시된 결과 반환: {market}")
                return QuantitativeResponse(**cached_result.get('full_report', {}))

        # 캐시가 없거나 강제 새로고침인 경우 실시간 분석
        logger.info(f"🚀 [실시간] 분석 실행: {market}")
        result = await quantitative_service.analyze_market(
            market=market,
            timeframe=timeframe,
            count=count,
            exchange=exchange,
        )

        # 결과를 캐시에 저장 (비동기로 실행)
        import asyncio
        asyncio.create_task(func.save_analysis_result(market, result, "api_request"))

        return QuantitativeResponse(**result)

    except Exception as e:
        logger.error(f"❌ [캐시] 정량지표 분석 실패: {market} - {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"정량지표 분석 실패: {str(e)}"
        )


@router.get(
    "/quantitative/analyze/all",
    tags=["Autotrading-Quantitative"],
    summary="모든 코인 정량지표 분석 조회 (캐시 기반)",
    description="캐시된 모든 코인의 분석 결과를 조회합니다."
)
async def get_all_quantitative_analyses():
    """
    모든 코인의 정량지표 분석 결과 조회 (캐시 기반)
    """
    try:
        logger.info("🔍 [캐시] 모든 코인 분석 결과 조회 요청")

        # Function 인스턴스 가져오기
        func = get_chart_analysis_func()

        # 삭제된 모듈로 인해 기능 비활성화
        if func is None:
            logger.warning("⚠️ [캐시] ChartAnalysisFunc가 비활성화되어 있습니다. 빈 결과를 반환합니다.")
            return {
                "status": "success",
                "data": [],
                "message": "ChartAnalysisFunc가 비활성화되어 있습니다."
            }

        # 모든 캐시된 분석 결과 조회
        cached_results = await func.get_all_latest_analyses()

        # 결과 포맷팅
        formatted_results = []
        for result in cached_results:
            formatted_results.append({
                'asset_symbol': result.get('asset_symbol'),
                'quant_score': result.get('quant_score'),
                'social_score': result.get('social_score'),
                'risk_score': result.get('risk_score'),
                'overall_score': result.get('overall_score'),
                'market_regime': result.get('market_regime'),
                'analyst_summary': result.get('analyst_summary'),
                'status': result.get('status'),
                'created_at': result.get('created_at'),
                'expires_at': result.get('expires_at'),
                'full_report': result.get('full_report')
            })

        logger.info(f"✅ [캐시] {len(formatted_results)}개 코인 분석 결과 반환")
        return {
            'status': 'success',
            'total_count': len(formatted_results),
            'results': formatted_results,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"❌ [캐시] 모든 코인 분석 결과 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"모든 코인 분석 결과 조회 실패: {str(e)}"
        )


@router.post(
    "/quantitative/analyze/trigger",
    tags=["Autotrading-Quantitative"],
    summary="알트코인 분석 트리거",
    description="특정 알트코인에 대한 즉시 분석을 트리거합니다."
)
async def trigger_altcoin_analysis(
    market: str = Query(..., description="거래 마켓 (예: DOGE/USDT)"),
    timeframe: str = Query("minutes:60", description="시간프레임"),
    count: int = Query(200, description="캔들 개수"),
    exchange: str = Query("binance", description="거래소")
):
    """
    알트코인 분석 트리거

    특정 알트코인에 대한 즉시 분석을 트리거하고 결과를 반환합니다.
    """
    try:
        logger.info(f"🔄 [트리거] 알트코인 분석 트리거: {market}")

        # Celery 태스크 트리거
        from src.scheduler.tasks.chart_analysis_task import trigger_altcoin_analysis
        task_result = trigger_altcoin_analysis.delay(market, timeframe, count, exchange)

        return {
            'status': 'success',
            'market': market,
            'task_id': task_result.id,
            'message': f'{market} 알트코인 분석이 시작되었습니다.',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"❌ [트리거] 알트코인 분석 트리거 실패: {market} - {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"알트코인 분석 트리거 실패: {str(e)}"
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
            "user_idx": "1",
            "include_trade_history": True,
            "recent_trades_count": 10
        }
    )
):
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
            "user_idx": 1
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


# ===== 거래 실행 데이터 조회 =====

@router.get(
    "/trades",
    tags=["Autotrading-Trade"],
    response_model=TradeExecutionListResponse,
    summary="거래 실행 데이터 목록 조회",
    description="사용자의 거래 실행 데이터 목록을 조회합니다. 필터링 옵션을 제공합니다."
)
async def get_trade_executions(
    user_idx: int = Query(..., description="사용자 인덱스"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    action: Optional[str] = Query(None, description="거래 액션 필터 (BUY/SELL)"),
    market: Optional[str] = Query(None, description="마켓 필터 (예: BTC/USDT)"),
    start_date: Optional[str] = Query(None, description="시작 날짜 (ISO 8601)"),
    end_date: Optional[str] = Query(None, description="종료 날짜 (ISO 8601)")
):
    """
    거래 실행 데이터 목록 조회

    사용자의 거래 실행 데이터를 페이지네이션과 필터링을 통해 조회합니다.
    - user_idx: 조회할 사용자 인덱스
    - page: 페이지 번호 (1부터 시작)
    - page_size: 페이지당 항목 수 (1-100)
    - action: 거래 액션 필터 (BUY/SELL)
    - market: 마켓 필터 (예: BTC/USDT)
    - start_date: 시작 날짜 (ISO 8601 형식)
    - end_date: 종료 날짜 (ISO 8601 형식)
    """
    try:
        # 날짜 문자열을 datetime 객체로 변환
        start_dt = None
        end_dt = None

        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))

        result = await trading_service.get_trades(
            user_idx=user_idx,
            page=page,
            page_size=page_size,
            action=action,
            market=market,
            start_date=start_dt,
            end_date=end_dt
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"거래 실행 데이터 조회 실패: {str(e)}"
        )


@router.get(
    "/trades/{trade_id}",
    tags=["Autotrading-Trade"],
    response_model=TradeExecutionDataResponse,
    summary="특정 거래 실행 데이터 조회",
    description="특정 거래 실행 데이터의 상세 정보를 조회합니다."
)
async def get_trade_execution_by_id(
    trade_id: int = Path(..., description="거래 ID"),
    user_idx: int = Query(..., description="사용자 인덱스")
):
    """
    특정 거래 실행 데이터 조회

    거래 ID와 사용자 인덱스로 특정 거래 실행 데이터의 상세 정보를 조회합니다.
    - trade_id: 조회할 거래 ID
    - user_idx: 사용자 인덱스
    """
    try:
        result = await trading_service.get_trade_by_id(
            trade_idx=trade_id,
            user_idx=user_idx
        )

        if not result:
            raise HTTPException(
                status_code=404,
                detail="거래 실행 데이터를 찾을 수 없습니다."
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"거래 실행 데이터 조회 실패: {str(e)}"
        )

