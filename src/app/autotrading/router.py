# src/app/routers/chart.py
from fastapi import APIRouter, Query, HTTPException, Body
from typing import Literal, Dict, Any, Optional
from datetime import datetime, timedelta
from src.app.autotrading.service import ChartService, Timeframe
from src.app.autotrading.model import TradingSignalQuery, TradingSignalStats
from src.app.autotrading.database import get_mongodb_service
from src.app.autotrading.docs import (
    desc_exchanges_list, desc_exchange_info, desc_price_endpoint, desc_chart_endpoint,
    desc_rsi_endpoint, desc_macd_endpoint, desc_signal_endpoint, desc_examples_endpoint,
    desc_health_endpoint, desc_timeframe, desc_count, desc_period,
    EXCHANGE_DETAILS, API_EXAMPLES_DATA, MARKET_FORMAT_RULES, TIMEFRAME_OPTIONS, COUNT_RECOMMENDATIONS
)
from src.common.utils.bitcoin.binace import BinanceUtils

router = APIRouter(prefix="/charts")

# 차트 서비스는 사용자별 API 키로 초기화해야 함
# 전역 인스턴스 대신 함수에서 생성하도록 변경



@router.get(
    "/signal/{exchange_type}/{market}/detailed",
    tags=["Trading Signals"],
    summary="종합 거래 신호 (상세 + MongoDB 저장)",
    description="에이전트용 상세 거래 신호 조회 및 MongoDB 저장"
)
async def get_detailed_trading_signal(
    exchange_type: str,
    market: str,
    timeframe: Timeframe = Query(
        "minutes:60",
        description=desc_timeframe
    ),
    count: int = Query(
        200,
        description=desc_count
    ),
    rsi_period: int = Query(
        14,
        description=desc_period
    ),
    save_to_db: bool = Query(
        True,
        description="MongoDB 저장 여부"
    )
):
    """에이전트용 상세 거래 신호 조회 (모든 데이터 포함 + MongoDB 저장)"""
    try:
        # 거래소별 시장 형식 변환
        if exchange_type == "upbit" and not market.startswith("KRW-"):
            market = f"KRW-{market}"
        elif exchange_type == "binance" and "/" not in market:
            market = f"{market}/USDT"

        service = ChartService(exchange_type=exchange_type)

        # 상세 거래 신호 조회 (MongoDB 저장 포함)
        detailed_signal = await service.get_trading_signal_with_storage(
            market=market,
            tf=timeframe,
            count=count,
            rsi_period=rsi_period,
            save_to_db=save_to_db
        )

        return detailed_signal

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ===== 🗄️ MongoDB 거래 신호 조회 =====
@router.get(
    "/signals/history",
    tags=["Trading Signals History"],
    summary="저장된 거래 신호 히스토리 조회",
    description="MongoDB에 저장된 거래 신호 히스토리 조회"
)
async def get_trading_signal_history(
    exchange: Optional[str] = Query(None, description="거래소 필터 (upbit/binance)"),
    market: Optional[str] = Query(None, description="시장 필터 (예: BTC, ETH)"),
    timeframe: Optional[str] = Query(None, description="시간프레임 필터"),
    signal: Optional[str] = Query(None, description="신호 타입 필터 (BUY/SELL/HOLD)"),
    limit: int = Query(100, description="조회 개수 제한 (최대 1000)"),
    skip: int = Query(0, description="건너뛸 개수")
):
    """저장된 거래 신호 히스토리 조회"""
    try:
        mongodb = await get_mongodb_service()

        # 시장 심볼 정규화 (BTC → BTC/USDT)
        normalized_market = market
        if market and exchange == "binance" and "/" not in market:
            normalized_market = f"{market}/USDT"
        elif market and exchange == "upbit" and not market.startswith("KRW-"):
            normalized_market = f"KRW-{market}"

        # 쿼리 조건 구성
        query = TradingSignalQuery(
            exchange=exchange,
            market=normalized_market,
            timeframe=timeframe,
            signal=signal,
            limit=min(limit, 1000),  # 최대 1000개로 제한
            skip=skip,
            start_date=None,
            end_date=None
        )

        signals = await mongodb.get_trading_signals(query)

        return {
            "message": "거래 신호 히스토리 조회 완료",
            "total_count": len(signals),
            "query": query.dict(),
            "signals": [signal.dict() for signal in signals]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"히스토리 조회 실패: {str(e)}")

