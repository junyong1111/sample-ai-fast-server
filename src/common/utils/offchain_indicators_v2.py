"""
오프체인 지표 분석 모듈 V2
- 뉴스 헤드라인 분석 (Reuters, Bloomberg, WSJ, FT, CoinDesk 등)
- 소셜미디어 센티멘트 분석 (Twitter, Reddit, Google Trends)
- 거시경제 지표 분석 (CPI, PPI, 금리, DXY)
"""

import asyncio
import aiohttp
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass

from src.common.utils.logger import set_logger

logger = set_logger("offchain_indicators_v2")

@dataclass
class NewsItem:
    """뉴스 아이템 데이터 클래스"""
    title: str
    source: str
    published_at: datetime
    sentiment_score: float
    relevance_score: float
    url: str = ""

@dataclass
class SocialSentiment:
    """소셜미디어 센티멘트 데이터 클래스"""
    platform: str
    mention_count: int
    sentiment_score: float
    trend_score: float
    timestamp: datetime

@dataclass
class MacroIndicator:
    """거시경제 지표 데이터 클래스"""
    indicator: str
    value: float
    previous_value: float
    change_pct: float
    impact_score: float
    timestamp: datetime

class NewsAnalyzer:
    """뉴스 헤드라인 분석기"""

    def __init__(self):
        self.crypto_keywords = [
            'bitcoin', 'btc', 'cryptocurrency', 'crypto', 'blockchain',
            'ethereum', 'eth', 'altcoin', 'defi', 'nft', 'web3',
            'binance', 'coinbase', 'kraken', 'exchange', 'trading',
            'regulation', 'sec', 'cftc', 'fed', 'central bank',
            'etf', 'institutional', 'adoption', 'mining', 'hashrate'
        ]

        self.positive_keywords = [
            'approve', 'adoption', 'institutional', 'bullish', 'surge',
            'rally', 'breakthrough', 'innovation', 'partnership', 'investment',
            'positive', 'growth', 'expansion', 'success', 'milestone',
            'record', 'high', 'gain', 'profit', 'benefit'
        ]

        self.negative_keywords = [
            'ban', 'regulation', 'crackdown', 'fraud', 'scam', 'hack',
            'crash', 'bearish', 'decline', 'loss', 'risk', 'volatility',
            'uncertainty', 'fear', 'panic', 'sell', 'dump', 'correction',
            'bubble', 'overvalued', 'warning', 'concern', 'threat'
        ]

    async def analyze_news_sentiment(self, news_items: List[NewsItem]) -> Dict[str, Any]:
        """뉴스 센티멘트 분석"""
        try:
            if not news_items:
                return {
                    "overall_sentiment": 0.0,
                    "sentiment_score": 0.0,
                    "relevance_score": 0.0,
                    "news_count": 0,
                    "positive_news": 0,
                    "negative_news": 0,
                    "neutral_news": 0,
                    "analysis": "뉴스 데이터 없음"
                }

            total_sentiment = 0.0
            total_relevance = 0.0
            positive_count = 0
            negative_count = 0
            neutral_count = 0

            for item in news_items:
                # 센티멘트 점수 누적
                total_sentiment += item.sentiment_score
                total_relevance += item.relevance_score

                # 센티멘트 분류
                if item.sentiment_score > 0.1:
                    positive_count += 1
                elif item.sentiment_score < -0.1:
                    negative_count += 1
                else:
                    neutral_count += 1

            # 평균 계산
            avg_sentiment = total_sentiment / len(news_items)
            avg_relevance = total_relevance / len(news_items)

            # 전체 센티멘트 점수 (-1 ~ +1)
            overall_sentiment = np.clip(avg_sentiment, -1.0, 1.0)

            # 분석 결과
            if overall_sentiment > 0.3:
                analysis = f"🟢 긍정적 뉴스 우세 ({positive_count}개 긍정, {negative_count}개 부정)"
            elif overall_sentiment < -0.3:
                analysis = f"🔴 부정적 뉴스 우세 ({positive_count}개 긍정, {negative_count}개 부정)"
            else:
                analysis = f"🟡 중립적 뉴스 ({positive_count}개 긍정, {negative_count}개 부정, {neutral_count}개 중립)"

            return {
                "overall_sentiment": overall_sentiment,
                "sentiment_score": overall_sentiment,
                "relevance_score": avg_relevance,
                "news_count": len(news_items),
                "positive_news": positive_count,
                "negative_news": negative_count,
                "neutral_news": neutral_count,
                "analysis": analysis
            }

        except Exception as e:
            logger.error(f"뉴스 센티멘트 분석 실패: {str(e)}")
            return {
                "overall_sentiment": 0.0,
                "sentiment_score": 0.0,
                "relevance_score": 0.0,
                "news_count": 0,
                "positive_news": 0,
                "negative_news": 0,
                "neutral_news": 0,
                "analysis": "뉴스 분석 실패"
            }

    def calculate_sentiment_score(self, title: str, content: str = "") -> float:
        """제목과 내용을 기반으로 센티멘트 점수 계산 (-1 ~ +1)"""
        try:
            text = (title + " " + content).lower()

            positive_count = sum(1 for keyword in self.positive_keywords if keyword in text)
            negative_count = sum(1 for keyword in self.negative_keywords if keyword in text)

            # 키워드 기반 점수 계산
            if positive_count + negative_count == 0:
                return 0.0

            sentiment_ratio = (positive_count - negative_count) / (positive_count + negative_count)
            return np.clip(sentiment_ratio, -1.0, 1.0)

        except Exception as e:
            logger.error(f"센티멘트 점수 계산 실패: {str(e)}")
            return 0.0

    def calculate_relevance_score(self, title: str, content: str = "") -> float:
        """크립토 관련성 점수 계산 (0 ~ 1)"""
        try:
            text = (title + " " + content).lower()

            # 크립토 키워드 매칭
            keyword_matches = sum(1 for keyword in self.crypto_keywords if keyword in text)

            # 관련성 점수 (0 ~ 1)
            relevance = min(keyword_matches / 5.0, 1.0)  # 최대 5개 키워드까지
            return relevance

        except Exception as e:
            logger.error(f"관련성 점수 계산 실패: {str(e)}")
            return 0.0

