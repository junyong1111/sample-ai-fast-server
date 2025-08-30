from __future__ import annotations

from typing import Dict, Any, List, Literal, Optional, Tuple
from datetime import datetime
import pandas as pd

from src.common.utils.bitcoin.exchange_interface import ExchangeFactory, Timeframe
from .database import get_mongodb_service


class ChartService:
    def __init__(self, exchange_type: str = "binance", api_key: str | None = None, secret: str | None = None, testnet: bool = False):
        """
        거래소를 선택할 수 있는 차트 서비스

        Args:
            exchange_type: 'upbit' 또는 'binance'
            api_key: API 키 (바이낸스만 해당)
            secret: 시크릿 키 (바이낸스만 해당)
            testnet: 테스트넷 사용 여부 (바이낸스만 해당)
        """
        self.exchange_type = exchange_type.lower()
        self.exchange = ExchangeFactory.create_exchange(
            exchange_type=exchange_type,
            api_key=api_key,
            secret=secret,
            testnet=testnet
        )

    # ---- 거래소 정보 ----
    def get_exchange_info(self) -> Dict[str, Any]:
        """현재 선택된 거래소 정보 반환"""
        return ExchangeFactory.get_exchange_info(self.exchange_type)

    def get_supported_exchanges(self) -> List[str]:
        """지원하는 거래소 목록 반환"""
        return ExchangeFactory.get_supported_exchanges()

    # ---- health ----
    async def get_chart_health(self) -> Dict[str, Any]:
        """거래소 헬스체크"""
        health = await self.exchange.get_chart_health()
        health["exchange_type"] = self.exchange_type
        return health

    # ---- 데이터 조회 ----
    async def get_candles(self, market: str, tf: Timeframe = "minutes:60", count: int = 200) -> pd.DataFrame:
        """
        원시 캔들 DataFrame 반환 (index: timestamp, cols: open/high/low/close/volume)
        """
        return await self.exchange.get_ohlcv_df(market, tf, count)

    # ---- 지표 계산(전체) ----
    def compute_indicators(
        self,
        df: pd.DataFrame,
        momentum_window: int = 20,
        vol_window: int = 20,
        rsi_period: int = 14,
        bb_period: int = 20,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9
    ) -> Dict[str, Any]:
        """
        하나의 DataFrame으로 모든 지표를 계산해서 dict로 반환
        """
        return self.exchange.compute_indicators(
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
        return self.exchange.rule_signals(indicators)

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
            "exchange": self.exchange_type,
            "market": market,
            "timeframe": tf,
            "count": count,
            "asof": ind.get("time"),
            "indicators": ind,
            "signals": rules
        }

    # ---- 거래 신호 조회 (에이전트용 상세 데이터 + MongoDB 저장) ----
    async def get_trading_signal_with_storage(
        self,
        market: str,
        tf: Timeframe = "minutes:60",
        count: int = 200,
        momentum_window: int = 20, vol_window: int = 20,
        rsi_period: int = 14, bb_period: int = 20,
        macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9,
        save_to_db: bool = True
    ) -> Dict[str, Any]:
        """
        거래 신호 조회 + MongoDB 저장 (에이전트용)

        Args:
            market: 거래 시장
            tf: 시간프레임
            count: 캔들 개수
            momentum_window: 모멘텀 윈도우
            vol_window: 거래량 윈도우
            rsi_period: RSI 기간
            bb_period: 볼린저 밴드 기간
            macd_fast: MACD 빠른 이동평균
            macd_slow: MACD 느린 이동평균
            macd_signal: MACD 시그널
            save_to_db: MongoDB 저장 여부

        Returns:
            모든 데이터를 포함한 거래 신호 정보
        """
        try:
            # 캔들 데이터 조회
            df = await self.get_candles(market, tf, count)

            # 지표 계산
            indicators = self.compute_indicators(
                df,
                momentum_window=momentum_window, vol_window=vol_window,
                rsi_period=rsi_period, bb_period=bb_period,
                macd_fast=macd_fast, macd_slow=macd_slow, macd_signal=macd_signal
            )

            # 규칙 평가
            rule_evaluation = self.evaluate_rules(indicators)

            # 현재 가격 (최신 종가)
            current_price = float(indicators.get("close", 0))

            # 종합 신호
            overall_signal = rule_evaluation.get("overall", "HOLD")

            # 사용된 파라미터
            parameters = {
                "timeframe": tf,
                "count": count,
                "momentum_window": momentum_window,
                "vol_window": vol_window,
                "rsi_period": rsi_period,
                "bb_period": bb_period,
                "macd_fast": macd_fast,
                "macd_slow": macd_slow,
                "macd_signal": macd_signal
            }

            # MongoDB에 저장
            if save_to_db:
                try:
                    mongodb = await get_mongodb_service()
                    await mongodb.save_trading_signal_with_details(
                        exchange=self.exchange_type,
                        market=market,
                        timeframe=tf,
                        current_price=current_price,
                        overall_signal=overall_signal,
                        indicators=indicators,
                        rule_evaluation=rule_evaluation,
                        parameters=parameters,
                        metadata={
                            "service_version": "1.0.0",
                            "data_source": "ccxt",
                            "calculation_method": "technical_analysis"
                        }
                    )
                except Exception as e:
                    print(f"⚠️ MongoDB 저장 실패 (계속 진행): {e}")

            # 에이전트용 상세 응답 구성
            response = {
                # 기본 정보
                "exchange": self.exchange_type,
                "market": market,
                "current_price": current_price,
                "overall_signal": overall_signal,
                "timeframe": tf,
                "timestamp": indicators.get("time", datetime.utcnow()),

                # 상세 지표 데이터 (에이전트용)
                "indicators": indicators,
                "rule_evaluation": rule_evaluation,
                "signal_details": {
                    "signal_strength": self._calculate_signal_strength(indicators, rule_evaluation),
                    "confidence_level": self._calculate_confidence_level(rule_evaluation),
                    "trend_direction": self._determine_trend_direction(indicators),
                    "volatility_level": self._calculate_volatility_level(indicators)
                },

                # 파라미터 정보
                "parameters_used": parameters,

                # 메타데이터
                "metadata": {
                    "candles_count": len(df),
                    "calculation_time": datetime.utcnow().isoformat(),
                    "exchange_type": self.exchange_type,
                    "data_quality": "high" if len(df) >= count else "partial"
                }
            }

            return response

        except Exception as e:
            print(f"❌ 거래 신호 조회 실패: {e}")
            raise

    def _calculate_signal_strength(self, indicators: Dict[str, Any], rule_evaluation: Dict[str, Any]) -> float:
        """신호 강도 계산 (0-100)"""
        try:
            # RSI 기반 강도
            rsi_strength = 0
            if "rsi" in indicators:
                rsi = indicators["rsi"]
                if rsi <= 20 or rsi >= 80:
                    rsi_strength = 100
                elif rsi <= 30 or rsi >= 70:
                    rsi_strength = 80
                elif rsi <= 40 or rsi >= 60:
                    rsi_strength = 60
                else:
                    rsi_strength = 40

            # 볼린저 밴드 기반 강도
            bb_strength = 0
            if "bb_pct_b" in indicators:
                bb_pct_b = indicators["bb_pct_b"]
                if bb_pct_b <= 0.1 or bb_pct_b >= 0.9:
                    bb_strength = 100
                elif bb_pct_b <= 0.2 or bb_pct_b >= 0.8:
                    bb_strength = 80
                elif bb_pct_b <= 0.3 or bb_pct_b >= 0.7:
                    bb_strength = 60
                else:
                    bb_strength = 40

            # MACD 기반 강도
            macd_strength = 0
            if "macd_cross" in indicators:
                macd_cross = indicators["macd_cross"]
                if macd_cross in ["bullish", "bearish"]:
                    macd_strength = 80
                else:
                    macd_strength = 40

            # 종합 강도 계산
            total_strength = (rsi_strength + bb_strength + macd_strength) / 3
            return round(total_strength, 2)

        except Exception:
            return 50.0  # 기본값

    def _calculate_confidence_level(self, rule_evaluation: Dict[str, Any]) -> str:
        """신뢰도 레벨 계산"""
        try:
            # 개별 규칙 신호 개수
            buy_signals = 0
            sell_signals = 0
            neutral_signals = 0

            for key, value in rule_evaluation.items():
                if key.startswith("rule") and key != "overall":
                    if value == "buy":
                        buy_signals += 1
                    elif value == "sell":
                        sell_signals += 1
                    else:
                        neutral_signals += 1

            total_rules = buy_signals + sell_signals + neutral_signals

            if total_rules == 0:
                return "unknown"

            # 신뢰도 계산
            if buy_signals >= 4:
                return "very_high_buy"
            elif sell_signals >= 4:
                return "very_high_sell"
            elif buy_signals >= 3:
                return "high_buy"
            elif sell_signals >= 3:
                return "high_sell"
            elif buy_signals >= 2:
                return "medium_buy"
            elif sell_signals >= 2:
                return "medium_sell"
            else:
                return "low"

        except Exception:
            return "unknown"

    def _determine_trend_direction(self, indicators: Dict[str, Any]) -> str:
        """트렌드 방향 판단"""
        try:
            # 이동평균 기반 트렌드
            sma_20 = indicators.get("sma_20")
            close = indicators.get("close")

            if sma_20 and close:
                if close > sma_20 * 1.02:  # 2% 이상 위
                    return "strong_uptrend"
                elif close > sma_20:
                    return "uptrend"
                elif close < sma_20 * 0.98:  # 2% 이상 아래
                    return "strong_downtrend"
                elif close < sma_20:
                    return "downtrend"
                else:
                    return "sideways"

            return "unknown"

        except Exception:
            return "unknown"

    def _calculate_volatility_level(self, indicators: Dict[str, Any]) -> str:
        """변동성 레벨 계산"""
        try:
            # 볼린저 밴드 대역폭 기반
            bb_bandwidth = indicators.get("bb_bandwidth")

            if bb_bandwidth:
                if bb_bandwidth >= 0.1:
                    return "very_high"
                elif bb_bandwidth >= 0.08:
                    return "high"
                elif bb_bandwidth >= 0.06:
                    return "medium"
                elif bb_bandwidth >= 0.04:
                    return "low"
                else:
                    return "very_low"

            return "unknown"

        except Exception:
            return "unknown"

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
            "exchange": self.exchange_type,
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
            "exchange": self.exchange_type,
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
            "exchange": self.exchange_type,
            "market": market,
            "timeframe": tf,
            "asof": ind.get("time"),
            "price": ind.get("close"),
            "rsi": {"value": ind.get("rsi"), "signal": rules.get("rule4_rsi")},
            "boll_pct_b": {"value": ind.get("bb_pct_b"), "signal": rules.get("rule5_bollinger")},
            "macd_cross": {"value": ind.get("macd_cross"), "signal": rules.get("rule6_macd")},
            "overall": rules.get("overall")
        }

    # ---- 추가 거래소 기능 ----
    async def get_ticker(self, market: str) -> Dict[str, Any]:
        """현재 가격 정보 조회"""
        ticker = await self.exchange.get_ticker(market)
        ticker["exchange"] = self.exchange_type
        return ticker

    async def get_orderbook(self, market: str, limit: int = 20) -> Dict[str, Any]:
        """호가창 정보 조회"""
        orderbook = await self.exchange.get_orderbook(market, limit)
        orderbook["exchange"] = self.exchange_type
        return orderbook

    async def get_recent_trades(self, market: str, limit: int = 100) -> List[Dict[str, Any]]:
        """최근 거래 내역 조회"""
        trades = await self.exchange.get_recent_trades(market, limit)
        for trade in trades:
            trade["exchange"] = self.exchange_type
        return trades