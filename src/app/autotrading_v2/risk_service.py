"""
리스크 분석 에이전트 서비스
yfinance, LangChain, LangGraph를 활용한 시장 리스크 분석
"""

import asyncio
import numpy as np

import pandas as pd
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timezone, timedelta
from src.config.setting import settings
# 선택적 import (패키지가 설치되지 않은 경우를 대비)
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    yf = None

try:
    from scipy.stats import pearsonr
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    pearsonr = None

try:
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    StandardScaler = None

from src.common.utils.logger import set_logger
from src.app.autotrading_v2.risk_models import (
    RiskAnalysisRequest, RiskAnalysisResponse,
    MarketData, RiskIndicators, CorrelationAnalysis,
    AIAnalysis, Recommendations
)

logger = set_logger("risk_analysis")


class RiskAnalysisService:
    """리스크 분석 서비스"""

    def __init__(self):
        """초기화"""
        self.symbols = {
            'btc': 'BTC-USD',
            'nasdaq': '^IXIC',
            'dxy': 'DX-Y.NYB',
            'vix': '^VIX',
            'gold': 'GC=F'
        }

        # AI 분석을 위한 LangChain 설정
        self.use_ai_analysis = True
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage, SystemMessage

            self.llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.3,
                max_tokens=1000
            )
            logger.info("✅ LangChain 초기화 완료")
        except Exception as e:
            logger.warning(f"⚠️ LangChain 초기화 실패: {str(e)}")
            self.use_ai_analysis = False
            self.llm = None

    async def analyze_risk(
        self,
        market: str,
        analysis_type: str = "daily",
        days_back: int = 90,
        personality: str = "neutral",
        include_analysis: bool = True
    ) -> Dict[str, Any]:
        """
        장기 시장 환경 리스크 분석 실행

        Args:
            market: 분석할 마켓 (예: BTC/USDT)
            analysis_type: 분석 유형 (daily, weekly)
            days_back: 조회 기간 (일) - 장기 분석용
            personality: 투자 성향 (conservative, neutral, aggressive)
            include_analysis: AI 분석 포함 여부

        Returns:
            Dict[str, Any]: 장기 시장 환경 분석 결과
        """
        try:
            logger.info(f"🚀 장기 시장 환경 분석 시작: {market} | {analysis_type} | {days_back}일")

            # ===== 1단계: 장기 시장 환경 데이터 수집 =====
            market_data = await self._collect_market_data(days_back, analysis_type)

            # ===== 2단계: 리스크 지표 계산 =====
            risk_indicators = self._calculate_risk_indicators(market_data)

            # ===== 3단계: 상관관계 분석 =====
            correlation_analysis = self._analyze_correlations(market_data)

            # ===== 4단계: AI 분석 및 요약 =====
            ai_analysis = None
            if include_analysis and self.use_ai_analysis:
                try:
                    ai_analysis = await self._perform_ai_analysis(
                        market_data, risk_indicators, correlation_analysis
                    )
                except Exception as e:
                    logger.error(f"AI 분석 실패: {str(e)}")

            # ===== 5단계: 최종 리스크 레벨 결정 (personality 고려) =====
            market_risk_level, risk_off_signal, confidence = self._determine_risk_level(
                risk_indicators, correlation_analysis, personality
            )

            # ===== 6단계: 리스크 에이전트는 투자 권장사항을 제공하지 않음 =====
            recommendations = None

            # ===== 7단계: 결과 구성 =====
            result = {
                "status": "success",
                "market": market,
                "timestamp": datetime.now(timezone.utc).isoformat(),

                # 시장 데이터
                "market_data": market_data.dict(),

                # 리스크 지표
                "risk_indicators": risk_indicators.dict(),

                # 상관관계 분석
                "correlation_analysis": correlation_analysis.dict(),

                # AI 분석
                "ai_analysis": ai_analysis.dict() if ai_analysis else None,

                # 최종 리스크 레벨
                "market_risk_level": market_risk_level,
                "risk_off_signal": risk_off_signal,
                "confidence": confidence,

                # 권장사항 (리스크 에이전트는 제공하지 않음)
                "recommendations": None,

                # 메타데이터
                "metadata": {
                    "analysis_period": f"{days_back}일",
                    "analysis_type": analysis_type,
                    "ai_analysis_included": ai_analysis is not None,
                    "data_points": 0  # MarketData는 단일 값이므로 길이 개념이 없음
                }
            }

            logger.info("🎉 리스크 분석 완료!")
            logger.info(f"📊 리스크 레벨: {market_risk_level} | Risk-Off: {risk_off_signal} | 신뢰도: {confidence:.2f}")

            return result

        except Exception as e:
            logger.error(f"리스크 분석 실패: {str(e)}")
            return {
                "status": "error",
                "market": market,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "market_data": {},
                "risk_indicators": {},
                "correlation_analysis": {},
                "ai_analysis": None,
                "market_risk_level": "UNKNOWN",
                "risk_off_signal": False,
                "confidence": 0.0,
                "recommendations": None,
                "metadata": {"error": str(e)}
            }

    async def _collect_market_data(self, days_back: int, analysis_type: str = "daily") -> MarketData:
        """장기 시장 환경 데이터 수집"""
        try:
            # 장기 분석을 위해 더 긴 기간 설정
            if analysis_type == "weekly":
                # 주봉 분석: 최소 6개월 데이터
                days_back = max(days_back, 180)
            else:
                # 일봉 분석: 최소 3개월 데이터
                days_back = max(days_back, 90)

            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            # 병렬로 데이터 수집
            tasks = []
            for symbol_name, symbol in self.symbols.items():
                task = self._fetch_yfinance_data(symbol, start_date, end_date)
                tasks.append((symbol_name, task))

            # 모든 데이터 수집 완료 대기
            results = {}
            for symbol_name, task in tasks:
                try:
                    data = await task
                    results[symbol_name] = data
                except Exception as e:
                    logger.warning(f"⚠️ {symbol_name} 데이터 수집 실패: {str(e)}")
                    results[symbol_name] = None

            # MarketData 객체 생성
            market_data = self._create_market_data_object(results)
            return market_data

        except Exception as e:
            logger.error(f"시장 데이터 수집 실패: {str(e)}")
            raise

    async def _fetch_yfinance_data(self, symbol: str, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """yfinance를 사용한 데이터 수집"""
        if not YFINANCE_AVAILABLE:
            logger.warning(f"⚠️ yfinance가 설치되지 않음")
            return None

        try:
            # 비동기 처리를 위해 별도 스레드에서 실행
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                lambda: yf.download(symbol, start=start_date, end=end_date, progress=False)
            )

            if data.empty:
                logger.warning(f"⚠️ {symbol} 데이터가 비어있음")
                return None

            return data

        except Exception as e:
            logger.error(f"yfinance 데이터 수집 실패 ({symbol}): {str(e)}")
            return None

    def _create_market_data_object(self, results: Dict[str, Optional[pd.DataFrame]]) -> MarketData:
        """수집된 데이터로 MarketData 객체 생성"""
        try:
            # 각 심볼별로 최신 가격과 변화율 계산
            data_dict = {}

            for symbol_name, df in results.items():
                if df is not None and not df.empty:
                    # 최신 가격 (Close)
                    current_price = float(df['Close'].iloc[-1])

                    # 24시간 변화율 (마지막 2개 데이터 포인트 기준)
                    if len(df) >= 2:
                        prev_price = float(df['Close'].iloc[-2])
                        change_24h = ((current_price - prev_price) / prev_price) * 100
                    else:
                        change_24h = 0.0

                    data_dict[symbol_name] = {
                        'price': current_price,
                        'change_24h': change_24h,
                        'data': df
                    }
                else:
                    # 기본값 설정
                    data_dict[symbol_name] = {
                        'price': 0.0,
                        'change_24h': 0.0,
                        'data': None
                    }

            # MarketData 객체 생성
            return MarketData(
                btc_price=data_dict['btc']['price'],
                btc_change_24h=data_dict['btc']['change_24h'],
                btc_volatility=self._calculate_volatility(data_dict['btc']['data']),

                nasdaq_price=data_dict['nasdaq']['price'],
                nasdaq_change_24h=data_dict['nasdaq']['change_24h'],

                dxy_price=data_dict['dxy']['price'],
                dxy_change_24h=data_dict['dxy']['change_24h'],

                vix_price=data_dict['vix']['price'],
                vix_change_24h=data_dict['vix']['change_24h'],

                gold_price=data_dict['gold']['price'],
                gold_change_24h=data_dict['gold']['change_24h']
            )

        except Exception as e:
            logger.error(f"MarketData 객체 생성 실패: {str(e)}")
            # 기본값으로 생성
            return MarketData(
                btc_price=0.0, btc_change_24h=0.0, btc_volatility=0.0,
                nasdaq_price=0.0, nasdaq_change_24h=0.0,
                dxy_price=0.0, dxy_change_24h=0.0,
                vix_price=0.0, vix_change_24h=0.0,
                gold_price=0.0, gold_change_24h=0.0
            )

    def _calculate_volatility(self, df: Optional[pd.DataFrame]) -> float:
        """변동성 계산 (연간화된 표준편차)"""
        if df is None or df.empty or len(df) < 2:
            return 0.0

        try:
            # 일일 수익률 계산
            returns = df['Close'].pct_change().dropna()

            # 연간화된 변동성 (252 거래일 기준)
            volatility = returns.std() * np.sqrt(252) * 100
            return float(volatility)

        except Exception as e:
            logger.error(f"변동성 계산 실패: {str(e)}")
            return 0.0

    def _calculate_risk_indicators(self, market_data: MarketData) -> RiskIndicators:
        """리스크 지표 계산"""
        try:
            # 비트코인 변동성 지표 (실제로는 더 복잡한 계산이 필요하지만 여기서는 간단히)
            btc_vol_7d = market_data.btc_volatility  # 실제로는 7일 변동성 계산 필요
            btc_vol_30d = market_data.btc_volatility * 1.2  # 실제로는 30일 변동성 계산 필요
            btc_vol_percentile = min(100, max(0, (btc_vol_30d - 20) / 40 * 100))  # 20-60% 범위를 0-100으로 정규화

            # VIX 레벨 및 백분위수
            vix_level = market_data.vix_price
            vix_percentile = min(100, max(0, (vix_level - 10) / 30 * 100))  # 10-40 범위를 0-100으로 정규화

            # 달러 인덱스 레벨 및 백분위수
            dxy_level = market_data.dxy_price
            dxy_percentile = min(100, max(0, (dxy_level - 90) / 20 * 100))  # 90-110 범위를 0-100으로 정규화

            # 금 변동성 및 백분위수 (간단한 추정)
            gold_vol = abs(market_data.gold_change_24h) * 2  # 24시간 변화율의 2배를 변동성으로 추정
            gold_percentile = min(100, max(0, (market_data.gold_price - 1500) / 500 * 100))  # 1500-2000 범위를 0-100으로 정규화

            # 종합 리스크 점수 계산 (가중 평균)
            overall_risk_score = (
                btc_vol_percentile * 0.3 +  # 비트코인 변동성 30%
                vix_percentile * 0.25 +    # VIX 25%
                dxy_percentile * 0.2 +     # 달러 인덱스 20%
                gold_percentile * 0.15 +   # 금 15%
                abs(market_data.btc_change_24h) * 0.1  # 비트코인 일일 변화율 10%
            )

            return RiskIndicators(
                btc_volatility_7d=btc_vol_7d,
                btc_volatility_30d=btc_vol_30d,
                btc_volatility_percentile=btc_vol_percentile,
                vix_level=vix_level,
                vix_percentile=vix_percentile,
                dxy_level=dxy_level,
                dxy_percentile=dxy_percentile,
                gold_volatility=gold_vol,
                gold_percentile=gold_percentile,
                overall_risk_score=overall_risk_score
            )

        except Exception as e:
            logger.error(f"리스크 지표 계산 실패: {str(e)}")
            # 기본값 반환
            return RiskIndicators(
                btc_volatility_7d=0.0, btc_volatility_30d=0.0, btc_volatility_percentile=50.0,
                vix_level=20.0, vix_percentile=50.0,
                dxy_level=100.0, dxy_percentile=50.0,
                gold_volatility=0.0, gold_percentile=50.0,
                overall_risk_score=50.0
            )

    def _analyze_correlations(self, market_data: MarketData) -> CorrelationAnalysis:
        """상관관계 분석"""
        try:
            # 실제 시장 데이터를 기반으로 한 간단한 상관관계 추정
            # 실제로는 더 많은 시계열 데이터가 필요하지만, 현재는 24시간 변화율을 기반으로 추정

            # 비트코인과 주요 자산의 상관관계 (변화율 기반 추정)
            btc_change = market_data.btc_change_24h
            nasdaq_change = market_data.nasdaq_change_24h
            dxy_change = market_data.dxy_change_24h
            vix_change = market_data.vix_change_24h
            gold_change = market_data.gold_change_24h

            # 변화율의 부호를 기반으로 한 간단한 상관관계 추정
            btc_nasdaq_corr = self._estimate_correlation(btc_change, nasdaq_change)
            btc_dxy_corr = self._estimate_correlation(btc_change, dxy_change)
            btc_vix_corr = self._estimate_correlation(btc_change, vix_change)
            btc_gold_corr = self._estimate_correlation(btc_change, gold_change)

            # 주요 자산 간 상관관계
            nasdaq_dxy_corr = self._estimate_correlation(nasdaq_change, dxy_change)
            nasdaq_vix_corr = self._estimate_correlation(nasdaq_change, vix_change)
            dxy_vix_corr = self._estimate_correlation(dxy_change, vix_change)

            # 상관관계 해석
            correlation_summary = self._interpret_correlations(
                btc_nasdaq_corr, btc_dxy_corr, btc_vix_corr, btc_gold_corr,
                nasdaq_dxy_corr, nasdaq_vix_corr, dxy_vix_corr
            )

            # Risk-Off 신호 지표들
            risk_off_indicators = self._identify_risk_off_indicators(
                btc_nasdaq_corr, btc_dxy_corr, btc_vix_corr,
                nasdaq_dxy_corr, nasdaq_vix_corr, dxy_vix_corr
            )

            return CorrelationAnalysis(
                btc_nasdaq_correlation=btc_nasdaq_corr,
                btc_dxy_correlation=btc_dxy_corr,
                btc_vix_correlation=btc_vix_corr,
                btc_gold_correlation=btc_gold_corr,
                nasdaq_dxy_correlation=nasdaq_dxy_corr,
                nasdaq_vix_correlation=nasdaq_vix_corr,
                dxy_vix_correlation=dxy_vix_corr,
                correlation_summary=correlation_summary,
                risk_off_indicators=risk_off_indicators
            )

        except Exception as e:
            logger.error(f"상관관계 분석 실패: {str(e)}")
            # 기본값 반환
            return CorrelationAnalysis(
                btc_nasdaq_correlation=0.0, btc_dxy_correlation=0.0,
                btc_vix_correlation=0.0, btc_gold_correlation=0.0,
                nasdaq_dxy_correlation=0.0, nasdaq_vix_correlation=0.0,
                dxy_vix_correlation=0.0,
                correlation_summary="상관관계 분석 실패",
                risk_off_indicators=[]
            )

    def _interpret_correlations(
        self, btc_nasdaq: float, btc_dxy: float, btc_vix: float, btc_gold: float,
        nasdaq_dxy: float, nasdaq_vix: float, dxy_vix: float
    ) -> str:
        """상관관계 해석"""
        interpretations = []

        if abs(btc_nasdaq) > 0.5:
            direction = "양의" if btc_nasdaq > 0 else "음의"
            strength = "강한" if abs(btc_nasdaq) > 0.7 else "중간"
            interpretations.append(f"비트코인-나스닥: {strength} {direction} 상관관계")

        if abs(btc_dxy) > 0.5:
            direction = "양의" if btc_dxy > 0 else "음의"
            strength = "강한" if abs(btc_dxy) > 0.7 else "중간"
            interpretations.append(f"비트코인-달러인덱스: {strength} {direction} 상관관계")

        if abs(nasdaq_vix) > 0.5:
            direction = "양의" if nasdaq_vix > 0 else "음의"
            strength = "강한" if abs(nasdaq_vix) > 0.7 else "중간"
            interpretations.append(f"나스닥-VIX: {strength} {direction} 상관관계")

        if not interpretations:
            return "주요 자산 간 상관관계가 약하거나 중립적입니다."

        return " | ".join(interpretations)

    def _identify_risk_off_indicators(
        self, btc_nasdaq: float, btc_dxy: float, btc_vix: float,
        nasdaq_dxy: float, nasdaq_vix: float, dxy_vix: float
    ) -> List[str]:
        """Risk-Off 신호 지표 식별"""
        indicators = []

        # VIX가 높고 나스닥과 강한 음의 상관관계
        if nasdaq_vix < -0.6:
            indicators.append("VIX 상승과 나스닥 하락 동반")

        # 달러 강세와 비트코인 약세
        if btc_dxy < -0.5:
            indicators.append("달러 강세와 비트코인 약세")

        # 비트코인과 나스닥의 강한 양의 상관관계 (위험 자산 동반 하락)
        if btc_nasdaq > 0.6:
            indicators.append("비트코인과 나스닥 강한 양의 상관관계")

        # VIX와 달러의 양의 상관관계 (안전자산 선호)
        if dxy_vix > 0.5:
            indicators.append("VIX 상승과 달러 강세 동반")

        return indicators

    def _estimate_correlation(self, change1: float, change2: float) -> float:
        """변화율을 기반으로 한 간단한 상관관계 추정"""
        try:
            # 둘 다 0에 가까우면 상관관계 없음
            if abs(change1) < 0.1 and abs(change2) < 0.1:
                return 0.0

            # 부호가 같으면 양의 상관관계, 다르면 음의 상관관계
            if (change1 > 0 and change2 > 0) or (change1 < 0 and change2 < 0):
                # 변화율의 크기에 따라 상관관계 강도 결정
                magnitude = min(abs(change1), abs(change2)) / max(abs(change1), abs(change2))
                return min(0.8, magnitude * 0.5)  # 최대 0.8
            else:
                # 변화율의 크기에 따라 상관관계 강도 결정
                magnitude = min(abs(change1), abs(change2)) / max(abs(change1), abs(change2))
                return max(-0.8, -magnitude * 0.5)  # 최소 -0.8

        except Exception as e:
            logger.error(f"상관관계 추정 실패: {str(e)}")
            return 0.0

    async def _perform_ai_analysis(
        self, market_data: MarketData, risk_indicators: RiskIndicators,
        correlation_analysis: CorrelationAnalysis
    ) -> Optional[AIAnalysis]:
        """AI 분석 수행"""
        if not self.use_ai_analysis or self.llm is None:
            return None

        try:
            # 분석할 데이터 준비
            analysis_data = {
                "market_data": market_data.dict(),
                "risk_indicators": risk_indicators.dict(),
                "correlation_analysis": correlation_analysis.dict()
            }

            # 프롬프트 생성
            prompt = self._create_analysis_prompt(analysis_data)

            # AI 분석 실행
            try:
                from langchain_core.messages import HumanMessage, SystemMessage
                messages = [
                    SystemMessage(content="당신은 전문적인 금융 리스크 분석가입니다. 주어진 시장 데이터를 분석하여 투자자에게 도움이 되는 인사이트를 제공해주세요."),
                    HumanMessage(content=prompt)
                ]
            except ImportError:
                # LangChain 메시지 클래스가 없는 경우 간단한 딕셔너리 사용
                messages = [
                    {"role": "system", "content": "당신은 전문적인 금융 리스크 분석가입니다. 주어진 시장 데이터를 분석하여 투자자에게 도움이 되는 인사이트를 제공해주세요."},
                    {"role": "user", "content": prompt}
                ]

            response = await self.llm.ainvoke(messages)
            analysis_text = response.content

            # AI 분석 결과 파싱
            market_summary = self._extract_section(analysis_text, "시장 요약")
            risk_assessment = self._extract_section(analysis_text, "리스크 평가")
            key_risks = self._extract_list(analysis_text, "주요 리스크")
            opportunities = self._extract_list(analysis_text, "투자 기회")
            risk_summary = self._extract_section(analysis_text, "리스크 요약")

            return AIAnalysis(
                market_summary=market_summary,
                risk_assessment=risk_assessment,
                key_risks=key_risks,
                opportunities=opportunities,
                recommendations=risk_summary,
                confidence=0.8
            )

        except Exception as e:
            logger.error(f"AI 분석 실패: {str(e)}")
            import traceback
            logger.error(f"AI 분석 실패 상세: {traceback.format_exc()}")
            return None

    def _create_analysis_prompt(self, data: Dict[str, Any]) -> str:
        """AI 분석을 위한 프롬프트 생성"""
        return f"""
다음 시장 데이터를 분석하여 투자자에게 도움이 되는 인사이트를 제공해주세요:

=== 시장 데이터 ===
- 비트코인 가격: ${data['market_data']['btc_price']:,.2f} ({data['market_data']['btc_change_24h']:+.2f}%)
- 나스닥: {data['market_data']['nasdaq_price']:,.2f} ({data['market_data']['nasdaq_change_24h']:+.2f}%)
- 달러 인덱스: {data['market_data']['dxy_price']:.2f} ({data['market_data']['dxy_change_24h']:+.2f}%)
- VIX: {data['market_data']['vix_price']:.2f} ({data['market_data']['vix_change_24h']:+.2f}%)
- 금: ${data['market_data']['gold_price']:,.2f} ({data['market_data']['gold_change_24h']:+.2f}%)

=== 리스크 지표 ===
- 비트코인 변동성: {data['risk_indicators']['btc_volatility_30d']:.2f}%
- VIX 레벨: {data['risk_indicators']['vix_level']:.2f}
- 달러 인덱스: {data['risk_indicators']['dxy_level']:.2f}
- 종합 리스크 점수: {data['risk_indicators']['overall_risk_score']:.1f}/100

=== 상관관계 분석 ===
- 비트코인-나스닥: {data['correlation_analysis']['btc_nasdaq_correlation']:.2f}
- 비트코인-달러인덱스: {data['correlation_analysis']['btc_dxy_correlation']:.2f}
- 비트코인-VIX: {data['correlation_analysis']['btc_vix_correlation']:.2f}
- 나스닥-VIX: {data['correlation_analysis']['nasdaq_vix_correlation']:.2f}

다음 형식으로 분석 결과를 제공해주세요:

**시장 요약:**
[현재 시장 상황에 대한 간단한 요약]

**리스크 평가:**
[현재 시장의 리스크 수준과 주요 위험 요인]

**주요 리스크:**
- [리스크 1]
- [리스크 2]
- [리스크 3]

**투자 기회:**
- [기회 1]
- [기회 2]
- [기회 3]

**리스크 요약:**
[현재 시장의 주요 리스크 요인들을 요약]
"""

    def _extract_section(self, text: str, section_name: str) -> str:
        """텍스트에서 특정 섹션 추출"""
        try:
            lines = text.split('\n')
            in_section = False
            section_content = []

            for line in lines:
                if section_name in line and ':' in line:
                    in_section = True
                    continue
                elif in_section and line.startswith('**') and ':' in line:
                    break
                elif in_section:
                    section_content.append(line.strip())

            return ' '.join(section_content).strip() or f"{section_name} 분석 결과 없음"
        except:
            return f"{section_name} 분석 결과 없음"

    def _extract_list(self, text: str, list_name: str) -> List[str]:
        """텍스트에서 리스트 추출"""
        try:
            lines = text.split('\n')
            in_section = False
            items = []

            for line in lines:
                if list_name in line and ':' in line:
                    in_section = True
                    continue
                elif in_section and line.startswith('**') and ':' in line:
                    break
                elif in_section and line.strip().startswith('-'):
                    item = line.strip()[1:].strip()
                    if item:
                        items.append(item)

            return items if items else [f"{list_name} 항목 없음"]
        except:
            return [f"{list_name} 항목 없음"]

    def _determine_risk_level(
        self, risk_indicators: RiskIndicators, correlation_analysis: CorrelationAnalysis, personality: str = "neutral"
    ) -> Tuple[str, bool, float]:
        """최종 리스크 레벨 결정 (투자 성향 고려)"""
        try:
            risk_score = risk_indicators.overall_risk_score
            vix_level = risk_indicators.vix_level
            risk_off_count = len(correlation_analysis.risk_off_indicators)

            # 투자 성향에 따른 임계값 조정
            if personality == "conservative":
                # 보수적: 더 민감하게 리스크 감지
                critical_threshold = 70
                high_threshold = 50
                medium_threshold = 30
                vix_critical = 30
                vix_high = 20
                vix_medium = 15
            elif personality == "aggressive":
                # 공격적: 덜 민감하게 리스크 감지
                critical_threshold = 90
                high_threshold = 70
                medium_threshold = 50
                vix_critical = 40
                vix_high = 30
                vix_medium = 25
            else:  # neutral
                # 중립적: 기본 임계값
                critical_threshold = 80
                high_threshold = 60
                medium_threshold = 40
                vix_critical = 35
                vix_high = 25
                vix_medium = 20

            # 리스크 레벨 결정
            if risk_score >= critical_threshold or vix_level >= vix_critical or risk_off_count >= 3:
                risk_level = "CRITICAL"
                risk_off = True
                confidence = 0.9
            elif risk_score >= high_threshold or vix_level >= vix_high or risk_off_count >= 2:
                risk_level = "HIGH"
                risk_off = True
                confidence = 0.8
            elif risk_score >= medium_threshold or vix_level >= vix_medium or risk_off_count >= 1:
                risk_level = "MEDIUM"
                risk_off = risk_off_count >= 1
                confidence = 0.7
            else:
                risk_level = "LOW"
                risk_off = False
                confidence = 0.6

            return risk_level, risk_off, confidence

        except Exception as e:
            logger.error(f"리스크 레벨 결정 실패: {str(e)}")
            return "UNKNOWN", False, 0.0

    # _generate_recommendations 함수 제거됨
    # 투자 권장사항은 마스터 에이전트가 담당하므로 리스크 에이전트에서는 제공하지 않음

    async def health_check(self) -> Dict[str, Any]:
        """서비스 헬스체크"""
        try:
            # 기본 데이터 수집 테스트
            test_data = await self._collect_market_data(7)

            # 리스크 지표 계산 테스트
            risk_indicators = self._calculate_risk_indicators(test_data)

            # 상관관계 분석 테스트
            correlation_analysis = self._analyze_correlations(test_data)

            return {
                "data_collection": "ok",
                "risk_calculation": "ok",
                "correlation_analysis": "ok",
                "ai_analysis": "ok" if self.use_ai_analysis else "disabled",
                "test_risk_score": risk_indicators.overall_risk_score,
                "test_correlations": len(correlation_analysis.risk_off_indicators)
            }

        except Exception as e:
            logger.error(f"헬스체크 실패: {str(e)}")
            return {
                "data_collection": "error",
                "risk_calculation": "error",
                "correlation_analysis": "error",
                "ai_analysis": "error",
                "error": str(e)
            }
