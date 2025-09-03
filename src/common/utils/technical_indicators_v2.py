"""
TA-Lib 기반 기술적 지표 계산 모듈 V2
고성능 및 정확성을 위한 TA-Lib 라이브러리 활용
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime
import warnings

# TA-Lib 경고 무시
warnings.filterwarnings('ignore', category=RuntimeWarning)


class TechnicalIndicatorsV2:
    """TA-Lib 기반 기술적 지표 계산 클래스 V2"""

    def __init__(self):
        """초기화"""
        self.indicators_cache = {}

    def calculate_all_indicators(
        self,
        ohlcv_df: pd.DataFrame,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        모든 기술적 지표를 한 번에 계산

        Args:
            ohlcv_df: OHLCV 데이터프레임
            config: 지표 설정 (기본값 사용 가능)

        Returns:
            Dict[str, Any]: 모든 지표 결과
        """
        if config is None:
            config = self._get_default_config()

        # OHLCV 데이터 추출
        high = ohlcv_df['high'].values.astype(np.float64)
        low = ohlcv_df['low'].values.astype(np.float64)
        close = ohlcv_df['close'].values.astype(np.float64)
        volume = ohlcv_df['volume'].values.astype(np.float64)

        # 기본 지표 계산
        indicators = {}

        # 1. 추세 지표
        indicators.update(self._calculate_trend_indicators(high, low, close, config))

        # 2. 모멘텀 지표
        indicators.update(self._calculate_momentum_indicators(high, low, close, config))

        # 3. 변동성 지표
        indicators.update(self._calculate_volatility_indicators(high, low, close, config))

        # 4. 거래량 지표
        indicators.update(self._calculate_volume_indicators(high, low, close, volume, config))

        # 5. 기타 지표
        indicators.update(self._calculate_other_indicators(high, low, close, config))

        # 캐시에 저장
        self.indicators_cache = indicators

        return indicators

    def _get_default_config(self) -> Dict[str, Any]:
        """기본 설정 반환"""
        return {
            # 추세 지표
            'adx_period': 14,
            'ema_periods': [20, 50, 200],
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,

            # 모멘텀 지표
            'rsi_period': 14,
            'stoch_k': 14,
            'stoch_d': 3,

            # 변동성 지표
            'bb_period': 20,
            'bb_std': 2.0,
            'atr_period': 14,

            # 거래량 지표
            'volume_period': 20,

            # 기타
            'momentum_period': 20,
            'return_volatility_period': 20
        }

    def _calculate_trend_indicators(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """추세 지표 계산"""
        indicators = {}

                # ADX (Average Directional Index) - 직접 구현
        indicators['adx'] = self._calculate_adx(high, low, close, config['adx_period'])

        # EMA (Exponential Moving Average) - 직접 구현
        for period in config['ema_periods']:
            indicators[f'ema_{period}'] = self._calculate_ema(close, period)

        # MACD - 직접 구현
        macd, macd_signal, macd_hist = self._calculate_macd(
            close,
            config['macd_fast'],
            config['macd_slow'],
            config['macd_signal']
        )
        indicators['macd'] = macd
        indicators['macd_signal'] = macd_signal
        indicators['macd_histogram'] = macd_hist

        # MACD 크로스오버 신호
        indicators['macd_cross'] = self._detect_macd_cross(macd, macd_signal)

        return indicators

    def _calculate_momentum_indicators(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """모멘텀 지표 계산"""
        indicators = {}

                # RSI - 직접 구현
        indicators['rsi'] = self._calculate_rsi(close, config['rsi_period'])

        # Stochastic - 직접 구현
        stoch_k, stoch_d = self._calculate_stochastic(
            high, low, close,
            config['stoch_k'],
            3,
            config['stoch_d']
        )
        indicators['stoch_k'] = stoch_k
        indicators['stoch_d'] = stoch_d

        # Williams %R - 직접 구현
        indicators['williams_r'] = self._calculate_williams_r(high, low, close, 14)

        # CCI (Commodity Channel Index) - 직접 구현
        indicators['cci'] = self._calculate_cci(high, low, close, 14)

        # 모멘텀 (누적수익률, Sharpe-like)
        indicators.update(self._calculate_momentum_metrics(close, config))

        return indicators

    def _calculate_volatility_indicators(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """변동성 지표 계산"""
        indicators = {}

                # Bollinger Bands - 직접 구현
        bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(
            close,
            config['bb_period'],
            config['bb_std']
        )
        indicators['bb_upper'] = bb_upper
        indicators['bb_middle'] = bb_middle
        indicators['bb_lower'] = bb_lower

        # %b (Percent B)
        indicators['bb_pct_b'] = (close - bb_lower) / (bb_upper - bb_lower + 1e-12)

        # Bandwidth
        indicators['bb_bandwidth'] = (bb_upper - bb_lower) / (bb_middle + 1e-12)

        # ATR (Average True Range) - 직접 구현
        indicators['atr'] = self._calculate_atr(high, low, close, config['atr_period'])

        # Keltner Channels
        indicators.update(self._calculate_keltner_channels(high, low, close, config))

        return indicators

    def _calculate_volume_indicators(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        volume: np.ndarray,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """거래량 지표 계산"""
        indicators = {}

                # OBV (On Balance Volume) - 직접 구현
        indicators['obv'] = self._calculate_obv(close, volume)

        # AD (Accumulation/Distribution) - 직접 구현
        indicators['ad'] = self._calculate_ad(high, low, close, volume)

        # CMF (Chaikin Money Flow) - 직접 구현
        indicators['cmf'] = self._calculate_cmf(high, low, close, volume, 3, 10)

        # Volume Z-Score
        indicators['volume_z_score'] = self._calculate_volume_z_score(volume, config['volume_period'])

        # VWAP (Volume Weighted Average Price)
        indicators['vwap'] = self._calculate_vwap(high, low, close, volume)

        return indicators

    def _calculate_other_indicators(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """기타 지표 계산"""
        indicators = {}

        # 수익률/변동성 비율
        indicators['return_volatility_ratio'] = self._calculate_return_volatility_ratio(
            close, config['return_volatility_period']
        )

        # 가격 위치 (현재 가격이 200EMA 대비 위치)
        if 'ema_200' in self.indicators_cache:
            ema_200 = self.indicators_cache['ema_200']
            indicators['price_vs_ema200'] = (close - ema_200) / (ema_200 + 1e-12)

        return indicators

    def _detect_macd_cross(self, macd: np.ndarray, signal: np.ndarray) -> np.ndarray:
        """MACD 크로스오버 신호 감지"""
        cross = np.zeros_like(macd)

        for i in range(1, len(macd)):
            if (macd[i-1] <= signal[i-1] and macd[i] > signal[i]):
                cross[i] = 1  # 골든크로스
            elif (macd[i-1] >= signal[i-1] and macd[i] < signal[i]):
                cross[i] = -1  # 데드크로스

        return cross

    def _calculate_momentum_metrics(self, close: np.ndarray, config: Dict[str, Any]) -> Dict[str, Any]:
        """모멘텀 메트릭 계산"""
        period = config['momentum_period']

        # 누적수익률
        cumret = (close / np.roll(close, period) - 1.0)
        cumret[:period] = np.nan

        # 수익률
        returns = np.diff(close) / close[:-1]
        returns = np.insert(returns, 0, np.nan)

        # Sharpe-like ratio
        rolling_mean = pd.Series(returns).rolling(window=period).mean().values
        rolling_std = pd.Series(returns).rolling(window=period).std().values
        sharpe_like = rolling_mean / (rolling_std + 1e-12)

        return {
            'momentum_cumret': cumret,
            'momentum_sharpe_like': sharpe_like
        }

    def _calculate_volume_z_score(self, volume: np.ndarray, period: int) -> np.ndarray:
        """거래량 Z-Score 계산"""
        rolling_mean = pd.Series(volume).rolling(window=period).mean().values
        rolling_std = pd.Series(volume).rolling(window=period).std().values
        return (volume - rolling_mean) / (rolling_std + 1e-12)

    def _calculate_vwap(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray) -> np.ndarray:
        """VWAP (Volume Weighted Average Price) 계산"""
        typical_price = (high + low + close) / 3
        vwap = np.cumsum(typical_price * volume) / np.cumsum(volume)
        return vwap

    def _calculate_keltner_channels(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, config: Dict[str, Any]) -> Dict[str, Any]:
        """Keltner Channels 계산"""
        period = 20
        multiplier = 2.0

        # EMA - 직접 구현
        ema = self._calculate_ema(close, period)

        # ATR - 직접 구현
        atr = self._calculate_atr(high, low, close, period)

        # Keltner Channels
        kc_upper = ema + (multiplier * atr)
        kc_lower = ema - (multiplier * atr)

        return {
            'kc_upper': kc_upper,
            'kc_middle': ema,
            'kc_lower': kc_lower
        }

    def _calculate_return_volatility_ratio(self, close: np.ndarray, period: int) -> np.ndarray:
        """수익률/변동성 비율 계산"""
        returns = np.diff(close) / close[:-1]
        returns = np.insert(returns, 0, np.nan)

        rolling_mean = pd.Series(returns).rolling(window=period).mean().values
        rolling_std = pd.Series(returns).rolling(window=period).std().values

        return rolling_mean / (rolling_std + 1e-12)

    # ===== 직접 구현 함수들 =====

    def _calculate_adx(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
        """ADX 직접 구현"""
        # True Range 계산
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        tr[0] = tr1[0]  # 첫 번째 값은 high - low

        # Directional Movement 계산
        dm_plus = high - np.roll(high, 1)
        dm_minus = np.roll(low, 1) - low

        dm_plus = np.where((dm_plus > dm_minus) & (dm_plus > 0), dm_plus, 0)
        dm_minus = np.where((dm_minus > dm_plus) & (dm_minus > 0), dm_minus, 0)

        # 첫 번째 값 초기화
        dm_plus[0] = 0
        dm_minus[0] = 0

        # Smoothed values (Wilder's smoothing)
        atr = self._wilders_smoothing(tr, period)
        di_plus = 100 * self._wilders_smoothing(dm_plus, period) / atr
        di_minus = 100 * self._wilders_smoothing(dm_minus, period) / atr

        # ADX 계산
        dx = 100 * np.abs(di_plus - di_minus) / (di_plus + di_minus + 1e-12)
        adx = self._wilders_smoothing(dx, period)

        return adx

    def _calculate_ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        """EMA 직접 구현"""
        alpha = 2.0 / (period + 1)
        ema = np.zeros_like(prices)
        ema[0] = prices[0]

        for i in range(1, len(prices)):
            ema[i] = alpha * prices[i] + (1 - alpha) * ema[i-1]

        return ema

    def _calculate_macd(self, close: np.ndarray, fast: int, slow: int, signal: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """MACD 직접 구현"""
        ema_fast = self._calculate_ema(close, fast)
        ema_slow = self._calculate_ema(close, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self._calculate_ema(macd_line, signal)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    def _calculate_rsi(self, prices: np.ndarray, period: int) -> np.ndarray:
        """RSI 직접 구현"""
        delta = np.diff(prices)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)

        # Wilder's smoothing
        avg_gain = self._wilders_smoothing(gain, period)
        avg_loss = self._wilders_smoothing(loss, period)

        rs = avg_gain / (avg_loss + 1e-12)
        rsi = 100 - (100 / (1 + rs))

        # 첫 번째 값은 NaN
        rsi = np.insert(rsi, 0, np.nan)

        return rsi

    def _calculate_stochastic(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, k_period: int, k_smooth: int, d_period: int) -> Tuple[np.ndarray, np.ndarray]:
        """Stochastic 직접 구현"""
        lowest_low = pd.Series(low).rolling(window=k_period).min().values
        highest_high = pd.Series(high).rolling(window=k_period).max().values

        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low + 1e-12))
        k_percent = pd.Series(k_percent).rolling(window=k_smooth).mean().values
        d_percent = pd.Series(k_percent).rolling(window=d_period).mean().values

        return k_percent, d_percent

    def _calculate_williams_r(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
        """Williams %R 직접 구현"""
        highest_high = pd.Series(high).rolling(window=period).max().values
        lowest_low = pd.Series(low).rolling(window=period).min().values

        williams_r = -100 * ((highest_high - close) / (highest_high - lowest_low + 1e-12))

        return williams_r

    def _calculate_cci(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
        """CCI 직접 구현"""
        typical_price = (high + low + close) / 3
        sma = pd.Series(typical_price).rolling(window=period).mean().values
        mad = pd.Series(np.abs(typical_price - sma)).rolling(window=period).mean().values

        cci = (typical_price - sma) / (0.015 * mad + 1e-12)

        return cci

    def _wilders_smoothing(self, data: np.ndarray, period: int) -> np.ndarray:
        """Wilder's smoothing 직접 구현"""
        smoothed = np.zeros_like(data)
        smoothed[0] = data[0]

        alpha = 1.0 / period

        for i in range(1, len(data)):
            smoothed[i] = alpha * data[i] + (1 - alpha) * smoothed[i-1]

        return smoothed

    def _calculate_bollinger_bands(self, close: np.ndarray, period: int, std_dev: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Bollinger Bands 직접 구현"""
        sma = pd.Series(close).rolling(window=period).mean().values
        std = pd.Series(close).rolling(window=period).std().values

        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)

        return upper_band, sma, lower_band

    def _calculate_atr(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
        """ATR 직접 구현"""
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        tr[0] = tr1[0]

        atr = self._wilders_smoothing(tr, period)
        return atr

    def _calculate_obv(self, close: np.ndarray, volume: np.ndarray) -> np.ndarray:
        """OBV 직접 구현"""
        obv = np.zeros_like(close)
        obv[0] = volume[0]

        for i in range(1, len(close)):
            if close[i] > close[i-1]:
                obv[i] = obv[i-1] + volume[i]
            elif close[i] < close[i-1]:
                obv[i] = obv[i-1] - volume[i]
            else:
                obv[i] = obv[i-1]

        return obv

    def _calculate_ad(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray) -> np.ndarray:
        """AD (Accumulation/Distribution) 직접 구현"""
        clv = ((close - low) - (high - close)) / (high - low + 1e-12)
        ad = np.cumsum(clv * volume)
        return ad

    def _calculate_cmf(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray, fast: int, slow: int) -> np.ndarray:
        """CMF (Chaikin Money Flow) 직접 구현"""
        clv = ((close - low) - (high - close)) / (high - low + 1e-12)
        ad = clv * volume

        fast_sum = pd.Series(ad).rolling(window=fast).sum().values
        slow_sum = pd.Series(ad).rolling(window=slow).sum().values

        cmf = fast_sum - slow_sum
        return cmf


class RegimeDetectorV2:
    """시장 레짐 감지 클래스 V2"""

    def __init__(self):
        """초기화"""
        self.regime_weights = {
            'trend': {
                'momentum': 0.40,
                'macd': 0.20,
                'return_volatility': 0.15,
                'volume': 0.15,
                'rsi': 0.05,
                'bollinger': 0.05
            },
            'range': {
                'rsi': 0.25,
                'bollinger': 0.25,
                'volume': 0.20,
                'momentum': 0.15,
                'macd': 0.10,
                'return_volatility': 0.05
            }
        }

    def detect_regime(
        self,
        indicators: Dict[str, Any],
        adx_threshold_high: float = 25.0,
        adx_threshold_low: float = 20.0
    ) -> Tuple[str, float, Dict[str, Any]]:
        """
        시장 레짐 감지 V2

        Args:
            indicators: 계산된 지표들
            adx_threshold_high: 추세장 판별 임계값
            adx_threshold_low: 횡보장 판별 임계값

        Returns:
            (regime, confidence, regime_info): 레짐, 신뢰도, 레짐 정보
        """
        if not indicators or 'adx' not in indicators:
            return "unknown", 0.0, {}

        adx = indicators['adx']
        ema_200 = indicators.get('ema_200', np.array([]))

        if len(adx) == 0:
            return "unknown", 0.0, {}

        latest_adx = adx[-1]
        latest_ema_200 = ema_200[-1] if len(ema_200) > 0 else np.nan

        # NaN 체크
        if np.isnan(latest_adx):
            return "unknown", 0.0, {}

        regime_info = {
            'adx': latest_adx,
            'ema_200': latest_ema_200,
            'adx_threshold_high': adx_threshold_high,
            'adx_threshold_low': adx_threshold_low
        }

        # 추세장 판별
        if latest_adx > adx_threshold_high:
            regime = "trend"
            # ADX가 높을수록 신뢰도 증가
            confidence = min(1.0, (latest_adx - adx_threshold_high) / 20.0)
            regime_info['trend_strength'] = 'strong' if latest_adx > 40 else 'moderate'
        # 횡보장 판별
        elif latest_adx < adx_threshold_low:
            regime = "range"
            # ADX가 낮을수록 신뢰도 증가
            confidence = min(1.0, (adx_threshold_low - latest_adx) / 10.0)
            regime_info['range_strength'] = 'strong' if latest_adx < 15 else 'moderate'
        # 전환 구간
        else:
            regime = "transition"
            confidence = 0.5
            regime_info['transition_zone'] = True

        regime_info['regime'] = regime
        regime_info['confidence'] = confidence

        return regime, confidence, regime_info

    def get_regime_weights(self, regime: str) -> Dict[str, float]:
        """레짐별 가중치 반환"""
        return self.regime_weights.get(regime, self.regime_weights['trend'])


class ScoreCalculatorV2:
    """지표별 점수 계산 클래스 V2"""

    def __init__(self):
        """초기화"""
        self.score_rules = {
            'momentum': self._calculate_momentum_score,
            'rsi': self._calculate_rsi_score,
            'bollinger': self._calculate_bollinger_score,
            'macd': self._calculate_macd_score,
            'volume': self._calculate_volume_score,
            'return_volatility': self._calculate_return_volatility_score
        }

    def calculate_all_scores(self, indicators: Dict[str, Any]) -> Dict[str, float]:
        """모든 지표의 점수 계산"""
        scores = {}

        for indicator_name, score_func in self.score_rules.items():
            try:
                scores[indicator_name] = score_func(indicators)
            except Exception as e:
                print(f"Warning: Failed to calculate {indicator_name} score: {e}")
                scores[indicator_name] = 0.0

        return scores

    def _calculate_momentum_score(self, indicators: Dict[str, Any]) -> float:
        """모멘텀 점수 계산 (-1 ~ +1)"""
        cumret = indicators.get('momentum_cumret', np.array([]))
        sharpe = indicators.get('momentum_sharpe_like', np.array([]))

        if len(cumret) == 0 or len(sharpe) == 0:
            return 0.0

        latest_cumret = cumret[-1]
        latest_sharpe = sharpe[-1]

        if np.isnan(latest_cumret) or np.isnan(latest_sharpe):
            return 0.0

        threshold = 0.10

        # 수익률 기반 점수
        if latest_cumret >= threshold:
            ret_score = 1.0
        elif latest_cumret <= -threshold:
            ret_score = -1.0
        else:
            ret_score = latest_cumret / threshold

        # Sharpe 기반 점수
        if latest_sharpe >= 1.0:
            sharpe_score = 1.0
        elif latest_sharpe <= -1.0:
            sharpe_score = -1.0
        else:
            sharpe_score = latest_sharpe

        # 종합 점수 (가중평균)
        return (ret_score * 0.7 + sharpe_score * 0.3)

    def _calculate_rsi_score(self, indicators: Dict[str, Any]) -> float:
        """RSI 점수 계산 (-1 ~ +1)"""
        rsi = indicators.get('rsi', np.array([]))

        if len(rsi) == 0:
            return 0.0

        latest_rsi = rsi[-1]

        if np.isnan(latest_rsi):
            return 0.0

        if latest_rsi <= 20:
            return 1.0
        elif latest_rsi >= 80:
            return -1.0
        elif latest_rsi <= 30:
            return 0.5
        elif latest_rsi >= 70:
            return -0.5
        else:
            # 30-70 구간에서 선형 보간
            if latest_rsi < 50:
                return 0.5 * (50 - latest_rsi) / 20
            else:
                return -0.5 * (latest_rsi - 50) / 20

    def _calculate_bollinger_score(self, indicators: Dict[str, Any]) -> float:
        """볼린저 밴드 점수 계산 (-1 ~ +1)"""
        pct_b = indicators.get('bb_pct_b', np.array([]))
        bandwidth = indicators.get('bb_bandwidth', np.array([]))

        if len(pct_b) == 0:
            return 0.0

        latest_pct_b = pct_b[-1]
        latest_bandwidth = bandwidth[-1] if len(bandwidth) > 0 else 0.0

        if np.isnan(latest_pct_b):
            return 0.0

        # %b 기반 점수
        if latest_pct_b <= 0.05:
            bb_score = 1.0
        elif latest_pct_b >= 0.95:
            bb_score = -1.0
        elif latest_pct_b <= 0.1:
            bb_score = 0.5
        elif latest_pct_b >= 0.9:
            bb_score = -0.5
        else:
            bb_score = 0.0

        # Bandwidth가 넓을수록 신뢰도 증가
        if not np.isnan(latest_bandwidth):
            bandwidth_multiplier = min(2.0, max(0.5, latest_bandwidth * 10))
            bb_score *= bandwidth_multiplier

        return bb_score

    def _calculate_macd_score(self, indicators: Dict[str, Any]) -> float:
        """MACD 점수 계산 (-1 ~ +1)"""
        macd = indicators.get('macd', np.array([]))
        signal = indicators.get('macd_signal', np.array([]))
        histogram = indicators.get('macd_histogram', np.array([]))

        if len(macd) == 0 or len(signal) == 0:
            return 0.0

        latest_macd = macd[-1]
        latest_signal = signal[-1]
        latest_histogram = histogram[-1] if len(histogram) > 0 else 0.0

        if np.isnan(latest_macd) or np.isnan(latest_signal):
            return 0.0

        # 골든크로스/데드크로스 판별
        if latest_macd > latest_signal and latest_histogram > 0:
            if latest_macd > 0:  # 0선 위에서 골든크로스
                return 1.0
            else:  # 0선 아래에서 골든크로스
                return 0.5
        elif latest_macd < latest_signal and latest_histogram < 0:
            if latest_macd < 0:  # 0선 아래에서 데드크로스
                return -1.0
            else:  # 0선 위에서 데드크로스
                return -0.5
        else:
            return 0.0

    def _calculate_volume_score(self, indicators: Dict[str, Any]) -> float:
        """거래량 점수 계산 (-1 ~ +1)"""
        volume_z = indicators.get('volume_z_score', np.array([]))

        if len(volume_z) == 0:
            return 0.0

        latest_volume_z = volume_z[-1]

        if np.isnan(latest_volume_z):
            return 0.0

        if latest_volume_z >= 2.0:
            return 1.0
        elif latest_volume_z <= -2.0:
            return -1.0
        elif latest_volume_z >= 1.0:
            return 0.5
        elif latest_volume_z <= -1.0:
            return -0.5
        else:
            return 0.0

    def _calculate_return_volatility_score(self, indicators: Dict[str, Any]) -> float:
        """수익률/변동성 점수 계산 (-1 ~ +1)"""
        rv_ratio = indicators.get('return_volatility_ratio', np.array([]))

        if len(rv_ratio) == 0:
            return 0.0

        latest_rv_ratio = rv_ratio[-1]

        if np.isnan(latest_rv_ratio):
            return 0.0

        if latest_rv_ratio >= 2.0:
            return 1.0
        elif latest_rv_ratio <= -2.0:
            return -1.0
        elif latest_rv_ratio >= 1.0:
            return 0.5
        elif latest_rv_ratio <= -1.0:
            return -0.5
        else:
            return 0.0
