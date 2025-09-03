"""
정량지표 (차트기반) 자동매매 API 라우터
N8n 에이전트 호환 엔드포인트 제공
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Dict, Any, Optional, Literal
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from .quantitative_service import QuantitativeService
from .service import ChartService

router = APIRouter(prefix="/quantitative")

# 서비스 인스턴스
quantitative_service = QuantitativeService()
chart_service = ChartService(exchange_type="binance")


class QuantitativeRequest(BaseModel):
    """정량지표 분석 요청 모델"""
    market: str = Field(..., description="거래 마켓 (예: BTC/USDT)")
    timeframe: Literal["minutes:1", "minutes:5", "minutes:15", "minutes:30", "minutes:60", "minutes:240", "days"] = Field("minutes:60", description="시간프레임")
    count: int = Field(200, description="캔들 개수 (기본값: 200)")
    exchange: Literal["binance", "upbit"] = Field("binance", description="거래소")
    testnet: bool = Field(True, description="테스트넷 사용 여부")


class QuantitativeResponse(BaseModel):
    """정량지표 분석 응답 모델"""
    status: str = Field(..., description="상태 (success/error)")
    market: str = Field(..., description="거래 마켓")
    timeframe: str = Field(..., description="시간프레임")
    timestamp: str = Field(..., description="분석 시간")

    # 레짐 정보
    regime: str = Field(..., description="시장 레짐 (trend/range)")
    regime_confidence: float = Field(..., description="레짐 신뢰도 (0-1)")

    # 기술적 지표
    indicators: Dict[str, Any] = Field(..., description="기술적 지표 값들")

    # 점수 정보
    scores: Dict[str, float] = Field(..., description="지표별 점수 (-1 ~ +1)")
    weighted_score: float = Field(..., description="가중치 적용 최종 점수")

    # 거래 신호
    signal: str = Field(..., description="거래 신호 (BUY/SELL/HOLD)")
    confidence: float = Field(..., description="신호 신뢰도 (0-1)")

    # 메타데이터
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")


@router.post(
    "/analyze",
    response_model=QuantitativeResponse,
    tags=["📊 정량지표"],
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
            "testnet": True
        }
    )
):
    """
    정량지표 분석 실행

    N8n에서 정기적으로 호출하여 거래 신호를 생성합니다.
    """
    try:
        # 정량지표 분석 실행
        result = await quantitative_service.analyze_market(
            market=request.market,
            timeframe=request.timeframe,
            count=request.count,
            exchange=request.exchange,
            testnet=request.testnet
        )

        return QuantitativeResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"정량지표 분석 실패: {str(e)}"
        )


@router.get(
    "/analyze/simple",
    tags=["📊 정량지표"],
    summary="간단한 정량지표 분석 (GET 방식)",
    description="GET 방식으로 간단한 정량지표 분석을 수행합니다."
)
async def analyze_quantitative_simple(
    market: str = Query(..., description="거래 마켓 (예: BTC/USDT)"),
    timeframe: Literal["minutes:1", "minutes:5", "minutes:15", "minutes:30", "minutes:60", "minutes:240", "days"] = Query("minutes:60", description="시간프레임"),
    count: int = Query(200, description="캔들 개수"),
    exchange: Literal["binance", "upbit"] = Query("binance", description="거래소"),
    testnet: bool = Query(True, description="테스트넷 사용 여부")
):
    """
    간단한 정량지표 분석 (GET 방식)

    N8n에서 GET 요청으로 쉽게 호출할 수 있습니다.
    """
    try:
        # 정량지표 분석 실행
        result = await quantitative_service.analyze_market(
            market=market,
            timeframe=timeframe,
            count=count,
            exchange=exchange,
            testnet=testnet
        )

        return {
            "status": "success",
            "data": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.get(
    "/health",
    tags=["🔍 헬스체크"],
    summary="정량지표 서비스 헬스체크",
    description="정량지표 서비스의 상태를 확인합니다."
)
async def health_check():
    """정량지표 서비스 헬스체크"""
    try:
        # 기본 연결 테스트
        health_status = await quantitative_service.health_check()

        return {
            "status": "healthy",
            "service": "quantitative_indicators",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": health_status
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "quantitative_indicators",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.get(
    "/indicators/list",
    tags=["📊 정량지표"],
    summary="지원하는 기술적 지표 목록",
    description="현재 지원하는 기술적 지표들의 목록을 조회합니다."
)
async def get_supported_indicators():
    """지원하는 기술적 지표 목록"""
    return {
        "status": "success",
        "indicators": {
            "trend": {
                "ADX": "Average Directional Index (추세 강도)",
                "EMA200": "200일 지수이동평균",
                "MACD": "Moving Average Convergence Divergence"
            },
            "momentum": {
                "RSI": "Relative Strength Index",
                "Stochastic": "Stochastic Oscillator"
            },
            "volatility": {
                "Bollinger_Bands": "Bollinger Bands",
                "ATR": "Average True Range"
            },
            "volume": {
                "Volume_Z_Score": "거래량 Z-Score",
                "OBV": "On Balance Volume"
            }
        },
        "regimes": {
            "trend": "추세장 (ADX > 25, 가격이 200EMA 위/아래)",
            "range": "횡보장 (ADX < 20, EMA 근처 박스권)"
        },
        "timeframes": [
            "minutes:1", "minutes:5", "minutes:15",
            "minutes:30", "minutes:60", "minutes:240", "days"
        ],
        "exchanges": ["binance", "upbit"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get(
    "/regime/weights",
    tags=["📊 정량지표"],
    summary="레짐별 가중치 조회",
    description="추세장과 횡보장의 지표별 가중치를 조회합니다."
)
async def get_regime_weights():
    """레짐별 가중치 조회"""
    return {
        "status": "success",
        "weights": {
            "trend_regime": {
                "momentum": 0.40,
                "macd": 0.20,
                "return_volatility": 0.15,
                "volume": 0.15,
                "rsi": 0.05,
                "bollinger": 0.05
            },
            "range_regime": {
                "rsi": 0.25,
                "bollinger": 0.25,
                "volume": 0.20,
                "momentum": 0.15,
                "macd": 0.10,
                "return_volatility": 0.05
            }
        },
        "description": {
            "trend_regime": "추세장에서는 모멘텀과 MACD에 높은 가중치",
            "range_regime": "횡보장에서는 RSI와 볼린저 밴드에 높은 가중치"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
