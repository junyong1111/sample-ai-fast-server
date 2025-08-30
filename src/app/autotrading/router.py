# src/app/routers/chart.py
from fastapi import APIRouter, Query
from typing import Literal
from src.app.autotrading.service import ChartService, Timeframe

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
        "rsi","bb_pct_b","bb_bandwidth","macd","macd_signal","macd_hist","macd_cross"
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