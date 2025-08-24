# src/app/routers/chart.py
from fastapi import APIRouter, Query
from typing import Literal
from datetime import datetime
from src.app.service.chart import ChartService, Timeframe

router = APIRouter(prefix="/charts")
svc = ChartService()

@router.get(
    "/health",
    tags=["지표-분석"],
    summary="Get chart health",
    description="Get chart health",
)
async def health():
    return await svc.get_chart_health()

@router.get(
    "/signals/overall",
    tags=["지표-분석"],
    summary="시그널 전체 조회",
    description="시그널 전체 조회",
)
async def overall(
    market: str = "KRW-BTC",
    tf: Timeframe = "minutes:60",
    count: int = 200
):
    return await svc.get_overall_signals(market, tf, count)

@router.get(
    "/signals/overall-with-db",
    tags=["지표-분석"],
    summary="시그널 전체 조회 + DB 저장",
    description="시그널 계산 후 MongoDB에 저장",
)
async def overall_with_db(
    market: str = "KRW-BTC",
    tf: Timeframe = "minutes:60",
    count: int = 200,
    save_to_db: bool = True
):
    return await svc.save_and_get_overall_signals(market, tf, count, save_to_db)

@router.get(
    "/indicators",
    tags=["지표-분석"],
    summary="지표 조회",
    description="지표 조회",
)
async def indicators(
    market: str = "KRW-BTC",
    tf: Timeframe = "minutes:60",
    count: int = 200
):
    df = await svc.get_candles(market, tf, count)
    ind = svc.compute_indicators(df)
    return {"market": market, "tf": tf, "asof": ind["time"], "indicators": ind}

@router.get(
    "/indicator/{name}",
    tags=["지표-분석"],
    summary="지표 조회",
    description="지표 조회",
)
async def indicator(
    name: Literal[
        "close","momentum_cumret","momentum_sharpe_like","volume_z","return_over_vol",
        "rsi","bb_pct_b","bb_pct_b","bb_bandwidth","macd","macd_signal","macd_hist","macd_cross"
    ],
    market: str = "KRW-BTC",
    tf: Timeframe = "minutes:60",
    count: int = 200
):
    return await svc.get_single_indicator(market, tf, count, name=name)

@router.get(
    "/rule/{rule}",
    tags=["지표-분석"],
    summary="규칙 조회",
    description="규칙 조회",
)
async def rule(
    rule: Literal["rule1_momentum","rule2_volume","rule3_ret_over_vol","rule4_rsi","rule5_bollinger","rule6_macd"],
    market: str = "KRW-BTC",
    tf: Timeframe = "minutes:60",
    count: int = 200
):
    return await svc.get_single_rule(market, tf, count, rule=rule)

@router.get(
    "/card",
    tags=["지표-분석"],
    summary="카드 조회",
    description="카드 조회",
)
async def card(
    market: str = "KRW-BTC",
    tf: Timeframe = "minutes:60",
    count: int = 200
):
    return await svc.get_indicator_card(market, tf, count)

# ---- MongoDB 히스토리 관련 API ----

@router.get(
    "/history/analysis",
    tags=["히스토리"],
    summary="과거 데이터 분석",
    description="특정 기간의 차트 데이터와 AI 분석 결과",
)
async def historical_analysis(
    market: str = "KRW-BTC",
    tf: Timeframe = "minutes:60",
    days: int = 7
):
    return await svc.get_historical_analysis(market, tf, days)

@router.get(
    "/history/statistics",
    tags=["히스토리"],
    summary="마켓 통계",
    description="특정 기간의 마켓 통계 정보",
)
async def market_statistics(
    market: str = "KRW-BTC",
    tf: Timeframe = "minutes:60",
    days: int = 30
):
    return await svc.get_market_statistics(market, tf, days)

@router.get(
    "/history/daily-aggregation",
    tags=["히스토리"],
    summary="일별 집계",
    description="특정 날짜의 시간별 지표 집계",
)
async def daily_aggregation(
    market: str = "KRW-BTC",
    tf: Timeframe = "minutes:60",
    target_date: str = None
):
    if target_date:
        try:
            target_dt = datetime.fromisoformat(target_date)
        except ValueError:
            target_dt = None
    else:
        target_dt = None

    return await svc.get_daily_aggregation(market, tf, target_dt)

# ---- AI 분석 저장 API ----

@router.post(
    "/ai/analysis",
    tags=["AI분석"],
    summary="AI 분석 결과 저장",
    description="AI가 생성한 매수/매도 분석 결과를 저장",
)
async def save_ai_analysis(
    market: str = "KRW-BTC",
    analysis: dict = None
):
    if analysis is None:
        analysis = {
            "confidence": 0.85,
            "recommendation": "BUY",
            "reasoning": "RSI 과매도 + 볼린저 밴드 하단 + MACD 상향 돌파",
            "risk_level": "medium",
            "target_price": 162000000,
            "stop_loss": 158000000
        }

    return await svc.save_ai_analysis(market, analysis)

# ---- 데이터 관리 API ----

@router.post(
    "/admin/cleanup",
    tags=["관리"],
    summary="오래된 데이터 정리",
    description="90일 이상 된 데이터를 정리",
)
async def cleanup_old_data(days: int = 90):
    return await svc.cleanup_old_data(days)