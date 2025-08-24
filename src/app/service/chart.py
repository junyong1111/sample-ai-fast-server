from __future__ import annotations

from typing import Dict, Any, List, Literal, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd

from src.common.utils.upbit import PyUpbitUtils
from src.app.repository.chart import ChartRepository


Timeframe = Literal[
    "days",
    "minutes:1","minutes:3","minutes:5","minutes:10","minutes:15","minutes:30","minutes:60","minutes:240"
]

class ChartService:
    def __init__(self, mongo_uri: str = "mongodb://localhost:27017"):
        self.pyupbit_utils = PyUpbitUtils()
        try:
            self.repository = ChartRepository(mongo_uri)
            self.db_enabled = True
        except Exception as e:
            print(f"MongoDB 연결 실패, DB 기능 비활성화: {e}")
            self.repository = None
            self.db_enabled = False

    # ---- health ----
    async def get_chart_health(self) -> Dict[str, Any]:
        health = await self.pyupbit_utils.get_chart_health()
        health["mongodb"] = "connected" if self.db_enabled else "disconnected"
        return health

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

    # ---- MongoDB 저장 기능이 포함된 전체 시그널 ----
    async def save_and_get_overall_signals(
        self,
        market: str,
        tf: Timeframe = "minutes:60",
        count: int = 200,
        save_to_db: bool = True,
        momentum_window: int = 20, vol_window: int = 20,
        rsi_period: int = 14, bb_period: int = 20,
        macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9
    ) -> Dict[str, Any]:
        """
        신호 계산 + DB 저장 + 응답 반환
        """
        # 기존 로직
        df = await self.get_candles(market, tf, count)
        ind = self.compute_indicators(
            df,
            momentum_window=momentum_window, vol_window=vol_window,
            rsi_period=rsi_period, bb_period=bb_period,
            macd_fast=macd_fast, macd_slow=macd_slow, macd_signal=macd_signal
        )
        rules = self.evaluate_rules(ind)

        result = {
            "market": market,
            "timeframe": tf,
            "count": count,
            "asof": ind.get("time"),
            "indicators": ind,
            "signals": rules
        }

        # MongoDB 저장
        if save_to_db and self.db_enabled:
            try:
                # 캔들 데이터 추출
                latest_candle = {
                    "open": float(df.iloc[-1]["open"]),
                    "high": float(df.iloc[-1]["high"]),
                    "low": float(df.iloc[-1]["low"]),
                    "close": float(df.iloc[-1]["close"]),
                    "volume": float(df.iloc[-1]["volume"])
                }

                db_id = await self.repository.save_chart_data(
                    market=market,
                    timeframe=tf,
                    indicators=ind,
                    signals=rules,
                    candle_data=latest_candle
                )

                result["saved_to_db"] = True
                result["db_id"] = db_id

            except Exception as e:
                result["saved_to_db"] = False
                result["db_error"] = str(e)
        else:
            result["saved_to_db"] = False
            result["db_reason"] = "DB 비활성화" if not self.db_enabled else "저장 비활성화"

        return result

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

    # ---- MongoDB 기반 히스토리 조회 ----
    async def get_historical_analysis(
        self,
        market: str,
        timeframe: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        과거 데이터 분석 결과 (MongoDB에서 조회)
        """
        if not self.db_enabled:
            return {
                "error": "MongoDB가 연결되지 않았습니다",
                "market": market,
                "timeframe": timeframe
            }

        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)

            # DB에서 히스토리 조회
            history = await self.repository.get_chart_history(
                market, timeframe, start_time, end_time
            )

            # AI 분석 결과도 함께 조회
            ai_analysis = await self.repository.get_ai_analysis_history(
                market, start_time, end_time
            )

            return {
                "market": market,
                "timeframe": timeframe,
                "period": f"{days} days",
                "data_points": len(history),
                "start_date": start_time,
                "end_date": end_time,
                "history": history,
                "ai_analysis": ai_analysis
            }

        except Exception as e:
            return {
                "error": f"히스토리 조회 실패: {str(e)}",
                "market": market,
                "timeframe": timeframe
            }

    # ---- 마켓 통계 조회 ----
    async def get_market_statistics(
        self,
        market: str,
        timeframe: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        마켓 통계 정보 조회 (MongoDB 집계)
        """
        if not self.db_enabled:
            return {
                "error": "MongoDB가 연결되지 않았습니다",
                "market": market,
                "timeframe": timeframe
            }

        try:
            return await self.repository.get_market_statistics(market, timeframe, days)
        except Exception as e:
            return {
                "error": f"통계 조회 실패: {str(e)}",
                "market": market,
                "timeframe": timeframe
            }

    # ---- 일별 집계 조회 ----
    async def get_daily_aggregation(
        self,
        market: str,
        timeframe: str,
        target_date: datetime = None
    ) -> Dict[str, Any]:
        """
        특정 날짜의 시간별 지표 집계
        """
        if not self.db_enabled:
            return {
                "error": "MongoDB가 연결되지 않았습니다",
                "market": market,
                "timeframe": timeframe
            }

        if target_date is None:
            target_date = datetime.utcnow()

        try:
            return await self.repository.aggregate_daily_history(
                market, timeframe, target_date
            )
        except Exception as e:
            return {
                "error": f"일별 집계 실패: {str(e)}",
                "market": market,
                "timeframe": timeframe,
                "target_date": target_date
            }

    # ---- AI 분석 결과 저장 ----
    async def save_ai_analysis(
        self,
        market: str,
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        AI 분석 결과를 MongoDB에 저장
        """
        if not self.db_enabled:
            return {
                "error": "MongoDB가 연결되지 않았습니다",
                "market": market
            }

        try:
            db_id = await self.repository.save_ai_analysis(market, analysis)
            return {
                "success": True,
                "market": market,
                "db_id": db_id,
                "saved_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "error": f"AI 분석 저장 실패: {str(e)}",
                "market": market
            }

    # ---- 데이터 정리 ----
    async def cleanup_old_data(self, days: int = 90) -> Dict[str, Any]:
        """
        오래된 데이터 정리
        """
        if not self.db_enabled:
            return {
                "error": "MongoDB가 연결되지 않았습니다"
            }

        try:
            return await self.repository.cleanup_old_data(days)
        except Exception as e:
            return {
                "error": f"데이터 정리 실패: {str(e)}"
            }