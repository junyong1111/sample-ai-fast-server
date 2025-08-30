# src/app/routers/chart.py
from fastapi import APIRouter, Query, HTTPException
from typing import Literal, Dict, Any
from src.app.autotrading.service import ChartService, Timeframe
from src.app.autotrading.docs import (
    desc_exchanges_list, desc_exchange_info, desc_price_endpoint, desc_chart_endpoint,
    desc_rsi_endpoint, desc_macd_endpoint, desc_signal_endpoint, desc_examples_endpoint,
    desc_health_endpoint, desc_timeframe, desc_count, desc_period,
    EXCHANGE_DETAILS, API_EXAMPLES_DATA, MARKET_FORMAT_RULES, TIMEFRAME_OPTIONS, COUNT_RECOMMENDATIONS
)

router = APIRouter(prefix="/charts")

# 간단한 차트 서비스 인스턴스
chart_service = ChartService()

# ===== 🏪 거래소 정보 =====
@router.get(
    "/exchanges",
    tags=["🏪 거래소"],
    summary="지원하는 거래소 목록",
    description=desc_exchanges_list
)
async def get_exchanges():
    """사용 가능한 거래소 목록"""
    return {
        "message": "사용 가능한 거래소 목록",
        "exchanges": ["upbit", "binance"],
        "current": "binance (기본값)",
        "details": EXCHANGE_DETAILS
    }

