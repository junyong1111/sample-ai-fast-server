"""
오프체인 분석 전용 라우터 V2
- N8n 에이전트가 툴로서 자유롭게 사용할 수 있는 독립적인 API
- 뉴스, 소셜미디어, 거시경제 지표 분석
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Dict, Any, Optional
import asyncio
import os
from datetime import datetime

from .offchain_service import OffchainServiceV2
from .models import OffchainRequest, OffchainResponse
from src.common.utils.social_data_sources import SocialDataAggregator
from src.common.utils.logger import set_logger

logger = set_logger("offchain_router_v2")

# 오프체인 전용 라우터 생성
router = APIRouter(
    prefix="/offchain",
    tags=["Offchain Analysis V2"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal Server Error"}
    }
)

@router.get(
    "/analyze",
    summary="오프체인 센티멘트 분석 (GET 방식)",
    description="GET 방식으로 간단한 오프체인 센티멘트 분석을 수행합니다."
)
async def analyze_offchain_simple(
    market: str = Query(..., description="거래 마켓 (예: BTC/USDT)"),
    timeframe: str = Query("minutes:60", description="시간프레임"),
    count: int = Query(200, description="캔들 개수"),
    include_news: bool = Query(True, description="뉴스 분석 포함 여부"),
    include_social: bool = Query(True, description="소셜미디어 분석 포함 여부"),
    include_macro: bool = Query(True, description="거시경제 분석 포함 여부")
):
    """오프체인 센티멘트 분석 (GET 방식)"""
    try:
        logger.info(f"🔍 [오프체인] GET 요청: {market} | {timeframe} | {count}개")

        async with OffchainServiceV2() as service:
            result = await service.analyze_offchain_sentiment(
                market=market,
                timeframe=timeframe,
                count=count
            )

        return result

    except Exception as e:
        logger.error(f"오프체인 분석 GET 요청 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"오프체인 분석 실패: {str(e)}")

@router.post(
    "/analyze",
    summary="오프체인 센티멘트 분석 (POST 방식)",
    description="POST 방식으로 상세한 오프체인 센티멘트 분석을 수행합니다."
)
async def analyze_offchain_detailed(
    request: OffchainRequest = Body(..., description="오프체인 분석 요청 데이터")
):
    """오프체인 센티멘트 분석 (POST 방식)"""
    try:
        logger.info(f"🔍 [오프체인] POST 요청: {request.market} | {request.timeframe} | {request.count}개")
        logger.info(f"📊 포함 옵션: 뉴스={request.include_news}, 소셜={request.include_social}, 거시경제={request.include_macro}")

        async with OffchainServiceV2() as service:
            result = await service.analyze_offchain_sentiment(
                market=request.market,
                timeframe=request.timeframe,
                count=request.count
            )

        return result

    except Exception as e:
        logger.error(f"오프체인 분석 POST 요청 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"오프체인 분석 실패: {str(e)}")

@router.get(
    "/news/analyze",
    summary="뉴스 센티멘트 분석",
    description="뉴스 헤드라인만을 대상으로 센티멘트 분석을 수행합니다."
)
async def analyze_news_sentiment(
    market: str = Query(..., description="거래 마켓 (예: BTC/USDT)"),
    timeframe: str = Query("minutes:60", description="시간프레임"),
    count: int = Query(200, description="캔들 개수")
):
    """뉴스 센티멘트 분석"""
    try:
        logger.info(f"📰 [뉴스] 분석 요청: {market} | {timeframe} | {count}개")

        async with OffchainServiceV2() as service:
            result = await service.analyze_offchain_sentiment(
                market=market,
                timeframe=timeframe,
                count=count
            )

            # 뉴스 분석만 추출
            news_analysis = result.get('analysis', {}).get('news_analysis', {})
            detailed_news = result.get('detailed_data', {}).get('news_analysis', {})

            return {
                "status": "success",
                "market": market,
                "timeframe": timeframe,
                "timestamp": datetime.now().isoformat(),
                "analysis": {
                    "news_sentiment": news_analysis,
                    "overall_sentiment": result.get('analysis', {}).get('overall_sentiment', {})
                },
                "detailed_data": {
                    "news_analysis": detailed_news,
                    "offchain_score": result.get('detailed_data', {}).get('offchain_score', 0.0)
                },
                "metadata": {
                    "analysis_type": "news_only",
                    "version": "v2"
                }
            }

    except Exception as e:
        logger.error(f"뉴스 분석 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"뉴스 분석 실패: {str(e)}")

@router.get(
    "/social/analyze",
    summary="소셜미디어 센티멘트 분석",
    description="소셜미디어 데이터만을 대상으로 센티멘트 분석을 수행합니다."
)
async def analyze_social_sentiment(
    market: str = Query(..., description="거래 마켓 (예: BTC/USDT)"),
    timeframe: str = Query("minutes:60", description="시간프레임"),
    count: int = Query(200, description="캔들 개수")
):
    """소셜미디어 센티멘트 분석"""
    try:
        logger.info(f"📱 [소셜] 분석 요청: {market} | {timeframe} | {count}개")

        async with OffchainServiceV2() as service:
            result = await service.analyze_offchain_sentiment(
                market=market,
                timeframe=timeframe,
                count=count
            )

            # 소셜 분석만 추출
            social_analysis = result.get('analysis', {}).get('social_analysis', {})
            detailed_social = result.get('detailed_data', {}).get('social_analysis', {})

            return {
                "status": "success",
                "market": market,
                "timeframe": timeframe,
                "timestamp": datetime.now().isoformat(),
                "analysis": {
                    "social_sentiment": social_analysis,
                    "overall_sentiment": result.get('analysis', {}).get('overall_sentiment', {})
                },
                "detailed_data": {
                    "social_analysis": detailed_social,
                    "offchain_score": result.get('detailed_data', {}).get('offchain_score', 0.0)
                },
                "metadata": {
                    "analysis_type": "social_only",
                    "version": "v2"
                }
            }

    except Exception as e:
        logger.error(f"소셜 분석 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"소셜 분석 실패: {str(e)}")

@router.get(
    "/macro/analyze",
    summary="거시경제 지표 분석",
    description="거시경제 지표만을 대상으로 분석을 수행합니다."
)
async def analyze_macro_indicators(
    market: str = Query(..., description="거래 마켓 (예: BTC/USDT)"),
    timeframe: str = Query("minutes:60", description="시간프레임"),
    count: int = Query(200, description="캔들 개수")
):
    """거시경제 지표 분석"""
    try:
        logger.info(f"📈 [거시경제] 분석 요청: {market} | {timeframe} | {count}개")

        async with OffchainServiceV2() as service:
            result = await service.analyze_offchain_sentiment(
                market=market,
                timeframe=timeframe,
                count=count
            )

            # 거시경제 분석만 추출
            macro_analysis = result.get('analysis', {}).get('macro_analysis', {})
            detailed_macro = result.get('detailed_data', {}).get('macro_analysis', {})

            return {
                "status": "success",
                "market": market,
                "timeframe": timeframe,
                "timestamp": datetime.now().isoformat(),
                "analysis": {
                    "macro_impact": macro_analysis,
                    "overall_sentiment": result.get('analysis', {}).get('overall_sentiment', {})
                },
                "detailed_data": {
                    "macro_analysis": detailed_macro,
                    "offchain_score": result.get('detailed_data', {}).get('offchain_score', 0.0)
                },
                "metadata": {
                    "analysis_type": "macro_only",
                    "version": "v2"
                }
            }

    except Exception as e:
        logger.error(f"거시경제 분석 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"거시경제 분석 실패: {str(e)}")

@router.get(
    "/health",
    summary="오프체인 분석 서비스 상태 확인",
    description="오프체인 분석 서비스의 상태를 확인합니다."
)
async def health_check():
    """오프체인 분석 서비스 상태 확인"""
    try:
        return {
            "status": "healthy",
            "service": "offchain_analysis_v2",
            "timestamp": datetime.now().isoformat(),
            "version": "v2",
            "endpoints": {
                "full_analysis": "/api/v1/autotrading/v2/offchain/analyze",
                "news_only": "/api/v1/autotrading/v2/offchain/news/analyze",
                "social_only": "/api/v1/autotrading/v2/offchain/social/analyze",
                "macro_only": "/api/v1/autotrading/v2/offchain/macro/analyze"
            }
        }
    except Exception as e:
        logger.error(f"헬스체크 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"헬스체크 실패: {str(e)}")

@router.get(
    "/reddit/analyze",
    summary="Reddit 센티멘트 분석",
    description="Reddit 데이터만을 대상으로 센티멘트 분석을 수행합니다."
)
async def analyze_reddit_sentiment(
    market: str = Query(..., description="거래 마켓 (예: BTC/USDT)"),
    limit: int = Query(50, description="수집할 포스트 수"),
    hours_back: int = Query(24, description="수집할 시간 범위 (시간)")
):
    """Reddit 센티멘트 분석"""
    try:
        logger.info(f"🔴 [Reddit] 분석 요청: {market} | {limit}개 | {hours_back}시간")

        # Reddit 설정 (환경변수에서 가져오기)
        reddit_client_id = os.getenv('REDDIT_CLIENT_ID')
        reddit_client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        reddit_user_agent = os.getenv('REDDIT_USER_AGENT', 'QuantumInsight/1.0 by YourUsername')

        if not reddit_client_id or not reddit_client_secret:
            raise HTTPException(
                status_code=500,
                detail="Reddit API 설정이 필요합니다. REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET 환경변수를 확인하세요."
            )

        reddit_config = {
            'client_id': reddit_client_id,
            'client_secret': reddit_client_secret,
            'user_agent': reddit_user_agent
        }

        social_aggregator = SocialDataAggregator(reddit_config=reddit_config)

        # Reddit 데이터 수집 및 분석
        reddit_mentions = await social_aggregator.collect_social_mentions(
            reddit_limit=limit,
            twitter_limit=0,  # Reddit만
            hours_back=hours_back
        )

        # Reddit 센티멘트 분석
        reddit_analysis = social_aggregator.calculate_platform_sentiment(reddit_mentions, 'reddit')

        return {
            "status": "success",
            "market": market,
            "platform": "reddit",
            "timestamp": datetime.now().isoformat(),
            "analysis": {
                "reddit_sentiment": {
                    "mention_count": reddit_analysis['mention_count'],
                    "avg_sentiment": f"{reddit_analysis['avg_sentiment']:.3f}",
                    "sentiment_score": f"{reddit_analysis['sentiment_score']:.3f}",
                    "trend_score": f"{reddit_analysis['trend_score']:.3f}",
                    "avg_engagement": f"{reddit_analysis['avg_engagement']:.3f}"
                },
                "interpretation": _get_sentiment_interpretation(reddit_analysis['sentiment_score'])
            },
            "detailed_data": {
                "platform_analysis": reddit_analysis,
                "total_mentions": len(reddit_mentions)
            },
            "metadata": {
                "analysis_type": "reddit_only",
                "version": "v2",
                "data_source": "Reddit API"
            }
        }

    except Exception as e:
        logger.error(f"Reddit 분석 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Reddit 분석 실패: {str(e)}")

@router.get(
    "/twitter/analyze",
    summary="Twitter 센티멘트 분석",
    description="Twitter 데이터만을 대상으로 센티멘트 분석을 수행합니다."
)
async def analyze_twitter_sentiment(
    market: str = Query(..., description="거래 마켓 (예: BTC/USDT)"),
    limit: int = Query(50, description="수집할 트윗 수"),
    hours_back: int = Query(24, description="수집할 시간 범위 (시간)")
):
    """Twitter 센티멘트 분석"""
    try:
        logger.info(f"🐦 [Twitter] 분석 요청: {market} | {limit}개 | {hours_back}시간")

        # Twitter 설정 (환경변수에서 가져오기)
        twitter_bearer_token = os.getenv('TWITTER_BEARER_TOKEN')

        if not twitter_bearer_token:
            raise HTTPException(
                status_code=500,
                detail="Twitter API 설정이 필요합니다. TWITTER_BEARER_TOKEN 환경변수를 확인하세요."
            )

        twitter_config = {
            'bearer_token': twitter_bearer_token
        }

        social_aggregator = SocialDataAggregator(twitter_config=twitter_config)

        # Twitter 데이터 수집 및 분석
        twitter_mentions = await social_aggregator.collect_social_mentions(
            reddit_limit=0,  # Twitter만
            twitter_limit=limit,
            hours_back=hours_back
        )

        # Twitter 센티멘트 분석
        twitter_analysis = social_aggregator.calculate_platform_sentiment(twitter_mentions, 'twitter')

        return {
            "status": "success",
            "market": market,
            "platform": "twitter",
            "timestamp": datetime.now().isoformat(),
            "analysis": {
                "twitter_sentiment": {
                    "mention_count": twitter_analysis['mention_count'],
                    "avg_sentiment": f"{twitter_analysis['avg_sentiment']:.3f}",
                    "sentiment_score": f"{twitter_analysis['sentiment_score']:.3f}",
                    "trend_score": f"{twitter_analysis['trend_score']:.3f}",
                    "avg_engagement": f"{twitter_analysis['avg_engagement']:.3f}"
                },
                "interpretation": _get_sentiment_interpretation(twitter_analysis['sentiment_score'])
            },
            "detailed_data": {
                "platform_analysis": twitter_analysis,
                "total_mentions": len(twitter_mentions)
            },
            "metadata": {
                "analysis_type": "twitter_only",
                "version": "v2",
                "data_source": "Twitter API v2"
            }
        }

    except Exception as e:
        logger.error(f"Twitter 분석 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Twitter 분석 실패: {str(e)}")

@router.get(
    "/info",
    summary="오프체인 분석 서비스 정보",
    description="오프체인 분석 서비스의 상세 정보를 제공합니다."
)
async def service_info():
    """오프체인 분석 서비스 정보"""
    return {
        "service_name": "Offchain Analysis V2",
        "description": "뉴스, 소셜미디어, 거시경제 지표를 통합 분석하는 오프체인 센티멘트 분석 서비스",
        "version": "v2",
        "features": [
            "뉴스 헤드라인 센티멘트 분석",
            "소셜미디어 센티멘트 분석 (Reddit & Twitter)",
            "거시경제 지표 분석",
            "통합 오프체인 점수 계산",
            "N8n 에이전트 호환 API"
        ],
        "data_sources": {
            "news": ["Reuters", "Bloomberg", "WSJ", "FT", "CoinDesk", "The Block"],
            "social": ["Reddit API", "Twitter API v2"],
            "macro": ["CPI", "PPI", "Interest Rates", "DXY", "Unemployment"]
        },
        "weight_distribution": {
            "news": "40%",
            "social": "35%",
            "macro": "25%"
        },
        "scoring_range": "-1.0 (강한 부정) ~ +1.0 (강한 긍정)",
        "api_endpoints": {
            "GET": "/api/v1/autotrading/v2/offchain/analyze",
            "POST": "/api/v1/autotrading/v2/offchain/analyze",
            "news": "/api/v1/autotrading/v2/offchain/news/analyze",
            "social": "/api/v1/autotrading/v2/offchain/social/analyze",
            "reddit": "/api/v1/autotrading/v2/offchain/reddit/analyze",
            "twitter": "/api/v1/autotrading/v2/offchain/twitter/analyze",
            "macro": "/api/v1/autotrading/v2/offchain/macro/analyze"
        }
    }

def _get_sentiment_interpretation(score: float) -> str:
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
