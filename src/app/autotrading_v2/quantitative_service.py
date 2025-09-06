"""
정량지표 (차트기반) 서비스 V2
TA-Lib 기반 고성능 기술적 분석 서비스
"""

import asyncio
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone

from src.common.utils.bitcoin.exchange_interface import ExchangeFactory
from src.common.utils.technical_indicators_v2 import TechnicalIndicatorsV2, RegimeDetectorV2, ScoreCalculatorV2
from src.common.utils.logger import set_logger
from src.app.autotrading_v2.models import QuantitativeRequest, QuantitativeResponse

logger = set_logger("quantitative_v2")


class QuantitativeServiceV2:
    """정량지표 분석 서비스 V2"""

    def __init__(self):
        """초기화"""
        self.indicators_calculator = TechnicalIndicatorsV2()
        self.regime_detector = RegimeDetectorV2()
        self.score_calculator = ScoreCalculatorV2()

        # 지표 설정
        self.indicator_config = {
            'adx_period': 14,
            'ema_periods': [20, 50, 200],
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'rsi_period': 14,
            'stoch_k': 14,
            'stoch_d': 3,
            'bb_period': 20,
            'bb_std': 2.0,
            'atr_period': 14,
            'volume_period': 20,
            'momentum_period': 20,
            'return_volatility_period': 20
        }

    async def analyze_market(
        self,
        market: str,
        timeframe: str = "minutes:60",
        count: int = 200,
        exchange: str = "binance",
        testnet: bool = True
    ) -> Dict[str, Any]:
        """
        시장 정량지표 분석 실행

        Args:
            market: 거래 마켓 (예: BTC/USDT)
            timeframe: 시간프레임
            count: 캔들 개수
            exchange: 거래소
            testnet: 테스트넷 사용 여부

        Returns:
            Dict[str, Any]: 분석 결과
        """
        try:
            logger.info("🚀 [1단계] 정량지표 분석 시작")
            logger.info(f"📊 {market} | {timeframe} | {count}개 캔들 | {exchange}")

            # ===== 1단계-1: OHLCV 데이터 수집 =====
            ohlcv_df = await self._get_ohlcv_data(market, timeframe, count, exchange, testnet)

            if ohlcv_df is None or len(ohlcv_df) == 0:
                raise ValueError(f"OHLCV 데이터를 가져올 수 없습니다: {market}")

            logger.info(f"✅ 데이터 수집: {len(ohlcv_df)}개 캔들")

            # ===== 1단계-2: 기술적 지표 계산 =====
            indicators = self.indicators_calculator.calculate_all_indicators(
                ohlcv_df, self.indicator_config
            )
            logger.info(f"✅ 지표 계산: {len(indicators)}개 지표")

            # ===== 1단계-3: 레짐 감지 (시장 환경 구분) =====
            regime, regime_confidence, regime_info = self.regime_detector.detect_regime(indicators)

            # ===== 1단계-4: 지표별 점수화 (-1 ~ +1 스케일) =====
            scores = self.score_calculator.calculate_all_scores(indicators)

            # ===== 1단계-5: 레짐별 가중치 적용 =====
            weighted_score = self._calculate_weighted_score(scores, regime)

            # 가중치 정보 로그
            weights = self.regime_detector.get_regime_weights(regime)
            if regime == "trend":
                logger.info(f"추세장 가중치: 모멘텀({weights['momentum']:.2f}) + MACD({weights['macd']:.2f}) + 변동성({weights['return_volatility']:.2f}) + 거래량({weights['volume']:.2f})")
            elif regime == "range":
                logger.info(f"횡보장 가중치: RSI({weights['rsi']:.2f}) + 볼린저({weights['bollinger']:.2f}) + 거래량({weights['volume']:.2f}) + 모멘텀({weights['momentum']:.2f})")
            else:
                logger.info(f"전환구간 가중치: 절충 적용")

            # ===== 1단계-6: 거래 신호 생성 =====
            signal, signal_confidence, position_size, position_percentage = self._generate_trading_signal(weighted_score, regime_confidence)

            # ===== 1단계-7: 결과 구성 =====
            result = {
                "status": "success",
                "market": market,
                "timeframe": timeframe,
                "timestamp": datetime.now(timezone.utc).isoformat(),

                # === 인간 친화적 분석 결과 ===
                "analysis": {
                    # 시장 상황 요약
                    "market_condition": self._get_market_condition_summary(regime, regime_confidence, indicators),
                    
                    # 거래 신호 및 권장사항
                    "trading_recommendation": self._get_trading_recommendation(signal, weighted_score, position_size, position_percentage, signal_confidence),
                    
                    # 주요 지표 해석
                    "key_indicators": self._get_key_indicators_summary(indicators, scores),
                    
                    # 리스크 평가
                    "risk_assessment": self._get_risk_assessment(weighted_score, regime_confidence, indicators)
                },

                # === 상세 데이터 (AI/시스템용) ===
                "detailed_data": {
                    # 레짐 정보
                    "regime": regime,
                    "regime_confidence": regime_confidence,
                    "regime_info": regime_info,

                    # 기술적 지표 (최신 값만)
                    "indicators": self._extract_latest_indicators(indicators),

                    # 점수 정보
                    "scores": scores,
                    "weighted_score": weighted_score,

                    # 거래 신호
                    "signal": signal,
                    "confidence": signal_confidence,
                    "position_size": position_size,
                    "position_percentage": position_percentage,

                    # 메타데이터
                    "metadata": {
                        "data_points": len(ohlcv_df),
                        "config": self.indicator_config,
                        "exchange": exchange,
                        "testnet": testnet
                    }
                }
            }

            logger.info("🎉 [1단계] 정량지표 분석 완료!")
            logger.info(f"📊 결과: {signal} | 레짐: {regime} | 점수: {weighted_score:.3f} | 신뢰도: {signal_confidence:.2f}")
            logger.info(f"💼 포지션: {position_size} ({position_percentage:.0f}%)")
            return result

        except Exception as e:
            logger.error(f"정량지표 분석 실패: {market} - {str(e)}")
            return {
                "status": "error",
                "market": market,
                "timeframe": timeframe,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
                "regime": "unknown",
                "regime_confidence": 0.0,
                "regime_info": {},
                "indicators": {},
                "scores": {},
                "weighted_score": 0.0,
                "signal": "HOLD",
                "confidence": 0.0,
                "metadata": {}
            }

    async def _get_ohlcv_data(
        self,
        market: str,
        timeframe: str,
        count: int,
        exchange: str,
        testnet: bool
    ) -> Optional[pd.DataFrame]:
        """OHLCV 데이터 수집"""
        try:
            # 거래소 팩토리를 통해 인스턴스 생성
            exchange_instance = ExchangeFactory.create_exchange(
                exchange_type=exchange,
                testnet=testnet
            )

            # OHLCV 데이터 가져오기
            ohlcv_df = await exchange_instance.get_ohlcv_df(
                market=market,
                tf=timeframe,
                count=count
            )

            # 데이터 검증 (최소 20개로 줄임)
            min_required = 50
            if ohlcv_df is None or len(ohlcv_df) < min_required:
                raise ValueError(f"충분한 데이터가 없습니다: {len(ohlcv_df) if ohlcv_df is not None else 0}개 (최소 {min_required}개 필요)")

            # 필요한 컬럼 확인
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            missing_columns = [col for col in required_columns if col not in ohlcv_df.columns]
            if missing_columns:
                raise ValueError(f"필수 컬럼이 없습니다: {missing_columns}")

            # NaN 값 처리
            ohlcv_df = ohlcv_df.dropna()

            if len(ohlcv_df) < min_required:
                raise ValueError(f"NaN 제거 후 데이터가 부족합니다: {len(ohlcv_df)}개 (최소 {min_required}개 필요)")

            return ohlcv_df

        except Exception as e:
            logger.error(f"OHLCV 데이터 수집 실패: {str(e)}")
            return None

    def _extract_latest_indicators(self, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """지표에서 최신 값만 추출"""
        latest_indicators = {}

        for key, value in indicators.items():
            if isinstance(value, np.ndarray) and len(value) > 0:
                latest_value = value[-1]
                if not np.isnan(latest_value):
                    latest_indicators[key] = float(latest_value)
            elif isinstance(value, (int, float)) and not np.isnan(value):
                latest_indicators[key] = float(value)

        return latest_indicators

    def _calculate_weighted_score(self, scores: Dict[str, float], regime: str) -> float:
        """레짐별 가중치 적용 점수 계산"""
        try:
            # 레짐별 가중치 가져오기
            weights = self.regime_detector.get_regime_weights(regime)

            # 가중치 적용 점수 계산
            weighted_score = 0.0
            total_weight = 0.0

            for indicator, score in scores.items():
                if indicator in weights:
                    weight = weights[indicator]
                    weighted_score += score * weight
                    total_weight += weight

            # 정규화
            if total_weight > 0:
                weighted_score = weighted_score / total_weight
            else:
                weighted_score = 0.0

            # -1 ~ +1 범위로 제한
            weighted_score = max(-1.0, min(1.0, weighted_score))

            return weighted_score

        except Exception as e:
            logger.error(f"가중치 점수 계산 실패: {str(e)}")
            return 0.0

    def _generate_trading_signal(self, weighted_score: float, regime_confidence: float) -> Tuple[str, float, str, float]:
        """거래 신호 및 포지션 관리 생성"""
        try:
            # 신호 임계값
            buy_threshold = 0.3
            sell_threshold = -0.3

            # 신호 결정
            if weighted_score >= buy_threshold:
                signal = "BUY"
            elif weighted_score <= sell_threshold:
                signal = "SELL"
            else:
                signal = "HOLD"

            # 포지션 크기 결정 (요구사항에 따라)
            if abs(weighted_score) >= 0.6:
                position_size = "FULL"  # 100%
                position_percentage = 100.0
            elif abs(weighted_score) >= 0.3:
                position_size = "HALF"  # 50%
                position_percentage = 50.0
            else:
                position_size = "HOLD"  # 관망
                position_percentage = 0.0

            # 신뢰도 계산
            # 가중치 점수의 절댓값이 클수록, 레짐 신뢰도가 높을수록 신호 신뢰도 증가
            score_confidence = min(1.0, abs(weighted_score))
            signal_confidence = (score_confidence * 0.7 + regime_confidence * 0.3)

            return signal, signal_confidence, position_size, position_percentage

        except Exception as e:
            logger.error(f"거래 신호 생성 실패: {str(e)}")
            return "HOLD", 0.0, "HOLD", 0.0

    async def health_check(self) -> Dict[str, Any]:
        """서비스 헬스체크"""
        try:
            # 기본 지표 계산 테스트
            test_data = pd.DataFrame({
                'open': np.random.randn(100) + 100,
                'high': np.random.randn(100) + 101,
                'low': np.random.randn(100) + 99,
                'close': np.random.randn(100) + 100,
                'volume': np.random.randn(100) + 1000
            })

            # 지표 계산 테스트
            indicators = self.indicators_calculator.calculate_all_indicators(test_data)

            # 레짐 감지 테스트
            regime, confidence, _ = self.regime_detector.detect_regime(indicators)

            # 점수 계산 테스트
            scores = self.score_calculator.calculate_all_scores(indicators)

            return {
                "indicators_calculation": "ok",
                "regime_detection": "ok",
                "score_calculation": "ok",
                "test_regime": regime,
                "test_confidence": confidence,
                "test_scores_count": len(scores)
            }

        except Exception as e:
            logger.error(f"헬스체크 실패: {str(e)}")
            return {
                "indicators_calculation": "error",
                "regime_detection": "error",
                "score_calculation": "error",
                "error": str(e)
            }

    def get_supported_indicators(self) -> Dict[str, Any]:
        """지원하는 지표 목록 반환"""
        return {
            "trend": {
                "ADX": "Average Directional Index (추세 강도)",
                "EMA": "Exponential Moving Average (20, 50, 200일)",
                "MACD": "Moving Average Convergence Divergence"
            },
            "momentum": {
                "RSI": "Relative Strength Index",
                "Stochastic": "Stochastic Oscillator",
                "Williams_R": "Williams %R",
                "CCI": "Commodity Channel Index"
            },
            "volatility": {
                "Bollinger_Bands": "Bollinger Bands (%b, Bandwidth)",
                "ATR": "Average True Range",
                "Keltner_Channels": "Keltner Channels"
            },
            "volume": {
                "OBV": "On Balance Volume",
                "AD": "Accumulation/Distribution",
                "CMF": "Chaikin Money Flow",
                "Volume_Z_Score": "Volume Z-Score",
                "VWAP": "Volume Weighted Average Price"
            },
            "other": {
                "Momentum": "Momentum (누적수익률, Sharpe-like)",
                "Return_Volatility_Ratio": "수익률/변동성 비율"
            }
        }

    def get_regime_weights(self) -> Dict[str, Any]:
        """레짐별 가중치 반환"""
        return {
            "trend_regime": {
                "momentum": 0.40,
                "macd": 0.20,
                "return_volatility": 0.15,
                "volume": 0.15,
                "rsi": 0.05,
                "bollinger": 0.05
            },
            "range_regime": {
                "rsi": 0.25,
                "bollinger": 0.25,
                "volume": 0.20,
                "momentum": 0.15,
                "macd": 0.10,
                "return_volatility": 0.05
            },
            "transition_regime": {
                "momentum": 0.25,
                "rsi": 0.20,
                "bollinger": 0.20,
                "macd": 0.15,
                "volume": 0.10,
                "return_volatility": 0.10
            }
        }