@router.get(
    "/exchanges/{exchange_type}",
    tags=["🏪 거래소"],
    summary="거래소 상세 정보",
    description=desc_exchange_info
)
async def get_exchange_info(exchange_type: str):
    """거래소별 상세 정보"""
    try:
        if exchange_type not in ["upbit", "binance"]:
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 거래소입니다. 'upbit' 또는 'binance'를 사용하세요."
            )

        info = chart_service.get_exchange_info()
        exchange_info = EXCHANGE_DETAILS.get(exchange_type, {})

        return {
            "exchange": exchange_type,
            "info": info,
            "description": exchange_info.get("description", ""),
            "markets": exchange_info.get("markets", []),
            "features": exchange_info.get("features", [])
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ===== 📊 차트 데이터 =====
@router.get(
    "/price/{exchange_type}/{market}",
    tags=["📊 차트 데이터"],
    summary="현재 가격 조회",
    description=desc_price_endpoint
)
async def get_current_price(
    exchange_type: str,
    market: str
):
    """현재 가격 조회"""
    try:
        # 거래소별 시장 형식 변환
        if exchange_type == "upbit" and not market.startswith("KRW-"):
            market = f"KRW-{market}"
        elif exchange_type == "binance" and "/" not in market:
            market = f"{market}/USDT"

        service = ChartService(exchange_type=exchange_type)
        ticker = await service.get_ticker(market)
        return {
            "exchange": exchange_type,
            "market": market,
            "price": ticker["last"],
            "change_24h": ticker["change_percent"],
            "volume_24h": ticker["volume"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/chart/{exchange_type}/{market}",
    tags=["📊 차트 데이터"],
    summary="차트 데이터 조회",
    description=desc_chart_endpoint
)
async def get_chart_data(
    exchange_type: str,
    market: str,
    timeframe: Timeframe = Query(
        "minutes:60",
        description=desc_timeframe
    ),
    count: int = Query(
        100,
        description=desc_count,
        ge=1,
        le=1000
    )
):
    """차트 데이터 조회"""
    try:
        # 거래소별 시장 형식 변환
        if exchange_type == "upbit" and not market.startswith("KRW-"):
            market = f"KRW-{market}"
        elif exchange_type == "binance" and "/" not in market:
            market = f"{market}/USDT"

        service = ChartService(exchange_type=exchange_type)
        candles = await service.get_candles(market, timeframe, count)

        return {
            "exchange": exchange_type,
            "market": market,
            "timeframe": timeframe,
            "count": len(candles),
            "latest_price": float(candles['close'].iloc[-1]),
            "latest_time": candles.index[-1].isoformat(),
            "price_range": {
                "high": float(candles['high'].max()),
                "low": float(candles['low'].min())
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ===== 📈 기술적 지표 =====
@router.get(
    "/rsi/{exchange_type}/{market}",
    tags=["📈 기술적 지표"],
    summary="RSI 지표 조회",
    description=desc_rsi_endpoint
)
async def get_rsi(
    exchange_type: str,
    market: str,
    period: int = Query(
        14,
        description=desc_period,
        ge=1,
        le=100
    ),
    timeframe: Timeframe = Query(
        "minutes:60",
        description=desc_timeframe
    )
):
    """RSI 지표 조회"""
    try:
        # 거래소별 시장 형식 변환
        if exchange_type == "upbit" and not market.startswith("KRW-"):
            market = f"KRW-{market}"
        elif exchange_type == "binance" and "/" not in market:
            market = f"{market}/USDT"

        service = ChartService(exchange_type=exchange_type)
        indicator = await service.get_single_indicator(
            market, timeframe, 100, "rsi"
        )

        rsi_value = indicator["indicator"]["value"]
        signal = "과매수" if rsi_value > 70 else "과매도" if rsi_value < 30 else "중립"

        return {
            "exchange": exchange_type,
            "market": market,
            "rsi": rsi_value,
            "signal": signal,
            "period": period,
            "timeframe": timeframe,
            "interpretation": {
                "0-30": "과매도 (매수 신호)",
                "30-70": "중립 구간",
                "70-100": "과매수 (매도 신호)"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/macd/{exchange_type}/{market}",
    tags=["📈 기술적 지표"],
    summary="MACD 지표 조회",
    description=desc_macd_endpoint
)
async def get_macd(
    exchange_type: str,
    market: str,
    timeframe: Timeframe = Query(
        "minutes:60",
        description=desc_timeframe
    )
):
    """MACD 지표 조회"""
    try:
        # 거래소별 시장 형식 변환
        if exchange_type == "upbit" and not market.startswith("KRW-"):
            market = f"KRW-{market}"
        elif exchange_type == "binance" and "/" not in market:
            market = f"{market}/USDT"

        service = ChartService(exchange_type=exchange_type)
        indicator = await service.get_single_indicator(
            market, timeframe, 100, "macd_cross"
        )

        return {
            "exchange": exchange_type,
            "market": market,
            "macd_cross": indicator["indicator"]["value"],
            "signal": indicator["indicator"]["value"],
            "timeframe": timeframe
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ===== 🎯 거래 신호 =====
@router.get(
    "/signal/{exchange_type}/{market}",
    tags=["🎯 거래 신호"],
    summary="종합 거래 신호",
    description=desc_signal_endpoint
)
async def get_trading_signal(
    exchange_type: str,
    market: str,
    timeframe: Timeframe = Query(
        "minutes:60",
        description=desc_timeframe
    )
):
    """종합 거래 신호 조회"""
    try:
        # 거래소별 시장 형식 변환
        if exchange_type == "upbit" and not market.startswith("KRW-"):
            market = f"KRW-{market}"
        elif exchange_type == "binance" and "/" not in market:
            market = f"{market}/USDT"

        service = ChartService(exchange_type=exchange_type)
        signals = await service.get_overall_signals(market, timeframe, 100)

        return {
            "exchange": exchange_type,
            "market": market,
            "current_price": signals["indicators"]["close"],
            "rsi": signals["indicators"]["rsi"],
            "overall_signal": signals["signals"]["overall"],
            "timeframe": timeframe,
            "timestamp": signals["asof"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ===== 📋 사용 예시 =====
@router.get(
    "/examples",
    tags=["📋 사용 예시"],
    summary="API 사용 예시",
    description=desc_examples_endpoint
)
async def get_api_examples():
    """API 사용 예시"""
    return {
        "message": "API 사용 예시",
        "examples": API_EXAMPLES_DATA,
        "거래소별_시장_형식": MARKET_FORMAT_RULES,
        "시간프레임_옵션": TIMEFRAME_OPTIONS,
        "캔들_개수_권장사항": COUNT_RECOMMENDATIONS
    }

# ===== 🔧 상태 확인 =====
@router.get(
    "/health",
    tags=["🔧 상태 확인"],
    summary="서비스 상태 확인",
    description=desc_health_endpoint
)
async def health_check():
    """서비스 상태 확인"""
    try:
        # 바이낸스 상태 확인
        binance_health = await chart_service.get_chart_health()

        return {
            "status": "healthy",
            "timestamp": binance_health["now_utc"],
            "exchanges": {
                "binance": binance_health["status"]
            },
            "message": "차트 서비스가 정상적으로 작동 중입니다."
        }
    except Exception as e:
        return {
            "status": "error",
            "timestamp": "2025-08-30T00:00:00Z",
            "error": str(e),
            "message": "서비스에 문제가 발생했습니다."
        }

