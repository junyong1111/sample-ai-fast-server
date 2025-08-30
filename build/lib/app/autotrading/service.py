import asyncio
from typing import List, Optional, Dict, Any
from decimal import Decimal
import httpx
from fastapi import HTTPException
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

from .model import (
    KlineData, MarketDataRequest, MarketDataResponse, ExchangeType,
    TechnicalIndicators, TradingSignal, SignalAnalysis, SignalResponse,
    StoredKlineData, StoredSignal
)

# ===== MongoDB 저장 서비스 =====
class MongoDBService:
    """MongoDB 데이터 저장 서비스"""

    def __init__(self, connection_string: str = "mongodb://localhost:27017"):
        self.client = AsyncIOMotorClient(connection_string)
        self.db = self.client.autotrading

        # 컬렉션들
        self.klines_collection = self.db.klines
        self.signals_collection = self.db.signals

        # 인덱스 생성
        self._create_indexes()

    async def _create_indexes(self):
        """데이터베이스 인덱스 생성"""
        # K라인 데이터 인덱스
        await self.klines_collection.create_index([
            ("exchange", 1),
            ("symbol", 1),
            ("interval", 1),
            ("open_time", -1)
        ])
        await self.klines_collection.create_index([
            ("exchange", 1),
            ("symbol", 1),
            ("open_time", -1)
        ])

        # 신호 데이터 인덱스
        await self.signals_collection.create_index([
            ("exchange", 1),
            ("symbol", 1),
            ("interval", 1),
            ("timestamp", -1)
        ])
        await self.signals_collection.create_index([
            ("exchange", 1),
            ("symbol", 1),
            ("timestamp", -1)
        ])

    async def save_klines(self, klines: List[KlineData]) -> List[str]:
        """K라인 데이터 저장"""
        if not klines:
            return []

        # 중복 데이터 방지를 위한 필터링
        saved_ids = []
        for kline in klines:
            # 동일한 시간대의 데이터가 있는지 확인
            existing = await self.klines_collection.find_one({
                "exchange": kline.exchange,
                "symbol": kline.symbol,
                "interval": kline.interval,
                "open_time": kline.open_time
            })

            if not existing:
                # StoredKlineData로 변환
                stored_kline = StoredKlineData(
                    exchange=kline.exchange,
                    symbol=kline.symbol,
                    interval=kline.interval,
                    open_time=kline.open_time,
                    open=kline.open,
                    high=kline.high,
                    low=kline.low,
                    close=kline.close,
                    volume=kline.volume,
                    close_time=kline.close_time
                )

                result = await self.klines_collection.insert_one(stored_kline.dict())
                saved_ids.append(str(result.inserted_id))

        return saved_ids

    async def save_signal(self, signal: SignalResponse) -> str:
        """신호 데이터 저장"""
        stored_signal = StoredSignal(
            exchange=signal.exchange,
            symbol=signal.symbol,
            interval=signal.interval,
            timestamp=signal.timestamp,
            signal_data=signal
        )

        result = await self.signals_collection.insert_one(stored_signal.dict())
        return str(result.inserted_id)

    async def get_stored_klines(
        self,
        exchange: ExchangeType,
        symbol: str,
        interval: str,
        limit: int = 200
    ) -> List[StoredKlineData]:
        """저장된 K라인 데이터 조회"""
        cursor = self.klines_collection.find({
            "exchange": exchange,
            "symbol": symbol,
            "interval": interval
        }).sort("open_time", -1).limit(limit)

        klines = []
        async for doc in cursor:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
            klines.append(StoredKlineData(**doc))

        return klines[::-1]  # 시간순 정렬

    async def get_stored_signals(
        self,
        exchange: ExchangeType,
        symbol: str,
        interval: str,
        limit: int = 100
    ) -> List[StoredSignal]:
        """저장된 신호 데이터 조회"""
        cursor = self.signals_collection.find({
            "exchange": exchange,
            "symbol": symbol,
            "interval": interval
        }).sort("timestamp", -1).limit(limit)

        signals = []
        async for doc in cursor:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
            signals.append(StoredSignal(**doc))

        return signals[::-1]  # 시간순 정렬

    async def get_latest_signal(
        self,
        exchange: ExchangeType,
        symbol: str,
        interval: str
    ) -> Optional[StoredSignal]:
        """최신 신호 데이터 조회"""
        doc = await self.signals_collection.find_one({
            "exchange": exchange,
            "symbol": symbol,
            "interval": interval
        }, sort=[("timestamp", -1)])

        if doc:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
            return StoredSignal(**doc)

        return None

