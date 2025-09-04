"""
자동 매매 API 라우터
거래 신호를 기반으로 자동 매매 실행 및 관리
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Dict, Any, Optional, Literal
from datetime import datetime, timezone
from src.app.autotrading.trading_service import TradingService
from src.app.autotrading.service import ChartService

router = APIRouter(prefix="/trading")

# 거래 서비스는 사용자별 API 키로 초기화해야 함
# 전역 인스턴스 대신 함수에서 생성하도록 변경


@router.get(
    "/account/status",
    tags=["💰 거래 계정"],
    summary="계정 상태 확인",
    description="Binance 계정의 잔고 및 상태 정보를 조회합니다."
)
async def get_account_status(
    use_testnet: bool = Query(True, description="테스트넷 사용 여부 (기본값: True)")
):
    """계정 상태 확인"""
    try:
        # 테스트넷 설정에 따른 서비스 인스턴스 생성
        trading_service_instance = TradingService(testnet=use_testnet)
        result = await trading_service_instance.get_account_status()
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
    price: Optional[float] = Query(None, description="지정가 주문 시 가격"),
    use_testnet: bool = Query(True, description="테스트넷 사용 여부 (기본값: True)")
):
    """거래 신호 실행"""
    try:
                # 테스트넷 설정에 따른 서비스 인스턴스 생성
        trading_service_instance = TradingService(testnet=use_testnet)

        # 거래 실행
        result = await trading_service_instance.execute_trading_signal(
            market=market,
            signal=signal,
            quantity=quantity,
            order_type=order_type,
            price=price
        )

        # 거래 신호 저장 (성공한 경우에만)
        if result.get('status') == 'success':
            try:
                signal_data = {
                    "market": market,
                    "signal": signal,
                    "quantity": quantity,
                    "order_type": order_type,
                    "price": price
                }
                await trading_service_instance.save_trading_signal(signal_data)
            except Exception as e:
                print(f"거래 신호 저장 실패: {e}")

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

        # 전략 실행 (임시로 기본 API 키 사용 - 실제로는 사용자별 API 키 필요)
        # TODO: 사용자 인증 후 사용자별 API 키로 초기화
        temp_trading_service = TradingService(
            api_key="temp_key",  # 임시 키
            secret_key="temp_secret",  # 임시 키
            testnet=True
        )
        result = await temp_trading_service.execute_strategy(
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
        # TODO: 사용자 인증 후 사용자별 API 키로 초기화
        temp_trading_service = TradingService(
            api_key="temp_key",
            secret_key="temp_secret",
            testnet=True
        )
        result = await temp_trading_service.get_order_status(order_id, market)
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
        # TODO: 사용자 인증 후 사용자별 API 키로 초기화
        temp_trading_service = TradingService(
            api_key="temp_key",
            secret_key="temp_secret",
            testnet=True
        )
        result = await temp_trading_service.cancel_order(order_id, market)
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
    market: Optional[str] = Query(None, description="특정 마켓 (선택사항)"),
    use_testnet: bool = Query(True, description="테스트넷 사용 여부 (기본값: True)")
):
    """미체결 주문 조회"""
    try:
        trading_service_instance = TradingService(testnet=use_testnet)
        result = await trading_service_instance.get_open_orders(market)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/orders/history",
    tags=["📋 주문 관리"],
    summary="거래 내역 조회",
    description="완료된 거래 내역을 조회합니다."
)
async def get_trade_history(
    market: Optional[str] = Query(None, description="특정 마켓 (선택사항)"),
    limit: int = Query(50, description="조회 개수 제한"),
    use_testnet: bool = Query(True, description="테스트넷 사용 여부 (기본값: True)")
):
    """거래 내역 조회"""
    try:
        trading_service_instance = TradingService(testnet=use_testnet)

        # 시장 심볼 정규화
        if market and '/' not in market:
            market = f"{market}/USDT"

        # 미체결 주문과 완료된 주문 조회
        open_orders = await trading_service_instance.get_open_orders(market)

        # 최근 거래 내역 조회 (실제 구현에서는 데이터베이스에서 조회)
        # 현재는 바이낸스 API로만 조회 가능
        return {
            "status": "success",
            "use_testnet": use_testnet,
            "market": market,
            "open_orders": open_orders.get('open_orders', []),
            "open_orders_count": open_orders.get('count', 0),
            "message": "거래 내역 조회 완료",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.get(
    "/signals",
    tags=["📊 거래 신호"],
    summary="저장된 거래 신호 조회",
    description="저장된 거래 신호들을 조회합니다."
)
async def get_trading_signals(
    market: Optional[str] = Query(None, description="특정 마켓 (선택사항)"),
    limit: int = Query(50, description="조회 개수 제한"),
    use_testnet: bool = Query(True, description="테스트넷 사용 여부 (기본값: True)")
):
    """저장된 거래 신호 조회"""
    try:
        trading_service_instance = TradingService(testnet=use_testnet)
        result = await trading_service_instance.get_trading_signals(market, limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/signals/save",
    tags=["📊 거래 신호"],
    summary="거래 신호 저장",
    description="거래 신호를 저장합니다."
)
async def save_trading_signal(
    signal_data: Dict[str, Any] = Body(
        ...,
        example={
            "market": "BTC/USDT",
            "signal": "BUY",
            "quantity": 0.001,
            "order_type": "market",
            "price": None
        }
    ),
    use_testnet: bool = Query(True, description="테스트넷 사용 여부 (기본값: True)")
):
    """거래 신호 저장"""
    try:
        trading_service_instance = TradingService(testnet=use_testnet)
        result = await trading_service_instance.save_trading_signal(signal_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/test/connection",
    tags=["🧪 테스트"],
    summary="연결 테스트",
    description="Binance API 연결 상태를 테스트합니다."
)
async def test_connection(
    use_testnet: bool = Query(True, description="테스트넷 사용 여부 (기본값: True)")
):
    """연결 테스트"""
    try:
        # 테스트넷 설정에 따른 서비스 인스턴스 생성
        trading_service_instance = TradingService(testnet=use_testnet)
        chart_service_instance = ChartService(exchange_type="binance", testnet=use_testnet)

        # Binance 연결 테스트
        health_check = await chart_service_instance.exchange.get_chart_health()

        # 계정 상태 테스트
        account_status = await trading_service_instance.get_account_status()

        return {
            "status": "success",
            "testnet": use_testnet,
            "binance_connection": health_check,
            "account_status": account_status,
            "timestamp": health_check.get("now_utc")
        }
    except Exception as e:
        return {
            "status": "error",
            "testnet": use_testnet,
            "error": str(e),
            "timestamp": None
        }

@router.get(
    "/data/integrated",
    tags=["📊 통합 거래 데이터"],
    summary="거래 신호와 거래 실행 결과 통합 조회",
    description="거래 신호와 실제 거래 실행 결과를 통합하여 조회합니다."
)
async def get_integrated_trading_data(
    exchange: str = Query("binance", description="거래소"),
    market: str = Query(..., description="거래 마켓 (예: BTC)"),
    testnet: bool = Query(True, description="테스트넷 사용 여부"),
    limit: int = Query(50, description="조회 개수 제한")
):
    """거래 신호와 거래 실행 결과 통합 조회"""
    try:
        from .database import get_mongodb_service

        mongodb = await get_mongodb_service()

        # 시장 심볼 정규화
        if '/' not in market:
            market = f"{market}/USDT"

        # 통합 데이터 조회
        integrated_data = await mongodb.get_trading_data_integrated(
            exchange=exchange,
            market=market,
            testnet=testnet,
            limit=limit
        )

        return integrated_data

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"통합 거래 데이터 조회 실패: {str(e)}"
        )

@router.get(
    "/executions",
    tags=["📊 거래 실행 결과"],
    summary="거래 실행 결과 조회",
    description="저장된 거래 실행 결과들을 조회합니다."
)
async def get_trading_executions(
    exchange: Optional[str] = Query(None, description="거래소 필터"),
    market: Optional[str] = Query(None, description="시장 필터"),
    testnet: Optional[bool] = Query(None, description="테스트넷 사용 여부"),
    action: Optional[str] = Query(None, description="거래 방향 필터"),
    order_type: Optional[str] = Query(None, description="주문 타입 필터"),
    limit: int = Query(50, description="조회 개수 제한"),
    skip: int = Query(0, description="건너뛸 개수")
):
    """거래 실행 결과 조회"""
    try:
        from .database import get_mongodb_service
        from .model import TradingExecutionQuery

        mongodb = await get_mongodb_service()

        # 시장 심볼 정규화
        if market and '/' not in market:
            market = f"{market}/USDT"

        # 쿼리 구성
        query = TradingExecutionQuery(
            exchange=exchange,
            market=market,
            testnet=testnet,
            action=action,
            order_type=order_type,
            limit=limit,
            skip=skip,
            start_date=None,
            end_date=None
        )

        # 거래 실행 결과 조회
        executions = await mongodb.get_trading_executions(query)

        return {
            "status": "success",
            "executions": [execution.dict() for execution in executions],
            "count": len(executions),
            "query": query.dict(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"거래 실행 결과 조회 실패: {str(e)}"
        )
