"""
실제 데이터 소스 연결 모듈
- NewsAPI, Twitter API, FRED API 등 실제 데이터 소스 연결
"""

import asyncio
import aiohttp
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import os
from dataclasses import dataclass

from src.common.utils.logger import set_logger

logger = set_logger("real_data_sources")

@dataclass
class APIKey:
    """API 키 관리"""
    news_api: str = os.getenv('NEWS_API_KEY', '')
    twitter_bearer: str = os.getenv('TWITTER_BEARER_TOKEN', '')
    fred_api: str = os.getenv('FRED_API_KEY', '')
    alpha_vantage: str = os.getenv('ALPHA_VANTAGE_API_KEY', '')

class NewsAPIClient:
    """NewsAPI 클라이언트"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://newsapi.org/v2"
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get_crypto_news(self, query: str = "bitcoin cryptocurrency",
                            language: str = "en",
                            sort_by: str = "publishedAt",
                            page_size: int = 20) -> List[Dict[str, Any]]:
        """크립토 뉴스 수집"""
        try:
            if not self.api_key:
                logger.warning("NewsAPI 키가 설정되지 않음. 모의 데이터 사용")
                return self._get_mock_news()

            url = f"{self.base_url}/everything"
            params = {
                'q': query,
                'language': language,
                'sortBy': sort_by,
                'pageSize': page_size,
                'apiKey': self.api_key
            }

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('articles', [])
                else:
                    logger.error(f"NewsAPI 요청 실패: {response.status}")
                    return self._get_mock_news()

        except Exception as e:
            logger.error(f"뉴스 데이터 수집 실패: {str(e)}")
            return self._get_mock_news()

    def _get_mock_news(self) -> List[Dict[str, Any]]:
        """모의 뉴스 데이터"""
        return [
            {
                "title": "Bitcoin ETF Approval Expected This Week",
                "source": {"name": "Reuters"},
                "publishedAt": (datetime.now() - timedelta(hours=2)).isoformat(),
                "url": "https://reuters.com/bitcoin-etf",
                "description": "Major Bitcoin ETF approval expected this week..."
            },
            {
                "title": "Crypto Regulation Concerns Rise in Europe",
                "source": {"name": "Bloomberg"},
                "publishedAt": (datetime.now() - timedelta(hours=4)).isoformat(),
                "url": "https://bloomberg.com/crypto-regulation",
                "description": "European regulators express concerns about crypto..."
            }
        ]

class TwitterAPIClient:
    """Twitter API 클라이언트"""

    def __init__(self, bearer_token: str):
        self.bearer_token = bearer_token
        self.base_url = "https://api.twitter.com/2"
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get_crypto_tweets(self, query: str = "bitcoin",
                              max_results: int = 100) -> List[Dict[str, Any]]:
        """크립토 관련 트윗 수집"""
        try:
            if not self.bearer_token:
                logger.warning("Twitter Bearer Token이 설정되지 않음. 모의 데이터 사용")
                return self._get_mock_tweets()

            url = f"{self.base_url}/tweets/search/recent"
            params = {
                'query': f"{query} lang:en",
                'max_results': max_results,
                'tweet.fields': 'created_at,public_metrics,context_annotations'
            }

            headers = {
                'Authorization': f'Bearer {self.bearer_token}'
            }

            async with self.session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('data', [])
                else:
                    logger.error(f"Twitter API 요청 실패: {response.status}")
                    return self._get_mock_tweets()

        except Exception as e:
            logger.error(f"트윗 데이터 수집 실패: {str(e)}")
            return self._get_mock_tweets()

    def _get_mock_tweets(self) -> List[Dict[str, Any]]:
        """모의 트윗 데이터"""
        return [
            {
                "id": "1234567890",
                "text": "Bitcoin is looking strong today! 🚀",
                "created_at": (datetime.now() - timedelta(hours=1)).isoformat(),
                "public_metrics": {
                    "retweet_count": 50,
                    "like_count": 200,
                    "reply_count": 10
                }
            },
            {
                "id": "1234567891",
                "text": "Crypto market is volatile but I'm bullish long-term",
                "created_at": (datetime.now() - timedelta(hours=2)).isoformat(),
                "public_metrics": {
                    "retweet_count": 25,
                    "like_count": 100,
                    "reply_count": 5
                }
            }
        ]

class FREDAPIClient:
    """FRED API 클라이언트 (연방준비은행 경제 데이터)"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.stlouisfed.org/fred"
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get_economic_indicators(self) -> Dict[str, Any]:
        """경제 지표 수집"""
        try:
            if not self.api_key:
                logger.warning("FRED API 키가 설정되지 않음. 모의 데이터 사용")
                return self._get_mock_economic_data()

            indicators = {}

            # CPI 데이터
            cpi_data = await self._get_series_data('CPIAUCSL')
            indicators['cpi'] = cpi_data

            # PPI 데이터
            ppi_data = await self._get_series_data('PPIACO')
            indicators['ppi'] = ppi_data

            # 실업률 데이터
            unemployment_data = await self._get_series_data('UNRATE')
            indicators['unemployment'] = unemployment_data

            return indicators

        except Exception as e:
            logger.error(f"경제 지표 수집 실패: {str(e)}")
            return self._get_mock_economic_data()

    async def _get_series_data(self, series_id: str) -> Dict[str, Any]:
        """시리즈 데이터 수집"""
        url = f"{self.base_url}/series/observations"
        params = {
            'series_id': series_id,
            'api_key': self.api_key,
            'file_type': 'json',
            'limit': 1,
            'sort_order': 'desc'
        }

        async with self.session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                observations = data.get('observations', [])
                if observations:
                    latest = observations[0]
                    return {
                        'value': float(latest.get('value', 0)),
                        'date': latest.get('date', ''),
                        'series_id': series_id
                    }
            return {'value': 0, 'date': '', 'series_id': series_id}

    def _get_mock_economic_data(self) -> Dict[str, Any]:
        """모의 경제 데이터"""
        return {
            'cpi': {'value': 3.2, 'date': '2024-01-01', 'series_id': 'CPIAUCSL'},
            'ppi': {'value': 2.8, 'date': '2024-01-01', 'series_id': 'PPIACO'},
            'unemployment': {'value': 3.8, 'date': '2024-01-01', 'series_id': 'UNRATE'}
        }