class SocialSentimentAnalyzer:
    """소셜미디어 센티멘트 분석기"""

    def __init__(self):
        self.platforms = ['twitter', 'reddit', 'telegram', 'youtube', 'google_trends']

    async def analyze_social_sentiment(self, social_data: List[SocialSentiment]) -> Dict[str, Any]:
        """소셜미디어 센티멘트 분석"""
        try:
            if not social_data:
                return {
                    "overall_sentiment": 0.0,
                    "sentiment_score": 0.0,
                    "trend_score": 0.0,
                    "platform_count": 0,
                    "total_mentions": 0,
                    "analysis": "소셜미디어 데이터 없음"
                }

            # 플랫폼별 가중치
            platform_weights = {
                'twitter': 0.3,
                'reddit': 0.25,
                'telegram': 0.2,
                'youtube': 0.15,
                'google_trends': 0.1
            }

            weighted_sentiment = 0.0
            weighted_trend = 0.0
            total_weight = 0.0
            total_mentions = 0

            for item in social_data:
                weight = platform_weights.get(item.platform, 0.1)
                weighted_sentiment += item.sentiment_score * weight
                weighted_trend += item.trend_score * weight
                total_weight += weight
                total_mentions += item.mention_count

            # 평균 계산
            avg_sentiment = weighted_sentiment / total_weight if total_weight > 0 else 0.0
            avg_trend = weighted_trend / total_weight if total_weight > 0 else 0.0

            # 전체 센티멘트 점수 (-1 ~ +1)
            overall_sentiment = np.clip(avg_sentiment, -1.0, 1.0)

            # 분석 결과
            if overall_sentiment > 0.3:
                analysis = f"🟢 긍정적 소셜 센티멘트 (트렌드: {avg_trend:.2f})"
            elif overall_sentiment < -0.3:
                analysis = f"🔴 부정적 소셜 센티멘트 (트렌드: {avg_trend:.2f})"
            else:
                analysis = f"🟡 중립적 소셜 센티멘트 (트렌드: {avg_trend:.2f})"

            return {
                "overall_sentiment": overall_sentiment,
                "sentiment_score": overall_sentiment,
                "trend_score": avg_trend,
                "platform_count": len(social_data),
                "total_mentions": total_mentions,
                "analysis": analysis
            }

        except Exception as e:
            logger.error(f"소셜 센티멘트 분석 실패: {str(e)}")
            return {
                "overall_sentiment": 0.0,
                "sentiment_score": 0.0,
                "trend_score": 0.0,
                "platform_count": 0,
                "total_mentions": 0,
                "analysis": "소셜 분석 실패"
            }

