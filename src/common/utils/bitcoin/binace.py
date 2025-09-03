from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, Any, Literal, List, Union
from datetime import datetime, timezone
from src.common.utils.logger import set_logger
import ccxt
from fastapi.concurrency import run_in_threadpool
logger =  set_logger("api.coupon")



INTERVAL_MAP = {
    "days": "1d",
    "minutes:1": "1m",
    "minutes:3": "3m",
    "minutes:5": "5m",
    "minutes:10": "10m",
    "minutes:15": "15m",
    "minutes:30": "30m",
    "minutes:60": "1h",
    "minutes:240": "4h",
}


class BinanceUtils:
    def __init__(self, api_key: str | None = None, secret: str | None = None, testnet: bool = True):
        """
        바이낸스 API 유틸리티 클래스

        Args:
            api_key: 바이낸스 API 키 (선택사항)
            secret: 바이낸스 시크릿 키 (선택사항)
            testnet: 테스트넷 사용 여부 (기본값: True - 안전을 위해)
        """
        import os

        # 환경변수에서 API 키 가져오기 (testnet 우선)
        if testnet:
            self.api_key = api_key or os.getenv('BINANCE_TESTNET_API_KEY', 'NSdQ8nBkN77FxUlrtApiOdqV3xnGkY8UNBFAMnQPyIGtPtNS4aZEwGvPj7v2ArXa')
            self.secret = secret or os.getenv('BINANCE_TESTNET_SECRET_KEY', 'G5CmRrTzQ49wfjPKqVBbr48hyZKZA4nbrTWvwK4TUrXpi7zoeE3CMipTVgWWZndm')
        else:
            self.api_key = api_key or os.getenv('BINANCE_API_KEY', '')
            self.secret = secret or os.getenv('BINANCE_SECRET_KEY', '')

        self.testnet = testnet

        # CCXT를 사용하여 바이낸스 연결
        config = {
            'enableRateLimit': True,
            'sandbox': testnet,  # testnet 모드 활성화
            'apiKey': None,
            'secret': None,
        }

        if self.api_key:
            config['apiKey'] = self.api_key
        if self.secret:
            config['secret'] = self.secret

        # 바이낸스 testnet 설정
        if testnet:
            config['urls'] = {
                'api': {
                    'public': 'https://testnet.binance.vision/api',
                    'private': 'https://testnet.binance.vision/api',
                }
            }

        self.exchange = ccxt.binance(config)  # type: ignore

    # ---------- Data fetch ----------
    async def get_chart_health(self) -> dict:
        """바이낸스 API 헬스체크"""
        try:
            # 간단한 API 호출로 연결 상태 확인
            ticker = await run_in_threadpool(self.exchange.fetch_ticker, 'BTC/USDT')
            return {
                "status": "ok",
                "exchange": "binance",
                "testnet": self.testnet,
                "now_utc": datetime.now(timezone.utc).isoformat(),
                "features": {
                    "ohlcv": True,
                    "ticker": True
                },
                "last_price": ticker.get('last') if ticker else None
            }
        except Exception as e:
            logger.error(
                f"""
                    [바이낸스 헬스체크 에러]
                    class : {e.__class__.__name__}
                    messsage : {str(e)}
                """
            )
            return {
                "status": "error",
                "exchange": "binance",
                "testnet": self.testnet,
                "now_utc": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
                "features": {
                    "ohlcv": False,
                    "ticker": False
                }
            }

    async def get_ohlcv_df(
        self,
        market: str,
        tf: Literal["days","minutes:1","minutes:3","minutes:5","minutes:10","minutes:15","minutes:30","minutes:60","minutes:240"] = "minutes:60",
        count: int = 200,
    ) -> pd.DataFrame:
        """
        바이낸스에서 OHLCV 데이터를 가져와서 DataFrame으로 반환

        Args:
            market: 거래쌍 (예: 'BTC/USDT')
            tf: 시간프레임
            count: 캔들 개수

        Returns:
            DataFrame with columns: open, high, low, close, volume
        """
        try:
            interval = INTERVAL_MAP[tf]

            # CCXT를 사용하여 OHLCV 데이터 가져오기
            ohlcv = await run_in_threadpool(
                self.exchange.fetch_ohlcv,
                market,
                interval,
                limit=count
            )

            if not ohlcv:
                raise ValueError(f"Empty OHLCV for {market} ({tf}, count={count})")

            # DataFrame으로 변환
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            # 필요한 컬럼만 보장
            required = {"open", "high", "low", "close", "volume"}
            missing = required.difference(df.columns)
            if missing:
                raise ValueError(f"Missing columns in OHLCV: {missing}")

            return df

        except Exception as e:
            raise ValueError(f"Failed to fetch OHLCV for {market}: {str(e)}")

    # ---------- Indicators ----------
    @staticmethod
    def rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """RSI 계산"""
        delta = series.diff()
        up = delta.clip(lower=0)
        down = (-delta).clip(lower=0)
        roll_up = up.ewm(alpha=1/period, adjust=False).mean()
        roll_down = down.ewm(alpha=1/period, adjust=False).mean()
        rs = roll_up / (roll_down + 1e-12)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def bollinger(close: pd.Series, period: int = 20, k: float = 2.0):
        """볼린저 밴드 계산"""
        ma = close.rolling(period).mean()
        sd = close.rolling(period).std(ddof=0)
        upper = ma + k * sd
        lower = ma - k * sd
        pct_b = (close - lower) / (upper - lower + 1e-12)
        bandwidth = (upper - lower) / (ma + 1e-12)
        return ma, upper, lower, pct_b, bandwidth

    @staticmethod
    def ema(series: pd.Series, span: int) -> pd.Series:
        """지수이동평균 계산"""
        return series.ewm(span=span, adjust=False).mean()

    @staticmethod
    def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
        """MACD 계산"""
        line = BinanceUtils.ema(close, fast) - BinanceUtils.ema(close, slow)
        sig = BinanceUtils.ema(line, signal)
        hist = line - sig
        return line, sig, hist

    @staticmethod
    def compute_indicators(
        df: pd.DataFrame,
        momentum_window: int = 20,
        vol_window: int = 20,
        rsi_period: int = 14,
        bb_period: int = 20,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9
    ) -> Dict[str, Any]:
        """모든 기술적 지표 계산"""
        close = df["close"]
        volume = df["volume"]
        ret = close.pct_change()

        # 1) 모멘텀(누적수익률/변동성)
        cumret = (close / close.shift(momentum_window) - 1.0)
        mom_vol = ret.rolling(momentum_window).std(ddof=0)
        sharpe_like = cumret / (mom_vol + 1e-12)

        # 2) 거래량 z-score
        vol_mean = volume.rolling(vol_window).mean()
        vol_std = volume.rolling(vol_window).std(ddof=0)
        vol_z = (volume - vol_mean) / (vol_std + 1e-12)

        # 3) 수익률/변동성
        mean_ret = ret.rolling(vol_window).mean()
        rv = mean_ret / (ret.rolling(vol_window).std(ddof=0) + 1e-12)

        # 4) RSI
        rsi_series = BinanceUtils.rsi(close, rsi_period)

        # 5) Bollinger
        ma, upper, lower, pct_b, bandwidth = BinanceUtils.bollinger(close, bb_period, 2.0)

        # 6) MACD
        macd_line, signal_line, hist = BinanceUtils.macd(close, macd_fast, macd_slow, macd_signal)
        macd_cross = "none"
        if len(macd_line) >= 2:
            prev_diff = macd_line.iloc[-2] - signal_line.iloc[-2]
            curr_diff = macd_line.iloc[-1] - signal_line.iloc[-1]
            macd_cross = "bullish" if prev_diff <= 0 and curr_diff > 0 else \
                         "bearish" if prev_diff >= 0 and curr_diff < 0 else "none"

        return {
            "time": df.index[-1].to_pydatetime() if hasattr(df.index[-1], "to_pydatetime") else df.index[-1],
            "close": float(close.iloc[-1]),
            "momentum_cumret": float(cumret.iloc[-1]) if cumret.notna().iloc[-1] else None,
            "momentum_sharpe_like": float(sharpe_like.iloc[-1]) if sharpe_like.notna().iloc[-1] else None,
            "volume_z": float(vol_z.iloc[-1]) if vol_z.notna().iloc[-1] else None,
            "return_over_vol": float(rv.iloc[-1]) if rv.notna().iloc[-1] else None,
            "rsi": float(rsi_series.iloc[-1]) if rsi_series.notna().iloc[-1] else None,
            "bb_pct_b": float(pct_b.iloc[-1]) if pct_b.notna().iloc[-1] else None,
            "bb_bandwidth": float(bandwidth.iloc[-1]) if bandwidth.notna().iloc[-1] else None,
            "macd": float(macd_line.iloc[-1]) if macd_line.notna().iloc[-1] else None,
            "macd_signal": float(signal_line.iloc[-1]) if signal_line.notna().iloc[-1] else None,
            "macd_hist": float(hist.iloc[-1]) if hist.notna().iloc[-1] else None,
            "macd_cross": macd_cross,
        }

    @staticmethod
    def rule_signals(ind: Dict[str, Any]) -> Dict[str, Any]:
        """거래 신호 규칙 평가"""
        sigs: Dict[str, str] = {}

        # 1) 모멘텀
        mom_buy = (ind.get("momentum_cumret", -1) >= 0.10) and (ind.get("momentum_sharpe_like", -1) > 0)
        sigs["rule1_momentum"] = "buy" if mom_buy else "neutral"

        # 2) 거래량
        vz = ind.get("volume_z")
        sigs["rule2_volume"] = "buy" if (vz is not None and vz >= 1.0) else "neutral"

        # 3) 수익률/변동성
        rv = ind.get("return_over_vol")
        sigs["rule3_ret_over_vol"] = "buy" if (rv is not None and rv >= 1.0) else ("sell" if (rv is not None and rv <= -1.0) else "neutral")

        # 4) RSI
        r = ind.get("rsi")
        sigs["rule4_rsi"] = "buy" if (r is not None and r < 30) else ("sell" if (r is not None and r > 70) else "neutral")

        # 5) Bollinger %b + bandwidth
        b = ind.get("bb_pct_b"); bw = ind.get("bb_bandwidth")
        if b is None or bw is None:
            sigs["rule5_bollinger"] = "neutral"
        else:
            strong = (bw > 0.06)
            if b < 0.1:
                sigs["rule5_bollinger"] = "buy_strong" if strong else "buy"
            elif b > 0.9:
                sigs["rule5_bollinger"] = "sell_strong" if strong else "sell"
            else:
                sigs["rule5_bollinger"] = "neutral"

        # 6) MACD cross
        cross = ind.get("macd_cross", "none")
        sigs["rule6_macd"] = "buy" if cross == "bullish" else ("sell" if cross == "bearish" else "neutral")

        buys = sum(1 for v in sigs.values() if v.startswith("buy"))
        sells = sum(1 for v in sigs.values() if v.startswith("sell"))
        sigs["overall"] = "BUY" if buys - sells >= 2 else ("SELL" if sells - buys >= 2 else "HOLD")
        return sigs

    # ---------- 추가 바이낸스 전용 기능 ----------
    async def get_ticker(self, market: str) -> Dict[str, Any]:
        """현재 가격 정보 조회"""
        try:
            # 시장 심볼 검증
            if not market or market == "string":
                raise ValueError(f"Invalid market symbol: {market}")

            # 바이낸스에서 지원하는 시장인지 확인
            markets = await run_in_threadpool(self.exchange.load_markets)
            if market not in markets:
                # 일반적인 시장 심볼로 변환 시도
                if "/" not in market:
                    # KRW-BTC -> BTC/USDT 형태로 변환 시도
                    if market.startswith("KRW-"):
                        market = market.replace("KRW-", "") + "/USDT"
                    else:
                        market = market + "/USDT"

                if market not in markets:
                    raise ValueError(f"Market {market} not supported by Binance. Available markets: {list(markets.keys())[:10]}...")

            ticker = await run_in_threadpool(self.exchange.fetch_ticker, market)
            if not ticker:
                raise ValueError(f"Empty ticker data for {market}")

            return {
                "symbol": ticker.get('symbol', market),
                "last": ticker.get('last', 0),
                "bid": ticker.get('bid', 0),
                "ask": ticker.get('ask', 0),
                "high": ticker.get('high', 0),
                "low": ticker.get('low', 0),
                "volume": ticker.get('baseVolume', 0),
                "change": ticker.get('change', 0),
                "change_percent": ticker.get('percentage', 0),
                "timestamp": ticker.get('timestamp', 0)
            }
        except Exception as e:
            raise ValueError(f"Failed to fetch ticker for {market}: {str(e)}")

    async def get_orderbook(self, market: str, limit: int = 20) -> Dict[str, Any]:
        """호가창 정보 조회"""
        try:
            orderbook = await run_in_threadpool(self.exchange.fetch_order_book, market, limit)
            return {
                "symbol": market,
                "bids": orderbook['bids'][:limit],
                "asks": orderbook['asks'][:limit],
                "timestamp": orderbook['timestamp']
            }
        except Exception as e:
            raise ValueError(f"Failed to fetch orderbook for {market}: {str(e)}")

    async def get_recent_trades(self, market: str, limit: int = 100) -> List[Dict[str, Any]]:
        """최근 거래 내역 조회"""
        try:
            trades = await run_in_threadpool(self.exchange.fetch_trades, market, limit=limit)
            return [
                {
                    "id": trade['id'],
                    "timestamp": trade['timestamp'],
                    "price": trade['price'],
                    "amount": trade['amount'],
                    "side": trade['side'],
                    "cost": trade['cost']
                }
                for trade in trades
            ]
        except Exception as e:
            raise ValueError(f"Failed to fetch trades for {market}: {str(e)}")

    # ---------- 거래 기능 (매매) ----------
    async def get_account_info(self) -> Dict[str, Any]:
        """계정 정보 조회"""
        try:
            if not self.api_key or not self.secret:
                raise ValueError("API key and secret are required for account operations")

            account = await run_in_threadpool(self.exchange.fetch_balance)
            return {
                "total_balance": account.get('total', {}),
                "free_balance": account.get('free', {}),
                "used_balance": account.get('used', {}),
                "info": account.get('info', {})
            }
        except Exception as e:
            raise ValueError(f"Failed to fetch account info: {str(e)}")

    async def place_market_order(self, market: str, side: Literal['buy', 'sell'], quantity: float) -> Dict[str, Any]:
        """시장가 주문 실행"""
        try:
            if not self.api_key or not self.secret:
                raise ValueError("API key and secret are required for trading")

            order = await run_in_threadpool(
                self.exchange.create_market_order,
                market, side, quantity
            )

            return {
                "order_id": order.get('id'),
                "symbol": order.get('symbol'),
                "side": order.get('side'),
                "type": order.get('type'),
                "amount": order.get('amount'),
                "cost": order.get('cost'),
                "status": order.get('status'),
                "timestamp": order.get('timestamp')
            }
        except Exception as e:
            raise ValueError(f"Failed to place market order: {str(e)}")

    async def place_limit_order(self, market: str, side: Literal['buy', 'sell'], quantity: float, price: float) -> Dict[str, Any]:
        """지정가 주문 실행"""
        try:
            if not self.api_key or not self.secret:
                raise ValueError("API key and secret are required for trading")

            order = await run_in_threadpool(
                self.exchange.create_limit_order,
                market, side, quantity, price
            )

            return {
                "order_id": order.get('id'),
                "symbol": order.get('symbol'),
                "side": order.get('side'),
                "type": order.get('type'),
                "amount": order.get('amount'),
                "price": order.get('price'),
                "status": order.get('status'),
                "timestamp": order.get('timestamp')
            }
        except Exception as e:
            raise ValueError(f"Failed to place limit order: {str(e)}")

    async def get_order_status(self, order_id: str, market: str) -> Dict[str, Any]:
        """주문 상태 조회"""
        try:
            if not self.api_key or not self.secret:
                raise ValueError("API key and secret are required for order operations")

            order = await run_in_threadpool(self.exchange.fetch_order, order_id, market)

            return {
                "order_id": order.get('id'),
                "symbol": order.get('symbol'),
                "side": order.get('side'),
                "type": order.get('type'),
                "amount": order.get('amount'),
                "price": order.get('price'),
                "status": order.get('status'),
                "filled": order.get('filled'),
                "remaining": order.get('remaining'),
                "cost": order.get('cost'),
                "timestamp": order.get('timestamp')
            }
        except Exception as e:
            raise ValueError(f"Failed to fetch order status: {str(e)}")

    async def cancel_order(self, order_id: str, market: str) -> Dict[str, Any]:
        """주문 취소"""
        try:
            if not self.api_key or not self.secret:
                raise ValueError("API key and secret are required for order operations")

            result = await run_in_threadpool(self.exchange.cancel_order, order_id, market)

            return {
                "order_id": result.get('id'),
                "symbol": result.get('symbol'),
                "status": "canceled",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            raise ValueError(f"Failed to cancel order: {str(e)}")

    async def get_open_orders(self, market: Union[str, None] = None) -> List[Dict[str, Any]]:
        """미체결 주문 조회"""
        try:
            if not self.api_key or not self.secret:
                raise ValueError("API key and secret are required for order operations")

            orders = await run_in_threadpool(self.exchange.fetch_open_orders, market)

            return [
                {
                    "order_id": order.get('id'),
                    "symbol": order.get('symbol'),
                    "side": order.get('side'),
                    "type": order.get('type'),
                    "amount": order.get('amount'),
                    "price": order.get('price'),
                    "status": order.get('status'),
                    "timestamp": order.get('timestamp')
                }
                for order in orders
            ]
        except Exception as e:
            raise ValueError(f"Failed to fetch open orders: {str(e)}")