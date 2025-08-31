"""
자동 매매 API 라우터
거래 신호를 기반으로 자동 매매 실행 및 관리
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional, Literal
from src.app.autotrading.trading_service import TradingService
from src.app.autotrading.service import ChartService

router = APIRouter(prefix="/trading")

# 거래 서비스 인스턴스
trading_service = TradingService(testnet=True)
chart_service = ChartService(exchange_type="binance")


@router.get(
    "/account/status",
    tags=["💰 거래 계정"],
    summary="계정 상태 확인",
    description="Binance 계정의 잔고 및 상태 정보를 조회합니다."
)
async def get_account_status():
    """계정 상태 확인"""
    try:
        result = await trading_service.get_account_status()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/execute/signal",
    tags=["🚀 자동 매매"],
    summary="거래 신호 실행",
    description="거래 신호를 기반으로 자동 매매를 실행합니다."
)
async def execute_trading_signal(
    market: str = Query(..., description="거래 마켓 (예: BTC/USDT)"),
    signal: str = Query(..., description="거래 신호 (BUY/SELL/HOLD)"),
    quantity: float = Query(..., description="거래 수량"),
    order_type: Literal['market', 'limit'] = Query('market', description="주문 타입"),
    price: Optional[float] = Query(None, description="지정가 주문 시 가격")
):
    """거래 신호 실행"""
    try:
        result = await trading_service.execute_trading_signal(
            market=market,
            signal=signal,
            quantity=quantity,
            order_type=order_type,
            price=price
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/execute/strategy",
    tags=["🚀 자동 매매"],
    summary="전략 실행",
    description="거래 신호 데이터를 기반으로 리스크 관리와 함께 전략을 실행합니다."
)
async def execute_strategy(
    market: str = Query(..., description="거래 마켓 (예: BTC/USDT)"),
    risk_per_trade: float = Query(0.01, description="거래당 리스크 비율 (기본값: 1%)"),
    order_type: Literal['market', 'limit'] = Query('market', description="주문 타입")
):
    """전략 실행"""
    try:
        # 먼저 거래 신호 데이터 조회
        signal_data = await chart_service.get_trading_signal_with_storage(
            market=market,
            tf="minutes:60",
            count=100
        )

        # 전략 실행
        result = await trading_service.execute_strategy(
            market=market,
            signal_data=signal_data,
            risk_per_trade=risk_per_trade,
            order_type=order_type
        )

        return {
            "signal_data": signal_data,
            "strategy_result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/orders/{order_id}/status",
    tags=["📋 주문 관리"],
    summary="주문 상태 조회",
    description="특정 주문의 상태를 조회합니다."
)
async def get_order_status(
    order_id: str,
    market: str = Query(..., description="거래 마켓")
):
    """주문 상태 조회"""
    try:
        result = await trading_service.get_order_status(order_id, market)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/orders/{order_id}",
    tags=["📋 주문 관리"],
    summary="주문 취소",
    description="특정 주문을 취소합니다."
)
async def cancel_order(
    order_id: str,
    market: str = Query(..., description="거래 마켓")
):
    """주문 취소"""
    try:
        result = await trading_service.cancel_order(order_id, market)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/orders/open",
    tags=["📋 주문 관리"],
    summary="미체결 주문 조회",
    description="현재 미체결된 주문들을 조회합니다."
)
async def get_open_orders(
    market: Optional[str] = Query(None, description="특정 마켓 (선택사항)")
):
    """미체결 주문 조회"""
    try:
        result = await trading_service.get_open_orders(market)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/test/connection",
    tags=["🧪 테스트"],
    summary="연결 테스트",
    description="Binance API 연결 상태를 테스트합니다."
)
async def test_connection():
    """연결 테스트"""
    try:
        # Binance 연결 테스트
        health_check = await chart_service.exchange.get_chart_health()

        # 계정 상태 테스트
        account_status = await trading_service.get_account_status()

        return {
            "status": "success",
            "testnet": True,
            "binance_connection": health_check,
            "account_status": account_status,
            "timestamp": health_check.get("now_utc")
        }
    except Exception as e:
        return {
            "status": "error",
            "testnet": True,
            "error": str(e),
            "timestamp": None
        }
