"""
오프체인 분석 서비스 V2
- 뉴스, 소셜미디어, 거시경제 지표를 통합 분석
- PRD 기준 가중치 적용 (뉴스 40%, 소셜 35%, 거시경제 25%)
"""

import asyncio
import aiohttp
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import numpy as np

from src.common.utils.offchain_indicators_v2 import (
    OffchainIndicatorsV2, NewsItem, SocialSentiment, MacroIndicator
)
from src.common.utils.social_data_sources import SocialDataAggregator
from src.common.utils.logger import set_logger
from .models import OffchainRequest, OffchainResponse

logger = set_logger("offchain_service_v2")

class OffchainServiceV2:
    """오프체인 분석 서비스 V2"""

    def __init__(self):
        self.offchain_analyzer = OffchainIndicatorsV2()
        self.session = None

        # 소셜미디어 데이터 수집기 초기화
        # 환경변수에서 API 키를 가져오거나 기본값 사용
        reddit_config: Optional[Dict[str, str]] = None
        twitter_config: Optional[Dict[str, str]] = None

        # Reddit API 설정
        reddit_client_id = os.getenv('REDDIT_CLIENT_ID')
        reddit_client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        reddit_user_agent = os.getenv('REDDIT_USER_AGENT', 'QuantumInsight/1.0 by YourUsername')

        if reddit_client_id and reddit_client_secret:
            reddit_config = {
                'client_id': reddit_client_id,
                'client_secret': reddit_client_secret,
                'user_agent': reddit_user_agent
            }
            logger.info("✅ Reddit API 설정 완료")
        else:
            logger.warning("⚠️ Reddit API 설정 없음 - 환경변수 확인 필요")

        # Twitter API 설정
        twitter_bearer_token = os.getenv('TWITTER_BEARER_TOKEN')

        if twitter_bearer_token:
            twitter_config = {
                'bearer_token': twitter_bearer_token
            }
            logger.info("✅ Twitter API 설정 완료")
        else:
            logger.warning("⚠️ Twitter API 설정 없음 - 환경변수 확인 필요")

        self.social_aggregator = SocialDataAggregator(
            reddit_config=reddit_config,
            twitter_config=twitter_config
        )

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def analyze_offchain_sentiment(
        self,
        market: str = "BTC/USDT",
        timeframe: str = "minutes:60",
        count: int = 200
    ) -> Dict[str, Any]:
        """오프체인 센티멘트 분석"""
        try:
            logger.info("🚀 [2단계] 오프체인 센티멘트 분석 시작")
            logger.info(f"📊 {market} | {timeframe} | {count}개 캔들")

            # 1. 뉴스 데이터 수집
            try:
                news_items = await self._collect_news_data()
                logger.info(f"✅ 뉴스 데이터: {len(news_items)}개")
            except Exception as e:
                logger.warning(f"뉴스 데이터 수집 실패: {str(e)}")
                news_items = []

            # 2. 소셜미디어 데이터 수집
            try:
                social_data = await self._collect_social_data()
                logger.info(f"✅ 소셜미디어 데이터: {len(social_data)}개")
            except Exception as e:
                logger.warning(f"소셜미디어 데이터 수집 실패: {str(e)}")
                social_data = []

            # 3. 거시경제 데이터 수집
            try:
                macro_data = await self._collect_macro_data()
                logger.info(f"✅ 거시경제 데이터: {len(macro_data)}개")
            except Exception as e:
                logger.warning(f"거시경제 데이터 수집 실패: {str(e)}")
                macro_data = []

            # 4. 통합 분석
            try:
                analysis_result = await self.offchain_analyzer.analyze_offchain_sentiment(
                    news_items, social_data, macro_data
                )
            except Exception as e:
                logger.error(f"통합 분석 실패: {str(e)}")
                # 기본 분석 결과 생성
                analysis_result = {
                    "offchain_score": 0.0,
                    "signal": "HOLD",
                    "signal_description": "🟡 분석 실패",
                    "confidence": 0.0,
                    "news_analysis": {"analysis": "뉴스 분석 실패", "news_count": 0},
                    "social_analysis": {"analysis": "소셜 분석 실패", "platform_count": 0, "total_mentions": 0},
                    "macro_analysis": {"analysis": "거시경제 분석 실패", "indicator_count": 0},
                    "weights": {"news": 0.4, "social": 0.35, "macro": 0.25}
                }

            # 5. 결과 구조화
            try:
                result = self._structure_analysis_result(
                    market, timeframe, analysis_result
                )
            except Exception as e:
                logger.error(f"결과 구조화 실패: {str(e)}")
                result = self._create_error_response(market, timeframe, str(e))

            logger.info("🎉 [2단계] 오프체인 센티멘트 분석 완료!")
            logger.info(f"📊 결과: {analysis_result['signal_description']} | 점수: {analysis_result['offchain_score']:.3f}")

            return result

        except Exception as e:
            logger.error(f"오프체인 센티멘트 분석 실패: {str(e)}")
            import traceback
            traceback.print_exc()
            return self._create_error_response(market, timeframe, str(e))

    async def _collect_news_data(self) -> List[NewsItem]:
        """뉴스 데이터 수집 (모의 데이터)"""
        try:
            # 실제 구현에서는 NewsAPI, GDELT, RSS 피드 등을 사용
            # 현재는 모의 데이터로 구현

            mock_news = [
                NewsItem(
                    title="Bitcoin ETF Approval Expected This Week",
                    source="Reuters",
                    published_at=datetime.now() - timedelta(hours=2),
                    sentiment_score=0.7,
                    relevance_score=0.9,
                    url="https://reuters.com/bitcoin-etf"
                ),
                NewsItem(
                    title="Crypto Regulation Concerns Rise in Europe",
                    source="Bloomberg",
                    published_at=datetime.now() - timedelta(hours=4),
                    sentiment_score=-0.3,
                    relevance_score=0.8,
                    url="https://bloomberg.com/crypto-regulation"
                ),
                NewsItem(
                    title="Major Bank Announces Bitcoin Custody Services",
                    source="WSJ",
                    published_at=datetime.now() - timedelta(hours=6),
                    sentiment_score=0.5,
                    relevance_score=0.7,
                    url="https://wsj.com/bitcoin-custody"
                ),
                NewsItem(
                    title="Bitcoin Mining Difficulty Reaches New High",
                    source="CoinDesk",
                    published_at=datetime.now() - timedelta(hours=8),
                    sentiment_score=0.2,
                    relevance_score=0.6,
                    url="https://coindesk.com/mining-difficulty"
                )
            ]

            return mock_news

        except Exception as e:
            logger.error(f"뉴스 데이터 수집 실패: {str(e)}")
            return []

    async def _collect_social_data(self) -> List[SocialSentiment]:
        """소셜미디어 데이터 수집 (실제 Reddit & Twitter API)"""
        try:
            # 실제 Reddit과 Twitter API를 통한 데이터 수집
            social_mentions = await self.social_aggregator.collect_social_mentions(
                reddit_limit=50,
                twitter_limit=50,
                hours_back=24
            )

            # SocialSentiment 형식으로 변환
            social_data = []

            # 플랫폼별로 그룹화
            reddit_mentions = [m for m in social_mentions if m.platform == 'reddit']
            twitter_mentions = [m for m in social_mentions if m.platform == 'twitter']

            # Reddit 데이터 처리
            if reddit_mentions:
                try:
                    reddit_analysis = self.social_aggregator.calculate_platform_sentiment(reddit_mentions, 'reddit')
                    social_data.append(SocialSentiment(
                        platform="reddit",
                        mention_count=reddit_analysis['mention_count'],
                        sentiment_score=reddit_analysis['sentiment_score'],
                        trend_score=reddit_analysis['trend_score'],
                        timestamp=datetime.now() - timedelta(hours=1)
                    ))
                except Exception as e:
                    logger.warning(f"Reddit 분석 실패: {str(e)}")

            # Twitter 데이터 처리
            if twitter_mentions:
                try:
                    twitter_analysis = self.social_aggregator.calculate_platform_sentiment(twitter_mentions, 'twitter')
                    social_data.append(SocialSentiment(
                        platform="twitter",
                        mention_count=twitter_analysis['mention_count'],
                        sentiment_score=twitter_analysis['sentiment_score'],
                        trend_score=twitter_analysis['trend_score'],
                        timestamp=datetime.now() - timedelta(hours=1)
                    ))
                except Exception as e:
                    logger.warning(f"Twitter 분석 실패: {str(e)}")

            # API 실패 시 모의 데이터 사용
            if not social_data:
                logger.warning("소셜미디어 API 실패, 모의 데이터 사용")
                social_data = [
                    SocialSentiment(
                        platform="reddit",
                        mention_count=890,
                        sentiment_score=0.2,
                        trend_score=0.4,
                        timestamp=datetime.now() - timedelta(hours=2)
                    ),
                    SocialSentiment(
                        platform="twitter",
                        mention_count=1250,
                        sentiment_score=0.4,
                        trend_score=0.6,
                        timestamp=datetime.now() - timedelta(hours=1)
                    )
                ]

            return social_data

        except Exception as e:
            logger.error(f"소셜미디어 데이터 수집 실패: {str(e)}")
            # 에러 시 모의 데이터 반환
            return [
                SocialSentiment(
                    platform="reddit",
                    mention_count=890,
                    sentiment_score=0.2,
                    trend_score=0.4,
                    timestamp=datetime.now() - timedelta(hours=2)
                ),
                SocialSentiment(
                    platform="twitter",
                    mention_count=1250,
                    sentiment_score=0.4,
                    trend_score=0.6,
                    timestamp=datetime.now() - timedelta(hours=1)
                )
            ]

    async def _collect_macro_data(self) -> List[MacroIndicator]:
        """거시경제 데이터 수집 (모의 데이터)"""
        try:
            # 실제 구현에서는 FRED API, Yahoo Finance, Investing.com 등을 사용
            # 현재는 모의 데이터로 구현

            mock_macro = [
                MacroIndicator(
                    indicator="cpi",
                    value=3.2,
                    previous_value=3.1,
                    change_pct=0.1,
                    impact_score=0.2,
                    timestamp=datetime.now() - timedelta(days=1)
                ),
                MacroIndicator(
                    indicator="interest_rate",
                    value=5.25,
                    previous_value=5.0,
                    change_pct=0.25,
                    impact_score=-0.3,
                    timestamp=datetime.now() - timedelta(days=2)
                ),
                MacroIndicator(
                    indicator="dxy",
                    value=103.5,
                    previous_value=104.2,
                    change_pct=-0.7,
                    impact_score=0.1,
                    timestamp=datetime.now() - timedelta(days=3)
                ),
                MacroIndicator(
                    indicator="unemployment",
                    value=3.8,
                    previous_value=3.9,
                    change_pct=-0.1,
                    impact_score=0.1,
                    timestamp=datetime.now() - timedelta(days=4)
                )
            ]

            return mock_macro

        except Exception as e:
            logger.error(f"거시경제 데이터 수집 실패: {str(e)}")
            return []

    def _structure_analysis_result(
        self,
        market: str,
        timeframe: str,
        analysis_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """분석 결과 구조화"""
        try:
            # 인간 친화적 분석 결과
            analysis = {
                "overall_sentiment": {
                    "signal": analysis_result['signal_description'],
                    "score": f"{analysis_result['offchain_score']:.3f}",
                    "confidence": f"{analysis_result['confidence']:.1%}",
                    "interpretation": self._get_sentiment_interpretation(analysis_result['offchain_score'])
                },
                "news_analysis": {
                    "sentiment": analysis_result['news_analysis']['analysis'],
                    "news_count": analysis_result['news_analysis']['news_count'],
                    "positive_news": analysis_result['news_analysis']['positive_news'],
                    "negative_news": analysis_result['news_analysis']['negative_news'],
                    "neutral_news": analysis_result['news_analysis']['neutral_news']
                },
                "social_analysis": {
                    "sentiment": analysis_result['social_analysis']['analysis'],
                    "platform_count": analysis_result['social_analysis']['platform_count'],
                    "total_mentions": analysis_result['social_analysis']['total_mentions'],
                    "trend_score": f"{analysis_result['social_analysis']['trend_score']:.2f}"
                },
                "macro_analysis": {
                    "impact": analysis_result['macro_analysis']['analysis'],
                    "indicator_count": analysis_result['macro_analysis']['indicator_count'],
                    "overall_impact": f"{analysis_result['macro_analysis']['overall_impact']:.3f}"
                },
                "weight_distribution": {
                    "news_weight": f"{analysis_result['weights']['news']:.0%}",
                    "social_weight": f"{analysis_result['weights']['social']:.0%}",
                    "macro_weight": f"{analysis_result['weights']['macro']:.0%}"
                }
            }

            # 상세 데이터 (AI/시스템용)
            detailed_data = {
                "offchain_score": analysis_result['offchain_score'],
                "signal": analysis_result['signal'],
                "confidence": analysis_result['confidence'],
                "news_analysis": analysis_result['news_analysis'],
                "social_analysis": analysis_result['social_analysis'],
                "macro_analysis": analysis_result['macro_analysis'],
                "weights": analysis_result['weights']
            }

            return {
                "status": "success",
                "market": market,
                "timeframe": timeframe,
                "timestamp": datetime.now().isoformat(),
                "analysis": analysis,
                "detailed_data": detailed_data,
                "metadata": {
                    "data_sources": ["news", "social", "macro"],
                    "analysis_type": "offchain_sentiment",
                    "version": "v2"
                }
            }

        except Exception as e:
            logger.error(f"분석 결과 구조화 실패: {str(e)}")
            return self._create_error_response(market, timeframe, str(e))

    def _get_sentiment_interpretation(self, score: float) -> str:
        """센티멘트 점수 해석"""
        if score >= 0.6:
            return "매우 강한 긍정적 신호"
        elif score >= 0.3:
            return "강한 긍정적 신호"
        elif score >= 0.1:
            return "약한 긍정적 신호"
        elif score >= -0.1:
            return "중립적 신호"
        elif score >= -0.3:
            return "약한 부정적 신호"
        elif score >= -0.6:
            return "강한 부정적 신호"
        else:
            return "매우 강한 부정적 신호"

    def _create_error_response(self, market: str, timeframe: str, error_msg: str) -> Dict[str, Any]:
        """에러 응답 생성"""
        return {
            "status": "error",
            "market": market,
            "timeframe": timeframe,
            "timestamp": datetime.now().isoformat(),
            "error": error_msg,
            "analysis": {
                "overall_sentiment": {
                    "signal": "🟡 분석 실패",
                    "score": "0.000",
                    "confidence": "0.0%",
                    "interpretation": "데이터 수집 또는 분석 중 오류 발생"
                }
            },
            "detailed_data": {
                "offchain_score": 0.0,
                "signal": "HOLD",
                "confidence": 0.0
            },
            "metadata": {
                "error": True,
                "error_message": error_msg
            }
        }