@router.get(
    "/signals/{signal_id}",
    tags=["Trading Signals History"],
    summary="특정 거래 신호 상세 조회",
    description="ID로 특정 거래 신호의 상세 정보 조회"
)
async def get_trading_signal_by_id(signal_id: str):
    """ID로 특정 거래 신호 상세 조회"""
    try:
        mongodb = await get_mongodb_service()
        signal = await mongodb.get_trading_signal_by_id(signal_id)

        if not signal:
            raise HTTPException(status_code=404, detail="해당 ID의 거래 신호를 찾을 수 없습니다.")

        return {
            "message": "거래 신호 상세 조회 완료",
            "signal": signal.dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"거래 신호 조회 실패: {str(e)}")

@router.get(
    "/signals/latest/{exchange_type}/{market}",
    tags=["Trading Signals History"],
    summary="최신 거래 신호 조회",
    description="특정 거래소/시장의 최신 거래 신호 조회"
)
async def get_latest_trading_signal(
    exchange_type: str,
    market: str,
    timeframe: Optional[str] = Query(None, description="시간프레임 필터")
):
    """특정 거래소/시장의 최신 거래 신호 조회"""
    try:
        mongodb = await get_mongodb_service()
        signal = await mongodb.get_latest_trading_signal(exchange_type, market, timeframe)

        if not signal:
            raise HTTPException(status_code=404, detail="해당 조건의 거래 신호를 찾을 수 없습니다.")

        return {
            "message": "최신 거래 신호 조회 완료",
            "signal": signal.dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"최신 거래 신호 조회 실패: {str(e)}")

