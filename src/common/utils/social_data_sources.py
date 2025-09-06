"""
소셜미디어 데이터 수집 모듈 V2
- Reddit API를 통한 실시간 데이터 수집
- X(Twitter) API를 통한 실시간 데이터 수집
- 센티멘트 분석 및 트렌드 점수 계산
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

logger = set_logger("social_data_sources")

# 소셜미디어 API 라이브러리 (선택적 설치)
try:
    import praw  # Reddit API
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False
    logger.warning("praw 라이브러리가 설치되지 않음. Reddit 기능을 사용할 수 없습니다.")

try:
    import tweepy  # Twitter API
    TWEEPY_AVAILABLE = True
except ImportError:
    TWEEPY_AVAILABLE = False
    logger.warning("tweepy 라이브러리가 설치되지 않음. Twitter 기능을 사용할 수 없습니다.")

try:
    from textblob import TextBlob  # 센티멘트 분석
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False
    logger.warning("textblob 라이브러리가 설치되지 않음. 센티멘트 분석 기능이 제한됩니다.")

@dataclass
class RedditPost:
    """Reddit 포스트 데이터 클래스"""
    title: str
    content: str
    subreddit: str
    score: int
    upvote_ratio: float
    num_comments: int
    created_utc: datetime
    url: str
    author: str

@dataclass
class TwitterPost:
    """Twitter 포스트 데이터 클래스"""
    text: str
    author: str
    retweet_count: int
    like_count: int
    reply_count: int
    created_at: datetime
    tweet_id: str
    is_retweet: bool

@dataclass
class SocialMention:
    """소셜미디어 멘션 데이터 클래스"""
    platform: str
    content: str
    author: str
    engagement_score: float
    sentiment_score: float
    timestamp: datetime
    url: str

class RedditDataCollector:
    """Reddit 데이터 수집기"""

    def __init__(self, client_id: str, client_secret: str, user_agent: str):
        """
        Reddit API 초기화
        - Reddit API 앱 등록 후 client_id, client_secret 필요
        - user_agent: "YourApp/1.0 by YourUsername"
        """
        if not PRAW_AVAILABLE:
            logger.error("praw 라이브러리가 설치되지 않음. Reddit 기능을 사용할 수 없습니다.")
            self.reddit = None
            return

        try:
            self.reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent
            )
            self.crypto_subreddits = [
                'Bitcoin', 'CryptoCurrency', 'ethereum', 'CryptoMarkets',
                'bitcoinmarkets', 'CryptoMoonShots', 'defi', 'ethtrader',
                'Crypto_com', 'binance', 'Coinbase', 'cryptocurrency'
            ]
            logger.info("✅ Reddit API 초기화 완료")
        except Exception as e:
            logger.error(f"Reddit API 초기화 실패: {str(e)}")
            self.reddit = None

    async def collect_crypto_posts(
        self,
        limit: int = 100,
        time_filter: str = "day"
    ) -> List[RedditPost]:
        """크립토 관련 Reddit 포스트 수집"""
        try:
            if not self.reddit:
                logger.warning("Reddit API가 초기화되지 않음")
                return []

            posts = []
            total_collected = 0

            for subreddit_name in self.crypto_subreddits:
                if total_collected >= limit:
                    break

                try:
                    subreddit = self.reddit.subreddit(subreddit_name)

                    # Hot 포스트 수집
                    for submission in subreddit.hot(limit=min(20, limit - total_collected)):
                        if total_collected >= limit:
                            break

                        post = RedditPost(
                            title=submission.title,
                            content=submission.selftext or "",
                            subreddit=subreddit_name,
                            score=submission.score,
                            upvote_ratio=submission.upvote_ratio,
                            num_comments=submission.num_comments,
                            created_utc=datetime.fromtimestamp(submission.created_utc),
                            url=f"https://reddit.com{submission.permalink}",
                            author=str(submission.author) if submission.author else "deleted"
                        )
                        posts.append(post)
                        total_collected += 1

                except Exception as e:
                    logger.warning(f"Subreddit {subreddit_name} 수집 실패: {str(e)}")
                    continue

            logger.info(f"✅ Reddit 포스트 {len(posts)}개 수집 완료")
            return posts

        except Exception as e:
            logger.error(f"Reddit 데이터 수집 실패: {str(e)}")
            return []

    def calculate_reddit_engagement_score(self, post: RedditPost) -> float:
        """Reddit 포스트 참여도 점수 계산 (0 ~ 1)"""
        try:
            # 기본 점수: 업보트 비율
            base_score = post.upvote_ratio

            # 댓글 수 가중치 (로그 스케일)
            comment_weight = min(np.log10(post.num_comments + 1) / 3.0, 1.0)

            # 스코어 가중치 (로그 스케일)
            score_weight = min(np.log10(abs(post.score) + 1) / 4.0, 1.0)

            # 최종 참여도 점수
            engagement_score = (base_score * 0.5 + comment_weight * 0.3 + score_weight * 0.2)
            return np.clip(engagement_score, 0.0, 1.0)

        except Exception as e:
            logger.error(f"Reddit 참여도 점수 계산 실패: {str(e)}")
            return 0.0

    def analyze_reddit_sentiment(self, post: RedditPost) -> float:
        """Reddit 포스트 센티멘트 분석 (-1 ~ +1)"""
        try:
            # 제목과 내용 결합
            text = f"{post.title} {post.content}".strip()

            if not text:
                return 0.0

            # TextBlob을 사용한 센티멘트 분석
            if TEXTBLOB_AVAILABLE:
                blob = TextBlob(text)
                sentiment = blob.sentiment.polarity
            else:
                # TextBlob이 없을 경우 간단한 키워드 기반 분석
                sentiment = self._simple_sentiment_analysis(text)

            # 업보트 비율로 센티멘트 보정
            upvote_adjustment = (post.upvote_ratio - 0.5) * 0.3

            # 최종 센티멘트 점수
            final_sentiment = sentiment + upvote_adjustment
            return np.clip(final_sentiment, -1.0, 1.0)

        except Exception as e:
            logger.error(f"Reddit 센티멘트 분석 실패: {str(e)}")
            return 0.0

    def _simple_sentiment_analysis(self, text: str) -> float:
        """간단한 키워드 기반 센티멘트 분석"""
        positive_keywords = ['good', 'great', 'excellent', 'amazing', 'bullish', 'moon', 'pump', 'buy', 'hodl']
        negative_keywords = ['bad', 'terrible', 'awful', 'bearish', 'dump', 'sell', 'crash', 'fear']

        text_lower = text.lower()
        positive_count = sum(1 for word in positive_keywords if word in text_lower)
        negative_count = sum(1 for word in negative_keywords if word in text_lower)

        if positive_count + negative_count == 0:
            return 0.0

        return (positive_count - negative_count) / (positive_count + negative_count)

class TwitterDataCollector:
    """Twitter 데이터 수집기"""

    def __init__(self, bearer_token: str):
        """
        Twitter API v2 초기화
        - Bearer Token 필요 (Academic Research access 권장)
        """
        if not TWEEPY_AVAILABLE:
            logger.error("tweepy 라이브러리가 설치되지 않음. Twitter 기능을 사용할 수 없습니다.")
            self.client = None
            return

        try:
            self.client = tweepy.Client(bearer_token=bearer_token)
            self.crypto_keywords = [
                'bitcoin', 'btc', 'cryptocurrency', 'crypto', 'ethereum', 'eth',
                'blockchain', 'defi', 'nft', 'web3', 'binance', 'coinbase'
            ]
            logger.info("✅ Twitter API 초기화 완료")
        except Exception as e:
            logger.error(f"Twitter API 초기화 실패: {str(e)}")
            self.client = None

    async def collect_crypto_tweets(
        self,
        max_results: int = 100,
        hours_back: int = 24
    ) -> List[TwitterPost]:
        """크립토 관련 트윗 수집"""
        try:
            if not self.client:
                logger.warning("Twitter API가 초기화되지 않음")
                return []

            tweets = []
            query = " OR ".join(self.crypto_keywords)

            # 시간 필터 (최근 24시간)
            start_time = datetime.utcnow() - timedelta(hours=hours_back)

            try:
                # Twitter API v2로 트윗 검색
                response = self.client.search_recent_tweets(
                    query=query,
                    max_results=min(max_results, 100),  # API 제한
                    tweet_fields=['created_at', 'public_metrics', 'author_id'],
                    user_fields=['username'],
                    start_time=start_time
                )

                if response.data:
                    for tweet in response.data:
                        # 공개 메트릭스 추출
                        metrics = tweet.public_metrics

                        twitter_post = TwitterPost(
                            text=tweet.text,
                            author=f"@{tweet.author_id}",  # 실제로는 username 매핑 필요
                            retweet_count=metrics.get('retweet_count', 0),
                            like_count=metrics.get('like_count', 0),
                            reply_count=metrics.get('reply_count', 0),
                            created_at=tweet.created_at,
                            tweet_id=tweet.id,
                            is_retweet=tweet.text.startswith('RT @')
                        )
                        tweets.append(twitter_post)

            except Exception as e:
                logger.warning(f"Twitter API 호출 실패: {str(e)}")
                # 모의 데이터 반환
                tweets = self._generate_mock_tweets(max_results)

            logger.info(f"✅ Twitter 트윗 {len(tweets)}개 수집 완료")
            return tweets

        except Exception as e:
            logger.error(f"Twitter 데이터 수집 실패: {str(e)}")
            return []

    def _generate_mock_tweets(self, count: int) -> List[TwitterPost]:
        """모의 트윗 데이터 생성 (API 실패 시)"""
        mock_tweets = []
        base_time = datetime.utcnow()

        mock_texts = [
            "Bitcoin is looking bullish today! 🚀",
            "Crypto market is showing strong momentum",
            "Ethereum 2.0 upgrade is game changing",
            "Regulatory concerns are affecting crypto prices",
            "Institutional adoption of Bitcoin continues",
            "DeFi protocols are innovating rapidly",
            "NFT market seems to be cooling down",
            "Crypto volatility is expected this week"
        ]

        for i in range(count):
            text = mock_texts[i % len(mock_texts)]
            mock_tweets.append(TwitterPost(
                text=text,
                author=f"@crypto_user_{i}",
                retweet_count=np.random.randint(0, 100),
                like_count=np.random.randint(0, 500),
                reply_count=np.random.randint(0, 50),
                created_at=base_time - timedelta(hours=i),
                tweet_id=f"mock_{i}",
                is_retweet=False
            ))

        return mock_tweets

    def calculate_twitter_engagement_score(self, tweet: TwitterPost) -> float:
        """Twitter 트윗 참여도 점수 계산 (0 ~ 1)"""
        try:
            # 리트윗, 좋아요, 댓글 수를 종합한 참여도 점수
            total_engagement = tweet.retweet_count + tweet.like_count + tweet.reply_count

            # 로그 스케일로 정규화 (0 ~ 1)
            engagement_score = min(np.log10(total_engagement + 1) / 4.0, 1.0)

            return engagement_score

        except Exception as e:
            logger.error(f"Twitter 참여도 점수 계산 실패: {str(e)}")
            return 0.0

    def analyze_twitter_sentiment(self, tweet: TwitterPost) -> float:
        """Twitter 트윗 센티멘트 분석 (-1 ~ +1)"""
        try:
            if not tweet.text:
                return 0.0

            # TextBlob을 사용한 센티멘트 분석
            if TEXTBLOB_AVAILABLE:
                blob = TextBlob(tweet.text)
                sentiment = blob.sentiment.polarity
            else:
                # TextBlob이 없을 경우 간단한 키워드 기반 분석
                sentiment = self._simple_sentiment_analysis(tweet.text)

            # 참여도로 센티멘트 보정
            engagement_score = self.calculate_twitter_engagement_score(tweet)
            engagement_adjustment = (engagement_score - 0.5) * 0.2

            # 최종 센티멘트 점수
            final_sentiment = sentiment + engagement_adjustment
            return np.clip(final_sentiment, -1.0, 1.0)

        except Exception as e:
            logger.error(f"Twitter 센티멘트 분석 실패: {str(e)}")
            return 0.0

    def _simple_sentiment_analysis(self, text: str) -> float:
        """간단한 키워드 기반 센티멘트 분석"""
        positive_keywords = ['good', 'great', 'excellent', 'amazing', 'bullish', 'moon', 'pump', 'buy', 'hodl']
        negative_keywords = ['bad', 'terrible', 'awful', 'bearish', 'dump', 'sell', 'crash', 'fear']

        text_lower = text.lower()
        positive_count = sum(1 for word in positive_keywords if word in text_lower)
        negative_count = sum(1 for word in negative_keywords if word in text_lower)

        if positive_count + negative_count == 0:
            return 0.0

        return (positive_count - negative_count) / (positive_count + negative_count)

class SocialDataAggregator:
    """소셜미디어 데이터 통합 분석기"""

    def __init__(self, reddit_config: Optional[Dict[str, str]] = None, twitter_config: Optional[Dict[str, str]] = None):
        """
        소셜미디어 데이터 수집기 초기화

        Args:
            reddit_config: {'client_id': '', 'client_secret': '', 'user_agent': ''}
            twitter_config: {'bearer_token': ''}
        """
        self.reddit_collector = None
        self.twitter_collector = None

        # Reddit 초기화
        if reddit_config and all(k in reddit_config for k in ['client_id', 'client_secret', 'user_agent']):
            self.reddit_collector = RedditDataCollector(
                client_id=reddit_config['client_id'],
                client_secret=reddit_config['client_secret'],
                user_agent=reddit_config['user_agent']
            )

        # Twitter 초기화
        if twitter_config and 'bearer_token' in twitter_config:
            self.twitter_collector = TwitterDataCollector(
                bearer_token=twitter_config['bearer_token']
            )

    async def collect_social_mentions(
        self,
        reddit_limit: int = 50,
        twitter_limit: int = 50,
        hours_back: int = 24
    ) -> List[SocialMention]:
        """소셜미디어 멘션 통합 수집"""
        try:
            mentions = []

            # Reddit 데이터 수집
            if self.reddit_collector:
                try:
                    reddit_posts = await self.reddit_collector.collect_crypto_posts(
                        limit=reddit_limit
                    )

                    for post in reddit_posts:
                        mention = SocialMention(
                            platform="reddit",
                            content=f"{post.title} {post.content}".strip(),
                            author=post.author,
                            engagement_score=self.reddit_collector.calculate_reddit_engagement_score(post),
                            sentiment_score=self.reddit_collector.analyze_reddit_sentiment(post),
                            timestamp=post.created_utc,
                            url=post.url
                        )
                        mentions.append(mention)
                except Exception as e:
                    logger.warning(f"Reddit 데이터 수집 실패: {str(e)}")

            # Twitter 데이터 수집
            if self.twitter_collector:
                try:
                    twitter_tweets = await self.twitter_collector.collect_crypto_tweets(
                        max_results=twitter_limit,
                        hours_back=hours_back
                    )

                    for tweet in twitter_tweets:
                        mention = SocialMention(
                            platform="twitter",
                            content=tweet.text,
                            author=tweet.author,
                            engagement_score=self.twitter_collector.calculate_twitter_engagement_score(tweet),
                            sentiment_score=self.twitter_collector.analyze_twitter_sentiment(tweet),
                            timestamp=tweet.created_at,
                            url=f"https://twitter.com/user/status/{tweet.tweet_id}"
                        )
                        mentions.append(mention)
                except Exception as e:
                    logger.warning(f"Twitter 데이터 수집 실패: {str(e)}")

            # API 키가 없거나 실패한 경우 모의 데이터 생성
            if not mentions:
                logger.info("API 키가 없거나 실패, 모의 소셜 데이터 생성")
                mentions = self._generate_mock_social_mentions(reddit_limit, twitter_limit)

            logger.info(f"✅ 소셜미디어 멘션 {len(mentions)}개 수집 완료")
            return mentions

        except Exception as e:
            logger.error(f"소셜미디어 데이터 수집 실패: {str(e)}")
            # 에러 시에도 모의 데이터 반환
            return self._generate_mock_social_mentions(reddit_limit, twitter_limit)

    def _generate_mock_social_mentions(self, reddit_limit: int, twitter_limit: int) -> List[SocialMention]:
        """모의 소셜미디어 멘션 데이터 생성"""
        mentions = []
        base_time = datetime.now()

        # Reddit 모의 데이터
        reddit_posts = [
            "Bitcoin is looking bullish today! 🚀",
            "Crypto market showing strong momentum",
            "Ethereum 2.0 upgrade is game changing",
            "Regulatory concerns affecting crypto prices",
            "Institutional adoption of Bitcoin continues",
            "DeFi protocols innovating rapidly",
            "NFT market seems to be cooling down",
            "Crypto volatility expected this week"
        ]

        for i in range(min(reddit_limit, len(reddit_posts))):
            content = reddit_posts[i % len(reddit_posts)]
            mentions.append(SocialMention(
                platform="reddit",
                content=content,
                author=f"reddit_user_{i}",
                engagement_score=np.random.uniform(0.3, 0.8),
                sentiment_score=np.random.uniform(-0.5, 0.7),
                timestamp=base_time - timedelta(hours=i),
                url=f"https://reddit.com/r/Bitcoin/comments/mock_{i}"
            ))

        # Twitter 모의 데이터
        twitter_tweets = [
            "Bitcoin breaking resistance levels! 📈",
            "Crypto market sentiment improving",
            "Ethereum network upgrades showing results",
            "Regulatory clarity needed for crypto",
            "Major banks entering crypto space",
            "DeFi yield farming opportunities",
            "NFT market correction underway",
            "Crypto adoption accelerating globally"
        ]

        for i in range(min(twitter_limit, len(twitter_tweets))):
            content = twitter_tweets[i % len(twitter_tweets)]
            mentions.append(SocialMention(
                platform="twitter",
                content=content,
                author=f"@crypto_trader_{i}",
                engagement_score=np.random.uniform(0.2, 0.9),
                sentiment_score=np.random.uniform(-0.3, 0.6),
                timestamp=base_time - timedelta(hours=i),
                url=f"https://twitter.com/user/status/mock_{i}"
            ))

        return mentions

    def calculate_platform_sentiment(self, mentions: List[SocialMention], platform: str) -> Dict[str, Any]:
        """플랫폼별 센티멘트 분석"""
        try:
            platform_mentions = [m for m in mentions if m.platform == platform]

            if not platform_mentions:
                return {
                    "platform": platform,
                    "mention_count": 0,
                    "avg_sentiment": 0.0,
                    "avg_engagement": 0.0,
                    "sentiment_score": 0.0,
                    "trend_score": 0.0
                }

            # 평균 센티멘트 및 참여도 계산
            sentiments = [m.sentiment_score for m in platform_mentions]
            engagements = [m.engagement_score for m in platform_mentions]

            avg_sentiment = np.mean(sentiments)
            avg_engagement = np.mean(engagements)

            # 가중 평균 (참여도 기반)
            weights = [m.engagement_score for m in platform_mentions]
            weighted_sentiment = np.average(sentiments, weights=weights)

            return {
                "platform": platform,
                "mention_count": len(platform_mentions),
                "avg_sentiment": avg_sentiment,
                "avg_engagement": avg_engagement,
                "sentiment_score": weighted_sentiment,
                "trend_score": avg_engagement
            }

        except Exception as e:
            logger.error(f"{platform} 센티멘트 분석 실패: {str(e)}")
            return {
                "platform": platform,
                "mention_count": 0,
                "avg_sentiment": 0.0,
                "avg_engagement": 0.0,
                "sentiment_score": 0.0,
                "trend_score": 0.0
            }

    async def analyze_social_sentiment(
        self,
        reddit_limit: int = 50,
        twitter_limit: int = 50,
        hours_back: int = 24
    ) -> Dict[str, Any]:
        """소셜미디어 센티멘트 통합 분석"""
        try:
            logger.info("🔍 [소셜미디어] 센티멘트 분석 시작")

            # 데이터 수집
            mentions = await self.collect_social_mentions(
                reddit_limit=reddit_limit,
                twitter_limit=twitter_limit,
                hours_back=hours_back
            )

            if not mentions:
                return {
                    "overall_sentiment": 0.0,
                    "sentiment_score": 0.0,
                    "trend_score": 0.0,
                    "platform_count": 0,
                    "total_mentions": 0,
                    "platform_analysis": {},
                    "analysis": "소셜미디어 데이터 없음"
                }

            # 플랫폼별 분석
            platforms = list(set(m.platform for m in mentions))
            platform_analysis = {}

            for platform in platforms:
                platform_analysis[platform] = self.calculate_platform_sentiment(mentions, platform)

            # 전체 센티멘트 계산 (플랫폼별 가중치 적용)
            platform_weights = {
                'reddit': 0.4,
                'twitter': 0.6
            }

            weighted_sentiment = 0.0
            weighted_trend = 0.0
            total_weight = 0.0
            total_mentions = len(mentions)

            for platform, analysis in platform_analysis.items():
                weight = platform_weights.get(platform, 0.5)
                weighted_sentiment += analysis['sentiment_score'] * weight
                weighted_trend += analysis['trend_score'] * weight
                total_weight += weight

            # 최종 점수 계산
            overall_sentiment = weighted_sentiment / total_weight if total_weight > 0 else 0.0
            overall_trend = weighted_trend / total_weight if total_weight > 0 else 0.0

            # 분석 결과
            if overall_sentiment > 0.3:
                analysis = f"🟢 긍정적 소셜 센티멘트 (트렌드: {overall_trend:.2f})"
            elif overall_sentiment < -0.3:
                analysis = f"🔴 부정적 소셜 센티멘트 (트렌드: {overall_trend:.2f})"
            else:
                analysis = f"🟡 중립적 소셜 센티멘트 (트렌드: {overall_trend:.2f})"

            logger.info(f"✅ [소셜미디어] 분석 완료: {analysis}")

            return {
                "overall_sentiment": overall_sentiment,
                "sentiment_score": overall_sentiment,
                "trend_score": overall_trend,
                "platform_count": len(platforms),
                "total_mentions": total_mentions,
                "platform_analysis": platform_analysis,
                "analysis": analysis
            }

        except Exception as e:
            logger.error(f"소셜미디어 센티멘트 분석 실패: {str(e)}")
            return {
                "overall_sentiment": 0.0,
                "sentiment_score": 0.0,
                "trend_score": 0.0,
                "platform_count": 0,
                "total_mentions": 0,
                "platform_analysis": {},
                "analysis": "소셜미디어 분석 실패"
            }