# ===== 거래소별 데이터 수집 서비스 =====
class BaseMarketDataService:
    """거래소 공통 데이터 수집 인터페이스"""

    def __init__(self, mongodb_service: MongoDBService):
        self.mongodb_service = mongodb_service

    async def get_klines(self, request: MarketDataRequest) -> MarketDataResponse:
        raise NotImplementedError

    def _parse_klines(self, raw_data: List, exchange: ExchangeType, symbol: str) -> List[KlineData]:
        raise NotImplementedError

class BinanceMarketDataService(BaseMarketDataService):
    """바이낸스 시장 데이터 수집 서비스"""

    def __init__(self, mongodb_service: MongoDBService, base_url: str = "https://api.binance.com"):
        super().__init__(mongodb_service)
        self.base_url = base_url.rstrip('/')

    async def get_klines(self, request: MarketDataRequest) -> MarketDataResponse:
        """바이낸스에서 K라인 데이터 수집"""
        url = f"{self.base_url}/api/v3/klines"
        params = {
            "symbol": request.symbol.upper(),
            "interval": request.interval,
            "limit": request.limit
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()

                raw_data = response.json()
                klines = self._parse_klines(raw_data, request.exchange, request.symbol)

                # MongoDB에 저장
                await self.mongodb_service.save_klines(klines)

                return MarketDataResponse(
                    exchange=request.exchange,
                    symbol=request.symbol.upper(),
                    interval=request.interval,
                    klines=klines,
                    count=len(klines),
                    timestamp=datetime.now()
                )

            except httpx.HTTPStatusError as e:
                raise HTTPException(
                    status_code=502,
                    detail=f"바이낸스 API 오류: {e.response.status_code} - {e.response.text}"
                )
            except httpx.RequestError as e:
                raise HTTPException(
                    status_code=503,
                    detail=f"네트워크 오류: {str(e)}"
                )

    def _parse_klines(self, raw_data: List, exchange: ExchangeType, symbol: str) -> List[KlineData]:
        """바이낸스 K라인 데이터 파싱"""
        klines = []
        for row in raw_data:
            kline = KlineData(
                open_time=datetime.fromtimestamp(row[0] / 1000),
                open=Decimal(str(row[1])),
                high=Decimal(str(row[2])),
                low=Decimal(str(row[3])),
                close=Decimal(str(row[4])),
                volume=Decimal(str(row[5])),
                close_time=datetime.fromtimestamp(row[6] / 1000),
                quote_volume=Decimal(str(row[7])),
                trades=int(row[8]),
                taker_buy_base=Decimal(str(row[9])),
                taker_buy_quote=Decimal(str(row[10])),
                exchange=exchange,
                symbol=symbol
            )
            klines.append(kline)
        return klines

class UpbitMarketDataService(BaseMarketDataService):
    """업비트 시장 데이터 수집 서비스"""

    def __init__(self, mongodb_service: MongoDBService, base_url: str = "https://api.upbit.com"):
        super().__init__(mongodb_service)
        self.base_url = base_url.rstrip('/')

    async def get_klines(self, request: MarketDataRequest) -> MarketDataResponse:
        """업비트에서 K라인 데이터 수집"""
        # 업비트는 한국 시장이므로 심볼 변환 필요
        upbit_symbol = self._convert_to_upbit_symbol(request.symbol)

        url = f"{self.base_url}/v1/candles/{request.interval}"
        params = {
            "market": upbit_symbol,
            "count": request.limit
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()

                raw_data = response.json()
                klines = self._parse_klines(raw_data, request.exchange, request.symbol)

                # MongoDB에 저장
                await self.mongodb_service.save_klines(klines)

                return MarketDataResponse(
                    exchange=request.exchange,
                    symbol=request.symbol,
                    interval=request.interval,
                    klines=klines,
                    count=len(klines),
                    timestamp=datetime.now()
                )

            except httpx.HTTPStatusError as e:
                raise HTTPException(
                    status_code=502,
                    detail=f"업비트 API 오류: {e.response.status_code} - {e.response.text}"
                )
            except httpx.RequestError as e:
                raise HTTPException(
                    status_code=503,
                    detail=f"네트워크 오류: {str(e)}"
                )

    def _convert_to_upbit_symbol(self, symbol: str) -> str:
        """바이낸스 심볼을 업비트 심볼로 변환"""
        # 예: BTCUSDT -> KRW-BTC
        if symbol.endswith('USDT'):
            base = symbol[:-4]
            return f"KRW-{base}"
        elif symbol.endswith('BTC'):
            base = symbol[:-3]
            return f"BTC-{base}"
        else:
            return f"KRW-{symbol}"

    def _parse_klines(self, raw_data: List, exchange: ExchangeType, symbol: str) -> List[KlineData]:
        """업비트 K라인 데이터 파싱"""
        klines = []
        for row in raw_data:
            kline = KlineData(
                open_time=datetime.fromisoformat(row['candle_date_time_kst'].replace('Z', '+00:00')),
                open=Decimal(str(row['opening_price'])),
                high=Decimal(str(row['high_price'])),
                low=Decimal(str(row['low_price'])),
                close=Decimal(str(row['trade_price'])),
                volume=Decimal(str(row['candle_acc_trade_volume'])),
                close_time=datetime.fromisoformat(row['candle_date_time_kst'].replace('Z', '+00:00')),
                exchange=exchange,
                symbol=symbol
            )
            klines.append(kline)
        return klines

class MarketDataServiceFactory:
    """거래소별 데이터 서비스 팩토리"""

    @staticmethod
    def create_service(exchange: ExchangeType, mongodb_service: MongoDBService) -> BaseMarketDataService:
        if exchange == ExchangeType.BINANCE:
            return BinanceMarketDataService(mongodb_service)
        elif exchange == ExchangeType.UPBIT:
            return UpbitMarketDataService(mongodb_service)
        else:
            raise ValueError(f"지원하지 않는 거래소: {exchange}")

# ===== 기술적 분석 서비스 (요구사항 완벽 충족) =====
class TechnicalAnalysisService:
    """기술적 지표 계산 서비스 - 6가지 규칙 완벽 구현"""

    @staticmethod
    def calculate_sma(prices: List[float], period: int) -> List[Optional[float]]:
        """단순이동평균 계산"""
        if len(prices) < period:
            return [None] * len(prices)

        sma_values: List[Optional[float]] = []
        for i in range(len(prices)):
            if i < period - 1:
                sma_values.append(None)
            else:
                window = prices[i-period+1:i+1]
                sma_values.append(sum(window) / period)

        return sma_values

    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> List[float]:
        """지수이동평균 계산"""
        if len(prices) == 0:
            return []

        multiplier = 2.0 / (period + 1)
        ema_values = [prices[0]]

        for price in prices[1:]:
            ema = price * multiplier + ema_values[-1] * (1 - multiplier)
            ema_values.append(ema)

        return ema_values

    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> List[Optional[float]]:
        """RSI 계산"""
        if len(prices) < period + 1:
            return [None] * len(prices)

        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [max(delta, 0.0) for delta in deltas]
        losses = [max(-delta, 0.0) for delta in deltas]

        avg_gains = TechnicalAnalysisService._calculate_avg(gains, period)
        avg_losses = TechnicalAnalysisService._calculate_avg(losses, period)

        rsi_values = [None]  # 첫 번째 값은 None
        for i in range(len(deltas)):
            if i < period - 1:
                rsi_values.append(None)
            else:
                if avg_losses[i] == 0:
                    rsi = 100.0
                else:
                    rs = avg_gains[i] / avg_losses[i]
                    rsi = 100.0 - (100.0 / (1 + rs))
                rsi_values.append(rsi)

        return rsi_values

    @staticmethod
    def calculate_bollinger_bands(prices: List[float], period: int = 20, std_dev: float = 2.0) -> tuple:
        """볼린저 밴드 계산"""
        sma_values = TechnicalAnalysisService.calculate_sma(prices, period)

        upper_bands = []
        lower_bands = []

        for i, sma in enumerate(sma_values):
            if sma is None:
                upper_bands.append(None)
                lower_bands.append(None)
            else:
                if i < period - 1:
                    upper_bands.append(None)
                    lower_bands.append(None)
                else:
                    window = prices[i-period+1:i+1]
                    variance = sum((p - sma) ** 2 for p in window) / period
                    std = variance ** 0.5

                    upper_bands.append(sma + std_dev * std)
                    lower_bands.append(sma - std_dev * std)

        return upper_bands, lower_bands, sma_values

    @staticmethod
    def calculate_macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
        """MACD 계산"""
        ema_fast = TechnicalAnalysisService.calculate_ema(prices, fast)
        ema_slow = TechnicalAnalysisService.calculate_ema(prices, slow)

        macd_line = [ema_fast[i] - ema_slow[i] for i in range(len(ema_fast))]
        signal_line = TechnicalAnalysisService.calculate_ema(macd_line, signal)

        return macd_line, signal_line

    @staticmethod
    def _calculate_avg(values: List[float], period: int) -> List[float]:
        """이동평균 계산 (RSI용)"""
        if len(values) < period:
            return [0.0] * len(values)

        avg_values = []
        current_sum = sum(values[:period])
        avg_values.append(current_sum / period)

        for i in range(period, len(values)):
            current_sum = current_sum - values[i-period] + values[i]
            avg_values.append(current_sum / period)

        return avg_values

# ===== 신호 생성 서비스 (요구사항 완벽 충족) =====
class SignalGenerationService:
    """거래 신호 생성 서비스 - 6가지 규칙 완벽 구현"""

    def __init__(self, analysis_service: TechnicalAnalysisService, mongodb_service: MongoDBService):
        self.analysis_service = analysis_service
        self.mongodb_service = mongodb_service

    async def generate_signal(self, klines: List[KlineData], symbol: str, interval: str, exchange: ExchangeType) -> SignalResponse:
        """거래 신호 생성"""
        if len(klines) < 50:
            raise HTTPException(
                status_code=400,
                detail="신호 생성을 위해 최소 50개의 캔들 데이터가 필요합니다"
            )

        # 가격 데이터 추출
        closes = [float(kline.close) for kline in klines]
        volumes = [float(kline.volume) for kline in klines]

        # 기술적 지표 계산
        indicators = self._calculate_indicators(closes, volumes)

        # 신호 분석 (6가지 규칙)
        analysis = self._analyze_signals(closes, volumes, indicators)

        # 거래 신호 생성
        signal = self._create_trading_signal(analysis, symbol, interval, exchange)

        # 응답 생성
        signal_response = SignalResponse(
            exchange=exchange,
            symbol=symbol,
            interval=interval,
            timestamp=datetime.now(),
            signal=signal,
            analysis=analysis,
            indicators=indicators
        )

        # MongoDB에 신호 저장
        await self.mongodb_service.save_signal(signal_response)

        return signal_response

    def _calculate_indicators(self, closes: List[float], volumes: List[float]) -> TechnicalIndicators:
        """기술적 지표 계산 - 요구사항 완벽 충족"""
        # 1. 모멘텀 기반 (누적 수익률, Sharpe ratio)
        momentum_window = 20
        if len(closes) >= momentum_window:
            cumret = (closes[-1] / closes[-momentum_window] - 1.0)
            returns = [closes[i] / closes[i-1] - 1.0 for i in range(1, len(closes))]
            momentum_vol = self._calculate_std(returns[-momentum_window:]) if len(returns) >= momentum_window else 0.0
            sharpe_like = cumret / (momentum_vol + 1e-12)
        else:
            cumret = None
            sharpe_like = None

        # 2. 거래량 Z-score
        vol_window = 20
        if len(volumes) >= vol_window:
            vol_mean = self._calculate_mean(volumes[-vol_window:])
            vol_std = self._calculate_std(volumes[-vol_window:])
            vol_z = (volumes[-1] - vol_mean) / (vol_std + 1e-12)
        else:
            vol_z = None

        # 3. 변동성 대비 수익률
        if len(closes) >= vol_window:
            returns = [closes[i] / closes[i-1] - 1.0 for i in range(1, len(closes))]
            mean_ret = self._calculate_mean(returns[-vol_window:])
            ret_std = self._calculate_std(returns[-vol_window:])
            return_over_vol = mean_ret / (ret_std + 1e-12)
        else:
            return_over_vol = None

        # 4. RSI(14)
        rsi_14 = TechnicalAnalysisService.calculate_rsi(closes, 14)

        # 5. 볼린저 밴드 (20, 2σ)
        bb_upper, bb_lower, bb_middle = TechnicalAnalysisService.calculate_bollinger_bands(closes, 20, 2.0)

        # 6. MACD(12,26,9)
        macd_line, macd_signal = TechnicalAnalysisService.calculate_macd(closes, 12, 26, 9)

        # 기본 지표들
        sma_20 = TechnicalAnalysisService.calculate_sma(closes, 20)
        ema_12 = TechnicalAnalysisService.calculate_ema(closes, 12)
        ema_26 = TechnicalAnalysisService.calculate_ema(closes, 26)
        volume_sma = TechnicalAnalysisService.calculate_sma(volumes, 20)

        # MACD 크로스 확인
        macd_cross = "none"
        if len(macd_line) >= 2 and len(macd_signal) >= 2:
            prev_diff = macd_line[-2] - macd_signal[-2]
            curr_diff = macd_line[-1] - macd_signal[-1]
            if prev_diff <= 0 and curr_diff > 0:
                macd_cross = "bullish"
            elif prev_diff >= 0 and curr_diff < 0:
                macd_cross = "bearish"

        return TechnicalIndicators(
            # 1. 모멘텀 기반
            momentum_cumret=cumret,
            momentum_sharpe_like=sharpe_like,

            # 2. 거래량 증가
            volume_z=vol_z,

            # 3. 변동성 대비 수익률
            return_over_vol=return_over_vol,

            # 4. RSI
            rsi_14=rsi_14[-1] if rsi_14[-1] is not None else None,

            # 5. 볼린저 밴드
            bb_pct_b=self._calculate_bb_pct_b(closes, bb_upper, bb_lower),
            bb_bandwidth=self._calculate_bb_bandwidth(bb_upper, bb_lower, bb_middle),
            bb_upper=bb_upper[-1] if bb_upper[-1] is not None else None,
            bb_lower=bb_lower[-1] if bb_lower[-1] is not None else None,
            bb_middle=bb_middle[-1] if bb_middle[-1] is not None else None,

            # 6. MACD
            macd=macd_line[-1] if len(macd_line) > 0 else None,
            macd_signal=macd_signal[-1] if len(macd_signal) > 0 else None,
            macd_hist=(macd_line[-1] - macd_signal[-1]) if len(macd_line) > 0 and len(macd_signal) > 0 else None,
            macd_cross=macd_cross,

            # 기본 지표들
            sma_20=sma_20[-1] if sma_20[-1] is not None else None,
            ema_12=ema_12[-1] if len(ema_12) > 0 else None,
            ema_26=ema_26[-1] if len(ema_26) > 0 else None,
            volume_sma=volume_sma[-1] if volume_sma[-1] is not None else None
        )

    def _calculate_bb_pct_b(self, closes: List[float], upper: List[Optional[float]], lower: List[Optional[float]]) -> Optional[float]:
        """볼린저 밴드 %B 계산"""
        if len(upper) == 0 or len(lower) == 0:
            return None

        current_price = closes[-1]
        current_upper = upper[-1]
        current_lower = lower[-1]

        if current_upper is None or current_lower is None or current_upper == current_lower:
            return None

        return (current_price - current_lower) / (current_upper - current_lower)

    def _calculate_mean(self, values: List[float]) -> float:
        """평균 계산"""
        return sum(values) / len(values) if values else 0.0

    def _calculate_std(self, values: List[float]) -> float:
        """표준편차 계산"""
        if not values:
            return 0.0
        mean = self._calculate_mean(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5

    def _calculate_bb_bandwidth(self, upper: List[Optional[float]], lower: List[Optional[float]], middle: List[Optional[float]]) -> Optional[float]:
        """볼린저 밴드 bandwidth 계산"""
        if len(upper) == 0 or len(lower) == 0 or len(middle) == 0:
            return None

        current_upper = upper[-1]
        current_lower = lower[-1]
        current_middle = middle[-1]

        if current_upper is None or current_lower is None or current_middle is None or current_middle == 0:
            return None

        return (current_upper - current_lower) / current_middle

    def _analyze_signals(self, closes: List[float], volumes: List[float], indicators: TechnicalIndicators) -> SignalAnalysis:
        """신호 분석 - 6가지 규칙 완벽 구현"""
        # 1. 모멘텀 기반: 누적 수익률 +10% 이상이고 Sharpe ratio > 0
        rule1_momentum = "neutral"
        momentum_score = 0.0
        if indicators.momentum_cumret is not None and indicators.momentum_sharpe_like is not None:
            if indicators.momentum_cumret >= 0.10 and indicators.momentum_sharpe_like > 0:
                rule1_momentum = "buy"
                momentum_score = 1.0
            elif indicators.momentum_cumret <= -0.10:
                momentum_score = -0.5

        # 2. 거래량 증가: Z-score >= 1.0
        rule2_volume = "neutral"
        volume_score = 0.0
        if indicators.volume_z is not None:
            if indicators.volume_z >= 1.0:
                rule2_volume = "buy"
                volume_score = 1.0
            elif indicators.volume_z <= -1.0:
                volume_score = -0.5

        # 3. 변동성 대비 수익률: >= 1.0 매수, <= -1.0 매도
        rule3_ret_over_vol = "neutral"
        ret_vol_score = 0.0
        if indicators.return_over_vol is not None:
            if indicators.return_over_vol >= 1.0:
                rule3_ret_over_vol = "buy"
                ret_vol_score = 1.0
            elif indicators.return_over_vol <= -1.0:
                rule3_ret_over_vol = "sell"
                ret_vol_score = -1.0

        # 4. RSI: < 30 매수, > 70 매도
        rule4_rsi = "neutral"
        rsi_score = 0.0
        if indicators.rsi_14 is not None:
            if indicators.rsi_14 < 30:
                rule4_rsi = "buy"
                rsi_score = 1.0
            elif indicators.rsi_14 > 70:
                rule4_rsi = "sell"
                rsi_score = -1.0

        # 5. 볼린저 밴드: %B < 0.1 매수, > 0.9 매도, bandwidth로 신뢰도
        rule5_bollinger = "neutral"
        bollinger_score = 0.0
        if indicators.bb_pct_b is not None and indicators.bb_bandwidth is not None:
            bandwidth_strong = indicators.bb_bandwidth > 0.06  # 신뢰도 높음

            if indicators.bb_pct_b < 0.1:
                rule5_bollinger = "buy_strong" if bandwidth_strong else "buy"
                bollinger_score = 1.0 if bandwidth_strong else 0.7
            elif indicators.bb_pct_b > 0.9:
                rule5_bollinger = "sell_strong" if bandwidth_strong else "sell"
                bollinger_score = -1.0 if bandwidth_strong else -0.7

        # 6. MACD: 시그널 선 상향 돌파 매수, 하향 돌파 매도
        rule6_macd = "neutral"
        macd_score = 0.0
        if indicators.macd_cross == "bullish":
            rule6_macd = "buy"
            macd_score = 1.0
        elif indicators.macd_cross == "bearish":
            rule6_macd = "sell"
            macd_score = -1.0

        # 종합 점수 계산
        scores = [momentum_score, volume_score, ret_vol_score, rsi_score, bollinger_score, macd_score]
        valid_scores = [s for s in scores if s != 0.0]

        if valid_scores:
            overall_score = sum(valid_scores) / len(valid_scores)
        else:
            overall_score = 0.0

        # 추천 결정
        if overall_score >= 0.6:
            recommendation = "BUY"
        elif overall_score <= -0.6:
            recommendation = "SELL"
        else:
            recommendation = "HOLD"

        # 신뢰도 계산
        confidence = abs(overall_score)

        return SignalAnalysis(
            rule1_momentum=rule1_momentum,
            momentum_score=momentum_score,
            rule2_volume=rule2_volume,
            volume_score=volume_score,
            rule3_ret_over_vol=rule3_ret_over_vol,
            ret_vol_score=ret_vol_score,
            rule4_rsi=rule4_rsi,
            rsi_score=rsi_score,
            rule5_bollinger=rule5_bollinger,
            bollinger_score=bollinger_score,
            rule6_macd=rule6_macd,
            macd_score=macd_score,
            overall_score=overall_score,
            recommendation=recommendation,
            confidence=confidence
        )

    def _create_trading_signal(self, analysis: SignalAnalysis, symbol: str, interval: str, exchange: ExchangeType) -> TradingSignal:
        """거래 신호 생성"""
        return TradingSignal(
            action=analysis.recommendation,
            confidence=analysis.confidence,
            score=analysis.overall_score,
            timestamp=datetime.now(),
            symbol=symbol,
            interval=interval,
            exchange=exchange
        )

# ===== 메인 자동매매 서비스 =====
class AutotradingService:
    """자동매매 메인 서비스 - 멀티 거래소 지원 + MongoDB 저장"""

    def __init__(self, mongodb_service: MongoDBService):
        self.mongodb_service = mongodb_service
        self.analysis_service = TechnicalAnalysisService()
        self.signal_service = SignalGenerationService(self.analysis_service, mongodb_service)

    async def get_trading_signal(self, request: MarketDataRequest) -> SignalResponse:
        """거래 신호 조회"""
        # 1. 거래소별 데이터 서비스 생성
        market_data_service = MarketDataServiceFactory.create_service(request.exchange, self.mongodb_service)

        # 2. 시장 데이터 수집
        market_data = await market_data_service.get_klines(request)

        # 3. 거래 신호 생성
        signal = await self.signal_service.generate_signal(
            market_data.klines,
            market_data.symbol,
            market_data.interval,
            market_data.exchange
        )

        return signal

    async def get_multi_exchange_signals(self, requests: List[MarketDataRequest]) -> List[SignalResponse]:
        """여러 거래소에서 동시에 신호 조회"""
        tasks = []
        for request in requests:
            task = self.get_trading_signal(request)
            tasks.append(task)

        signals = await asyncio.gather(*tasks, return_exceptions=True)

        # 에러 처리
        valid_signals = []
        for i, signal in enumerate(signals):
            if isinstance(signal, Exception):
                print(f"거래소 {requests[i].exchange} 신호 생성 실패: {signal}")
            else:
                valid_signals.append(signal)

        return valid_signals

    async def get_stored_data(
        self,
        exchange: ExchangeType,
        symbol: str,
        interval: str,
        data_type: str = "klines",
        limit: int = 200
    ):
        """저장된 데이터 조회"""
        if data_type == "klines":
            return await self.mongodb_service.get_stored_klines(exchange, symbol, interval, limit)
        elif data_type == "signals":
            return await self.mongodb_service.get_stored_signals(exchange, symbol, interval, limit)
        else:
            raise ValueError(f"지원하지 않는 데이터 타입: {data_type}")

    async def get_latest_signal(
        self,
        exchange: ExchangeType,
        symbol: str,
        interval: str
    ):
        """최신 신호 조회"""
        return await self.mongodb_service.get_latest_signal(exchange, symbol, interval)