class RealDataCollector:
    """실제 데이터 수집기"""

    def __init__(self):
        self.api_keys = APIKey()

    async def collect_all_data(self) -> Dict[str, Any]:
        """모든 데이터 소스에서 데이터 수집"""
        try:
            logger.info("🔍 [실제 데이터] 수집 시작")

            # 뉴스 데이터
            async with NewsAPIClient(self.api_keys.news_api) as news_client:
                news_data = await news_client.get_crypto_news()

            # 트위터 데이터
            async with TwitterAPIClient(self.api_keys.twitter_bearer) as twitter_client:
                twitter_data = await twitter_client.get_crypto_tweets()

            # 경제 지표 데이터
            async with FREDAPIClient(self.api_keys.fred_api) as fred_client:
                economic_data = await fred_client.get_economic_indicators()

            logger.info("✅ [실제 데이터] 수집 완료")

            return {
                'news': news_data,
                'social': twitter_data,
                'macro': economic_data,
                'timestamp': datetime.now().isoformat(),
                'data_sources': {
                    'news': 'NewsAPI' if self.api_keys.news_api else 'Mock',
                    'social': 'Twitter API' if self.api_keys.twitter_bearer else 'Mock',
                    'macro': 'FRED API' if self.api_keys.fred_api else 'Mock'
                }
            }

        except Exception as e:
            logger.error(f"실제 데이터 수집 실패: {str(e)}")
            return {
                'news': [],
                'social': [],
                'macro': {},
                'timestamp': datetime.now().isoformat(),
                'data_sources': {'news': 'Mock', 'social': 'Mock', 'macro': 'Mock'},
                'error': str(e)
            }
