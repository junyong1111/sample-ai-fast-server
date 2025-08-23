from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, Any, Literal, List
from datetime import datetime, timezone

import pyupbit
from fastapi.concurrency import run_in_threadpool


INTERVAL_MAP = {
    "days": "day",
    "minutes:1": "minute1",
    "minutes:3": "minute3",
    "minutes:5": "minute5",
    "minutes:10": "minute10",
    "minutes:15": "minute15",
    "minutes:30": "minute30",
    "minutes:60": "minute60",
    "minutes:240": "minute240",
}


class PyUpbitUtils:
    def __init__(self):
        pass

    # ---------- Data fetch ----------
    async def get_chart_health(self) -> dict:
        # 간단 헬스체크: 현재 시각과 PyUpbit 버전/필수 함수 존재 여부
        import pyupbit
        ok = hasattr(pyupbit, "get_ohlcv")
        return {
            "status": "ok" if ok else "degraded",
            "pyupbit_version": getattr(pyupbit, "__version__", "unknown"),
            "now_utc": datetime.now(timezone.utc).isoformat(),
            "features": {
                "get_ohlcv": ok
            }
        }

    async def get_ohlcv_df(
        self,
        market: str,
        tf: Literal["days","minutes:1","minutes:3","minutes:5","minutes:10","minutes:15","minutes:30","minutes:60","minutes:240"] = "minutes:60",
        count: int = 200,
    ) -> pd.DataFrame:
        """
        PyUpbit 동기 호출을 threadpool로 감싸 비동기 FastAPI에서 안전하게 사용.
        반환: index=Timestamp, columns=open/high/low/close/volume/...
        """
        interval = INTERVAL_MAP[tf]
        df = await run_in_threadpool(pyupbit.get_ohlcv, market, interval=interval, count=count)
        if df is None or df.empty:
            raise ValueError(f"Empty OHLCV for {market} ({tf}, count={count})")
        # 필요한 컬럼만 보장
        required = {"open","high","low","close","volume"}
        missing = required.difference(df.columns)
        if missing:
            raise ValueError(f"Missing columns in OHLCV: {missing}")
        return df

    # ---------- Indicators ----------
    @staticmethod
    def rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        up = delta.clip(lower=0)
        down = (-delta).clip(lower=0)
        roll_up = up.ewm(alpha=1/period, adjust=False).mean()
        roll_down = down.ewm(alpha=1/period, adjust=False).mean()
        rs = roll_up / (roll_down + 1e-12)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def bollinger(close: pd.Series, period: int = 20, k: float = 2.0):
        ma = close.rolling(period).mean()
        sd = close.rolling(period).std(ddof=0)
        upper = ma + k * sd
        lower = ma - k * sd
        pct_b = (close - lower) / (upper - lower + 1e-12)
        bandwidth = (upper - lower) / (ma + 1e-12)
        return ma, upper, lower, pct_b, bandwidth

    @staticmethod
    def ema(series: pd.Series, span: int) -> pd.Series:
        return series.ewm(span=span, adjust=False).mean()

    @staticmethod
    def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
        line = PyUpbitUtils.ema(close, fast) - PyUpbitUtils.ema(close, slow)
        sig = PyUpbitUtils.ema(line, signal)
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
        rsi_series = PyUpbitUtils.rsi(close, rsi_period)

        # 5) Bollinger
        ma, upper, lower, pct_b, bandwidth = PyUpbitUtils.bollinger(close, bb_period, 2.0)

        # 6) MACD
        macd_line, signal_line, hist = PyUpbitUtils.macd(close, macd_fast, macd_slow, macd_signal)
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