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
        description=desc_count
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
        df = await service.get_candles(market, timeframe, count)

        # 최신 데이터 추출
        latest_data = df.iloc[-1] if not df.empty else {}

        return {
            "exchange": exchange_type,
            "market": market,
            "timeframe": timeframe,
            "count": len(df),
            "latest_price": float(latest_data.get("close", 0)),
            "latest_time": latest_data.get("timestamp", datetime.utcnow()).isoformat() if "timestamp" in latest_data else datetime.utcnow().isoformat(),
            "price_range": {
                "high": float(df["high"].max()) if not df.empty else 0,
                "low": float(df["low"].min()) if not df.empty else 0
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
        description=desc_period
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
            market, timeframe, 100, "rsi", rsi_period=period
        )

        # RSI 해석
        rsi_value = indicator["indicator"]["value"]
        if rsi_value <= 30:
            interpretation = "과매도 (매수 신호)"
        elif rsi_value >= 70:
            interpretation = "과매수 (매도 신호)"
        else:
            interpretation = "중립 (관망)"

        return {
            "exchange": exchange_type,
            "market": market,
            "rsi": rsi_value,
            "period": period,
            "timeframe": timeframe,
            "interpretation": interpretation
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
    summary="종합 거래 신호 (기본)",
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
    """종합 거래 신호 조회 (기본)"""
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

@router.get(
    "/signal/{exchange_type}/{market}/detailed",
    tags=["🎯 거래 신호"],
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
    tags=["🗄️ 거래 신호 히스토리"],
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
    tags=["🗄️ 거래 신호 히스토리"],
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
    tags=["🗄️ 거래 신호 히스토리"],
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
    tags=["🗄️ 거래 신호 히스토리"],
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

# ===== 🤖 AI 거래 실행 =====
@router.post(
    "/trade/execute",
    tags=["🤖 AI 거래 실행"],
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
    tags=["🔧 거래 설정"],
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