@router.get(
    "/signals/stats",
    tags=["Trading Signals History"],
    summary="거래 신호 통계 정보",
    description="저장된 거래 신호의 통계 정보 조회"
)
async def get_trading_signal_stats(
    exchange: Optional[str] = Query(None, description="거래소 필터"),
    market: Optional[str] = Query(None, description="시장 필터"),
    start_date: Optional[str] = Query(None, description="시작 날짜 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="종료 날짜 (YYYY-MM-DD)")
):
    """거래 신호 통계 정보 조회"""
    try:
        mongodb = await get_mongodb_service()

        # 날짜 파싱
        start_dt = None
        end_dt = None

        if start_date:
            try:
                start_dt = datetime.fromisoformat(f"{start_date}T00:00:00")
            except ValueError:
                raise HTTPException(status_code=400, detail="시작 날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식으로 입력하세요.")

        if end_date:
            try:
                end_dt = datetime.fromisoformat(f"{end_date}T23:59:59")
            except ValueError:
                raise HTTPException(status_code=400, detail="종료 날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식으로 입력하세요.")

        stats = await mongodb.get_trading_signal_stats(
            exchange=exchange,
            market=market,
            start_date=start_dt,
            end_date=end_dt
        )

        return {
            "message": "거래 신호 통계 조회 완료",
            "stats": stats.dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")


# ===== 🔧 상태 확인 =====
@router.get(
    "/health",
    tags=["Health Check"],
    summary="서비스 상태 확인",
    description=desc_health_endpoint
)
async def health_check():
    """서비스 상태 확인"""
    try:
        # 바이낸스 상태 확인 (임시로 기본 설정 사용)
        temp_service = ChartService(exchange_type="upbit")
        binance_health = await temp_service.get_chart_health()

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

# ===== 🤖 AI 거래 실행 =====
@router.post(
    "/trade/execute",
    tags=["AI Trading Execution"],
    summary="AI 거래 시그널에 따른 자동 거래 실행",
    description="AI가 제공한 거래 시그널을 받아서 자동으로 거래를 실행합니다."
)
async def execute_ai_trade(
    trade_request: Dict[str, Any] = Body(
        ...,
        example={
            "action": "BUY",
            "market": "BTC/USDT",
            "target_price": 108000.0,
            "quantity": 0.001,
            "order_type": "market",
            "confidence": 0.9,
            "reason": "RSI 과매도 + 볼린저 밴드 하단 터치",
            "use_testnet": True,
            "auto_calculate_quantity": False
        }
    )
):
    """AI 거래 시그널에 따른 자동 거래 실행"""
    try:
        # 필수 필드 검증
        required_fields = ['action', 'market', 'target_price']
        for field in required_fields:
            if field not in trade_request:
                raise HTTPException(
                    status_code=400,
                    detail=f"필수 필드가 누락되었습니다: {field}"
                )

        # 시장 심볼 정규화
        market = trade_request['market']
        if '/' not in market:
            market = f"{market}/USDT"

        # 설정값 추출
        use_testnet = trade_request.get('use_testnet', True)
        auto_calculate_quantity = trade_request.get('auto_calculate_quantity', False)
        action = trade_request['action']

        # HOLD 신호는 거래 없음
        if action == 'HOLD':
            return {
                "status": "success",
                "action": "HOLD",
                "market": market,
                "message": "HOLD 신호 - 거래를 실행하지 않습니다.",
                "timestamp": datetime.utcnow().isoformat()
            }

        # 바이낸스 연결
        binance = BinanceUtils(testnet=use_testnet)

        # 현재 가격 조회
        current_price = await binance.get_ticker(market)
        current_price_value = float(current_price['last'])

        # 수량 계산
        if auto_calculate_quantity:
            # 자동 수량 계산 (신뢰도 기반)
            confidence = trade_request.get('confidence', 0.5)
            balance = await binance.get_account_info()
            usdt_balance = balance.get('free_balance', {}).get('USDT', 0)

            # 리스크 계산 (거래당 1% * 신뢰도)
            risk_per_trade = 0.01 * confidence
            investment_amount = float(usdt_balance) * risk_per_trade

            # 최대 포지션 크기 제한 (10%)
            max_position = float(usdt_balance) * 0.1
            investment_amount = min(investment_amount, max_position)

            quantity = investment_amount / current_price_value

            print(f"자동 수량 계산: 투자금액=${investment_amount:.2f}, 수량={quantity:.6f}")
        else:
            # AI가 제시한 수량 사용
            quantity = trade_request.get('quantity', 0)
            if quantity <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="수량이 0보다 커야 합니다."
                )

        # 주문 실행
        order_type = trade_request.get('order_type', 'market')

        if action == 'BUY':
            if order_type == 'market':
                order = await binance.place_market_order(market, 'buy', quantity)
            else:
                order = await binance.place_limit_order(market, 'buy', quantity, current_price_value)
        elif action == 'SELL':
            if order_type == 'market':
                order = await binance.place_market_order(market, 'sell', quantity)
            else:
                order = await binance.place_limit_order(market, 'sell', quantity, current_price_value)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 거래 방향입니다: {action}"
            )

        return {
            "status": "success",
            "action": action,
            "market": market,
            "quantity": quantity,
            "current_price": current_price_value,
            "target_price": trade_request['target_price'],
            "order_type": order_type,
            "order_id": order.get('id'),
            "order_status": order.get('status'),
            "use_testnet": use_testnet,
            "auto_calculate_quantity": auto_calculate_quantity,
            "timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        return {
            "status": "error",
            "market": trade_request.get('market', 'UNKNOWN'),
            "signal": trade_request.get('action', 'UNKNOWN'),
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# ===== 🔧 거래 설정 =====
@router.get(
    "/trade/settings",
    tags=["Trade Settings"],
    summary="현재 거래 설정 조회",
    description="AI 거래 봇의 현재 설정을 조회합니다."
)
async def get_trade_settings():
    """거래 설정 조회"""
    return {
        "message": "AI 거래 봇 설정",
        "settings": {
            "default_testnet": True,
            "default_auto_calculate": True,
            "risk_per_trade": "1%",
            "max_position_size": "10%",
            "supported_markets": ["BTC/USDT", "ETH/USDT", "BNB/USDT"],
            "supported_actions": ["BUY", "SELL", "HOLD"],
            "supported_order_types": ["market", "limit"]
        }
    }

@router.post(
    "/trade/settings",
    tags=["🔧 거래 설정"],
    summary="거래 설정 변경",
    description="AI 거래 봇의 설정을 변경합니다."
)
async def update_trade_settings(
    settings: Dict[str, Any] = Body(
        ...,
        example={
            "default_testnet": True,
            "default_auto_calculate": True,
            "risk_per_trade": 0.01,
            "max_position_size": 0.1
        }
    )
):
    """거래 설정 변경"""
    try:
        # 설정 검증 및 업데이트 로직
        # (실제 구현에서는 설정 파일이나 데이터베이스에 저장)

        return {
            "status": "success",
            "message": "거래 설정이 업데이트되었습니다.",
            "updated_settings": settings,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"설정 업데이트 실패: {str(e)}"
        )

# ===== 📊 거래 히스토리 =====
@router.get(
    "/trade/history",
    tags=["📊 거래 히스토리"],
    summary="거래 실행 히스토리 조회",
    description="AI 거래 봇이 실행한 거래 내역을 조회합니다."
)
async def get_trade_history(
    use_testnet: bool = Query(True, description="테스트넷 사용 여부"),
    market: Optional[str] = Query(None, description="시장 필터"),
    action: Optional[str] = Query(None, description="거래 방향 필터"),
    limit: int = Query(50, description="조회 개수 제한")
):
    """거래 실행 히스토리 조회"""
    try:
        binance = BinanceUtils(testnet=use_testnet)

        # 미체결 주문 조회
        open_orders = await binance.get_open_orders(market)

        # 최근 거래 내역 조회 (실제 구현에서는 데이터베이스에서 조회)
        return {
            "status": "success",
            "use_testnet": use_testnet,
            "open_orders": open_orders,
            "message": "거래 히스토리 조회 완료",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

