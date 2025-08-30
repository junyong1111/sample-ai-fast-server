from fastapi import APIRouter, Depends, Query, HTTPException
from datetime import datetime
from typing import List

from .model import (
    MarketDataRequest, MarketDataResponse, SignalResponse, HealthResponse,
    ExchangeType, ExchangeStatus, StoredKlineData, StoredSignal
)
from .service import (
    MarketDataServiceFactory, TechnicalAnalysisService,
    SignalGenerationService, AutotradingService, MongoDBService
)

router = APIRouter(prefix="/autotrading", tags=["자동매매"])

# MongoDB 서비스 인스턴스
mongodb_service = MongoDBService()

# 의존성 주입을 위한 팩토리 함수들
def get_autotrading_service() -> AutotradingService:
    """자동매매 서비스 의존성"""
    return AutotradingService(mongodb_service)

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """헬스 체크 - 지원하는 거래소 목록 포함"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        version="2.0.0",
        exchanges=[ExchangeType.BINANCE, ExchangeType.UPBIT]
    )

@router.get("/exchanges/status", response_model=List[ExchangeStatus])
async def get_exchanges_status():
    """거래소별 상태 조회"""
    # 실제 구현에서는 각 거래소의 상태를 확인해야 함
    return [
        ExchangeStatus(
            exchange=ExchangeType.BINANCE,
            status="active",
            last_update=datetime.now(),
            symbols_count=1000
        ),
        ExchangeStatus(
            exchange=ExchangeType.UPBIT,
            status="active",
            last_update=datetime.now(),
            symbols_count=200
        )
    ]

@router.post("/signals", response_model=SignalResponse)
async def get_trading_signal(
    request: MarketDataRequest,
    autotrading_service: AutotradingService = Depends(get_autotrading_service)
):
    """거래 신호 조회 - 거래소 선택 가능"""
    try:
        signal = await autotrading_service.get_trading_signal(request)
        return signal
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"신호 생성 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/signals/{symbol}", response_model=SignalResponse)
async def get_trading_signal_by_symbol(
    symbol: str,
    exchange: ExchangeType = Query(..., description="거래소 선택"),
    interval: str = Query("1d", description="시간 간격"),
    limit: int = Query(200, ge=50, le=1000, description="데이터 개수"),
    autotrading_service: AutotradingService = Depends(get_autotrading_service)
):
    """심볼별 거래 신호 조회 - 거래소 지정"""
    request = MarketDataRequest(
        symbol=symbol,
        interval=interval,
        limit=limit,
        exchange=exchange
    )

    try:
        signal = await autotrading_service.get_trading_signal(request)
        return signal
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"신호 생성 중 오류가 발생했습니다: {str(e)}"
        )

@router.post("/signals/multi-exchange", response_model=List[SignalResponse])
async def get_multi_exchange_signals(
    requests: List[MarketDataRequest],
    autotrading_service: AutotradingService = Depends(get_autotrading_service)
):
    """여러 거래소에서 동시에 신호 조회"""
    if len(requests) > 10:
        raise HTTPException(
            status_code=400,
            detail="한 번에 최대 10개 거래소까지만 조회 가능합니다"
        )

    try:
        signals = await autotrading_service.get_multi_exchange_signals(requests)
        return signals
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"멀티 거래소 신호 생성 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/market-data/{symbol}", response_model=MarketDataResponse)
async def get_market_data(
    symbol: str,
    exchange: ExchangeType = Query(..., description="거래소 선택"),
    interval: str = Query("1d", description="시간 간격"),
    limit: int = Query(200, ge=50, le=1000, description="데이터 개수")
):
    """시장 데이터 조회 - 거래소별"""
    request = MarketDataRequest(
        symbol=symbol,
        interval=interval,
        limit=limit,
        exchange=exchange
    )

    try:
        market_data_service = MarketDataServiceFactory.create_service(exchange, mongodb_service)
        market_data = await market_data_service.get_klines(request)
        return market_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"시장 데이터 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/signals/compare/{symbol}")
async def compare_exchanges_signals(
    symbol: str,
    interval: str = Query("1d", description="시간 간격"),
    limit: int = Query(200, ge=50, le=1000, description="데이터 개수"),
    autotrading_service: AutotradingService = Depends(get_autotrading_service)
):
    """동일 심볼에 대해 여러 거래소 신호 비교"""
    # 바이낸스와 업비트에서 동시에 신호 조회
    requests = [
        MarketDataRequest(
            symbol=symbol,
            interval=interval,
            limit=limit,
            exchange=ExchangeType.BINANCE
        ),
        MarketDataRequest(
            symbol=symbol,
            interval=interval,
            limit=limit,
            exchange=ExchangeType.UPBIT
        )
    ]

    try:
        signals = await autotrading_service.get_multi_exchange_signals(requests)

        # 거래소별 신호 비교 결과
        comparison = {}
        for signal in signals:
            exchange = signal.exchange
            comparison[exchange] = {
                "action": signal.signal.action,
                "confidence": signal.signal.confidence,
                "score": signal.signal.score,
                "recommendation": signal.analysis.recommendation,
                "overall_score": signal.analysis.overall_score,
                "timestamp": signal.timestamp
            }

        return {
            "symbol": symbol,
            "interval": interval,
            "comparison": comparison,
            "timestamp": datetime.now()
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"거래소 비교 신호 생성 중 오류가 발생했습니다: {str(e)}"
        )

# ===== MongoDB 저장 데이터 조회 엔드포인트 =====

@router.get("/stored/klines/{symbol}", response_model=List[StoredKlineData])
async def get_stored_klines(
    symbol: str,
    exchange: ExchangeType = Query(..., description="거래소 선택"),
    interval: str = Query("1d", description="시간 간격"),
    limit: int = Query(200, ge=1, le=1000, description="데이터 개수")
):
    """저장된 K라인 데이터 조회"""
    try:
        klines = await mongodb_service.get_stored_klines(exchange, symbol, interval, limit)
        return klines
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"저장된 K라인 데이터 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/stored/signals/{symbol}", response_model=List[StoredSignal])
async def get_stored_signals(
    symbol: str,
    exchange: ExchangeType = Query(..., description="거래소 선택"),
    interval: str = Query("1d", description="시간 간격"),
    limit: int = Query(100, ge=1, le=500, description="데이터 개수")
):
    """저장된 신호 데이터 조회"""
    try:
        signals = await mongodb_service.get_stored_signals(exchange, symbol, interval, limit)
        return signals
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"저장된 신호 데이터 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/stored/latest-signal/{symbol}")
async def get_latest_stored_signal(
    symbol: str,
    exchange: ExchangeType = Query(..., description="거래소 선택"),
    interval: str = Query("1d", description="시간 간격")
):
    """최신 저장된 신호 데이터 조회"""
    try:
        signal = await mongodb_service.get_latest_signal(exchange, symbol, interval)
        if signal:
            return signal
        else:
            raise HTTPException(
                status_code=404,
                detail=f"해당 조건의 저장된 신호 데이터를 찾을 수 없습니다"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"최신 신호 데이터 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/stored/stats/{symbol}")
async def get_stored_data_stats(
    symbol: str,
    exchange: ExchangeType = Query(..., description="거래소 선택"),
    interval: str = Query("1d", description="시간 간격")
):
    """저장된 데이터 통계 조회"""
    try:
        # K라인 데이터 개수
        klines_count = await mongodb_service.klines_collection.count_documents({
            "exchange": exchange,
            "symbol": symbol,
            "interval": interval
        })

        # 신호 데이터 개수
        signals_count = await mongodb_service.signals_collection.count_documents({
            "exchange": exchange,
            "symbol": symbol,
            "interval": interval
        })

        # 최신 데이터 시간
        latest_kline = await mongodb_service.klines_collection.find_one(
            {"exchange": exchange, "symbol": symbol, "interval": interval},
            sort=[("open_time", -1)]
        )

        latest_signal = await mongodb_service.signals_collection.find_one(
            {"exchange": exchange, "symbol": symbol, "interval": interval},
            sort=[("timestamp", -1)]
        )

        return {
            "exchange": exchange,
            "symbol": symbol,
            "interval": interval,
            "klines_count": klines_count,
            "signals_count": signals_count,
            "latest_kline_time": latest_kline["open_time"] if latest_kline else None,
            "latest_signal_time": latest_signal["timestamp"] if latest_signal else None,
            "timestamp": datetime.now()
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"데이터 통계 조회 중 오류가 발생했습니다: {str(e)}"
        )

