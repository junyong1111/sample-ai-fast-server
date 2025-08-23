from __future__ import annotations

from typing import Dict, Any, List, Literal, Optional, Tuple
from datetime import datetime
import pandas as pd

from src.common.utils.upbit import PyUpbitUtils


Timeframe = Literal[
    "days",
    "minutes:1","minutes:3","minutes:5","minutes:10","minutes:15","minutes:30","minutes:60","minutes:240"
]

class ChartService:
    def __init__(self):
        self.pyupbit_utils = PyUpbitUtils()

    # ---- health ----
    async def get_chart_health(self) -> Dict[str, Any]:
        return await self.pyupbit_utils.get_chart_health()

    # ---- 데이터 조회 ----
    async def get_candles(self, market: str, tf: Timeframe = "minutes:60", count: int = 200) -> pd.DataFrame:
        """
        원시 캔들 DataFrame 반환 (index: timestamp, cols: open/high/low/close/volume)
        """
        return await self.pyupbit_utils.get_ohlcv_df(market, tf, count)

    # ---- 지표 계산(전체) ----
    def compute_indicators(
        self,
        df: pd.DataFrame,
        momentum_window: int = 20, vol_window: int = 20,
        rsi_period: int = 14, bb_period: int = 20,
        macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9
    ) -> Dict[str, Any]:
        """
        하나의 DataFrame으로 모든 지표를 계산해서 dict로 반환
        """
        return self.pyupbit_utils.compute_indicators(
            df,
            momentum_window=momentum_window, vol_window=vol_window,
            rsi_period=rsi_period, bb_period=bb_period,
            macd_fast=macd_fast, macd_slow=macd_slow, macd_signal=macd_signal
        )

    # ---- 규칙 평가(전체) ----
    def evaluate_rules(self, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """
        요구한 6가지 규칙을 한 번에 평가 (rule1~rule6 + overall)
        """
        return self.pyupbit_utils.rule_signals(indicators)

    # ---- 전체 시그널(데이터 획득 + 지표 + 규칙) ----
    async def get_overall_signals(
        self,
        market: str,
        tf: Timeframe = "minutes:60",
        count: int = 200,
        momentum_window: int = 20, vol_window: int = 20,
        rsi_period: int = 14, bb_period: int = 20,
        macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9
    ) -> Dict[str, Any]:
        """
        최종 패키지: 캔들 → 지표 → 규칙 평가까지 한번에
        """
        df = await self.get_candles(market, tf, count)
        ind = self.compute_indicators(
            df,
            momentum_window=momentum_window, vol_window=vol_window,
            rsi_period=rsi_period, bb_period=bb_period,
            macd_fast=macd_fast, macd_slow=macd_slow, macd_signal=macd_signal
        )
        rules = self.evaluate_rules(ind)
        return {
            "market": market,
            "timeframe": tf,
            "count": count,
            "asof": ind.get("time"),
            "indicators": ind,
            "signals": rules
        }

    # ---- 개별 지표만 조회 ----
    async def get_single_indicator(
        self,
        market: str,
        tf: Timeframe = "minutes:60",
        count: int = 200,
        name: Literal[
            "close",
            "momentum_cumret","momentum_sharpe_like",
            "volume_z",
            "return_over_vol",
            "rsi",
            "bb_pct_b","bb_bandwidth",
            "macd","macd_signal","macd_hist","macd_cross"
        ] = "rsi",
        momentum_window: int = 20, vol_window: int = 20,
        rsi_period: int = 14, bb_period: int = 20,
        macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9
    ) -> Dict[str, Any]:
        """
        특정 지표만 골라서 반환
        """
        df = await self.get_candles(market, tf, count)
        ind = self.compute_indicators(
            df,
            momentum_window=momentum_window, vol_window=vol_window,
            rsi_period=rsi_period, bb_period=bb_period,
            macd_fast=macd_fast, macd_slow=macd_slow, macd_signal=macd_signal
        )
        if name not in ind:
            raise ValueError(f"Unknown indicator: {name}")
        return {
            "market": market,
            "timeframe": tf,
            "asof": ind.get("time"),
            "indicator": { "name": name, "value": ind[name] }
        }

    # ---- 개별 규칙만 평가 ----
    async def get_single_rule(
        self,
        market: str,
        tf: Timeframe = "minutes:60",
        count: int = 200,
        rule: Literal["rule1_momentum","rule2_volume","rule3_ret_over_vol","rule4_rsi","rule5_bollinger","rule6_macd"] = "rule4_rsi",
        momentum_window: int = 20, vol_window: int = 20,
        rsi_period: int = 14, bb_period: int = 20,
        macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9
    ) -> Dict[str, Any]:
        """
        특정 규칙의 신호만 반환 (buy/sell/neutral 등)
        """
        df = await self.get_candles(market, tf, count)
        ind = self.compute_indicators(
            df,
            momentum_window=momentum_window, vol_window=vol_window,
            rsi_period=rsi_period, bb_period=bb_period,
            macd_fast=macd_fast, macd_slow=macd_slow, macd_signal=macd_signal
        )
        rules = self.evaluate_rules(ind)
        if rule not in rules:
            raise ValueError(f"Unknown rule: {rule}")
        return {
            "market": market,
            "timeframe": tf,
            "asof": ind.get("time"),
            "rule": { "name": rule, "signal": rules[rule] }
        }

    # ---- 요약 카드(지표 값 + 규칙 해석을 함께) ----
    async def get_indicator_card(
        self,
        market: str,
        tf: Timeframe = "minutes:60",
        count: int = 200
    ) -> Dict[str, Any]:
        """
        대시보드 위젯용 간단 카드: 가격/RSI/%b/MACD 신호를 한 번에
        """
        df = await self.get_candles(market, tf, count)
        ind = self.compute_indicators(df)
        rules = self.evaluate_rules(ind)
        return {
            "market": market,
            "timeframe": tf,
            "asof": ind.get("time"),
            "price": ind.get("close"),
            "rsi": {"value": ind.get("rsi"), "signal": rules.get("rule4_rsi")},
            "boll_pct_b": {"value": ind.get("bb_pct_b"), "signal": rules.get("rule5_bollinger")},
            "macd_cross": {"value": ind.get("macd_cross"), "signal": rules.get("rule6_macd")},
            "overall": rules.get("overall")
        }