class MacroEconomicAnalyzer:
    """거시경제 지표 분석기"""

    def __init__(self):
        self.indicators = {
            'cpi': {'weight': 0.3, 'impact_threshold': 0.1},
            'ppi': {'weight': 0.2, 'impact_threshold': 0.1},
            'interest_rate': {'weight': 0.25, 'impact_threshold': 0.05},
            'dxy': {'weight': 0.15, 'impact_threshold': 1.0},
            'unemployment': {'weight': 0.1, 'impact_threshold': 0.1}
        }

    async def analyze_macro_indicators(self, macro_data: List[MacroIndicator]) -> Dict[str, Any]:
        """거시경제 지표 분석"""
        try:
            if not macro_data:
                return {
                    "overall_impact": 0.0,
                    "impact_score": 0.0,
                    "indicator_count": 0,
                    "analysis": "거시경제 데이터 없음"
                }

            weighted_impact = 0.0
            total_weight = 0.0

            for item in macro_data:
                weight = self.indicators.get(item.indicator, {}).get('weight', 0.1)
                impact = item.impact_score * weight
                weighted_impact += impact
                total_weight += weight

            # 평균 임팩트 계산
            avg_impact = weighted_impact / total_weight if total_weight > 0 else 0.0

            # 전체 임팩트 점수 (-1 ~ +1)
            overall_impact = np.clip(avg_impact, -1.0, 1.0)

            # 분석 결과
            if overall_impact > 0.3:
                analysis = f"🟢 긍정적 거시경제 환경 (임팩트: {avg_impact:.2f})"
            elif overall_impact < -0.3:
                analysis = f"🔴 부정적 거시경제 환경 (임팩트: {avg_impact:.2f})"
            else:
                analysis = f"🟡 중립적 거시경제 환경 (임팩트: {avg_impact:.2f})"

            return {
                "overall_impact": overall_impact,
                "impact_score": overall_impact,
                "indicator_count": len(macro_data),
                "analysis": analysis
            }

        except Exception as e:
            logger.error(f"거시경제 지표 분석 실패: {str(e)}")
            return {
                "overall_impact": 0.0,
                "impact_score": 0.0,
                "indicator_count": 0,
                "analysis": "거시경제 분석 실패"
            }

class OffchainIndicatorsV2:
    """오프체인 지표 통합 분석기"""

    def __init__(self):
        self.news_analyzer = NewsAnalyzer()
        self.social_analyzer = SocialSentimentAnalyzer()
        self.macro_analyzer = MacroEconomicAnalyzer()

    async def analyze_offchain_sentiment(
        self,
        news_items: List[NewsItem] = None,
        social_data: List[SocialSentiment] = None,
        macro_data: List[MacroIndicator] = None
    ) -> Dict[str, Any]:
        """오프체인 센티멘트 통합 분석"""
        try:
            logger.info("🔍 [오프체인] 센티멘트 분석 시작")

            # 기본값 설정
            news_items = news_items or []
            social_data = social_data or []
            macro_data = macro_data or []

            # 각 모듈별 분석
            news_analysis = await self.news_analyzer.analyze_news_sentiment(news_items)
            social_analysis = await self.social_analyzer.analyze_social_sentiment(social_data)
            macro_analysis = await self.macro_analyzer.analyze_macro_indicators(macro_data)

            # 가중치 적용 (PRD 기준)
            news_weight = 0.4
            social_weight = 0.35
            macro_weight = 0.25

            # 최종 오프체인 점수 계산
            offchain_score = (
                news_analysis['sentiment_score'] * news_weight +
                social_analysis['sentiment_score'] * social_weight +
                macro_analysis['impact_score'] * macro_weight
            )

            # 점수 클리핑 (-1 ~ +1)
            offchain_score = np.clip(offchain_score, -1.0, 1.0)

            # 신호 해석
            if offchain_score >= 0.3:
                signal = "BUY"
                signal_desc = "🟢 긍정적 오프체인 신호"
            elif offchain_score <= -0.3:
                signal = "SELL"
                signal_desc = "🔴 부정적 오프체인 신호"
            else:
                signal = "HOLD"
                signal_desc = "🟡 중립적 오프체인 신호"

            logger.info(f"✅ [오프체인] 분석 완료: {signal_desc} (점수: {offchain_score:.3f})")

            return {
                "offchain_score": offchain_score,
                "signal": signal,
                "signal_description": signal_desc,
                "confidence": abs(offchain_score),
                "news_analysis": news_analysis,
                "social_analysis": social_analysis,
                "macro_analysis": macro_analysis,
                "weights": {
                    "news": news_weight,
                    "social": social_weight,
                    "macro": macro_weight
                }
            }

        except Exception as e:
            logger.error(f"오프체인 센티멘트 분석 실패: {str(e)}")
            return {
                "offchain_score": 0.0,
                "signal": "HOLD",
                "signal_description": "🟡 분석 실패",
                "confidence": 0.0,
                "news_analysis": {"analysis": "분석 실패"},
                "social_analysis": {"analysis": "분석 실패"},
                "macro_analysis": {"analysis": "분석 실패"},
                "weights": {"news": 0.4, "social": 0.35, "macro": 0.25}
            }
