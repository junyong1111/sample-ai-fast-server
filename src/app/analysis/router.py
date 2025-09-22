"""
분석 조회 API 라우터 (차트, 리스크, 소셜)
"""
from typing import List
from fastapi import APIRouter, HTTPException, Query
import asyncpg
from src.config.database import database_config
from datetime import datetime, timedelta, timezone
import json

from src.common.utils.logger import set_logger
from src.app.analysis.service import AnalysisService
from src.app.analysis.ai_service import AIAnalysisService

logger = set_logger(__name__)
router = APIRouter(tags=["Analysis"])

@router.get(
    "/chart",
    summary="차트 분석 결과 조회",
    description="특정 티커 목록과 시간 범위에 해당하는 차트 분석 결과를 조회합니다."
)
async def get_chart_analysis(
    tickers: str = Query("BTC/USDT,ETH/USDT", description="조회할 티커 목록 (콤마로 구분, 예: BTC/USDT,ETH/USDT)"),
    hours_back: int = Query(24, ge=1, le=720, description="몇 시간 전까지의 데이터를 조회할지 (최대 720시간 = 30일)"),
    limit: int = Query(100, ge=1, le=1000, description="각 티커별로 조회할 최대 결과 수")
):
    """
    특정 티커 목록과 시간 범위에 해당하는 차트 분석 결과를 조회합니다.

    Args:
        tickers: 조회할 티커 목록 (콤마로 구분)
        hours_back: 몇 시간 전까지의 데이터를 조회할지
        limit: 각 티커별로 조회할 최대 결과 수

    Returns:
        해당 티커들의 차트 분석 결과 리스트
    """
    try:
        # 콤마로 구분된 티커 문자열을 리스트로 변환
        ticker_list = [ticker.strip() for ticker in tickers.split(',') if ticker.strip()]

        if not ticker_list:
            raise HTTPException(status_code=400, detail="티커 목록이 비어있습니다.")

        logger.info(f"📊 차트 분석 조회 요청: {len(ticker_list)}개 티커, {hours_back}시간 전부터")

        service = AnalysisService()
        reports = await service.get_chart_analysis_by_tickers(ticker_list, hours_back, limit)

        return {
            "status": "success",
            "data": reports,
            "message": f"요청된 티커 및 시간 범위에 대한 차트 분석 결과를 성공적으로 조회했습니다.",
            "query": {
                "tickers": ticker_list,
                "hours_back": hours_back,
                "limit": limit
            }
        }
    except Exception as e:
        logger.error(f"❌ 차트 분석 조회 API 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"차트 분석 조회 실패: {str(e)}")

@router.get(
    "/risk",
    summary="리스크 분석 조회",
    description="스케줄러에서 미리 분석한 리스크 분석 결과를 조회합니다."
)
async def get_risk_analysis(
    market: str = Query("BTC/USDT,ETH/USDT", description="조회할 마켓 목록 (콤마로 구분, 예: BTC/USDT,ETH/USDT)"),
    hours_back: int = Query(24, ge=1, le=168, description="몇 시간 전까지의 데이터를 조회할지 (최대 168시간 = 7일)"),
    limit: int = Query(10, ge=1, le=100, description="각 마켓별로 조회할 최대 결과 수")
):
    """
    리스크 분석 결과 조회 (GET 방식)

    스케줄러에서 1시간마다 미리 분석한 리스크 분석 결과를 데이터베이스에서 조회합니다.
    """
    try:
        # 마켓 목록 파싱
        market_list = [m.strip() for m in market.split(',') if m.strip()]
        logger.info(f"📊 리스크 분석 조회 요청: {len(market_list)}개 마켓, {hours_back}시간 전부터")

        # 데이터베이스 연결
        conn = await asyncpg.connect(
            host=database_config.POSTGRESQL_DB_HOST,
            port=int(database_config.POSTGRESQL_DB_PORT),
            database=database_config.POSTGRESQL_DB_DATABASE,
            user=database_config.POSTGRESQL_DB_USER,
            password=database_config.POSTGRESQL_DB_PASSWORD
        )

        try:
            # 시간 범위 계산
            now_utc = datetime.now(timezone.utc)
            start_time_naive = now_utc.replace(tzinfo=None) - timedelta(hours=hours_back)
            start_time = start_time_naive

            all_results = []

            # 각 마켓별로 리스크 분석 결과 조회
            for market_symbol in market_list:
                query = """
                    SELECT
                        asset_symbol,
                        risk_score,
                        market_risk_level,
                        risk_off_signal,
                        confidence,
                        risk_indicators,
                        correlation_analysis,
                        full_analysis_data,
                        created_at,
                        expires_at
                    FROM risk_analysis_reports
                    WHERE asset_symbol = $1
                    AND created_at >= $2::timestamp
                    ORDER BY created_at DESC
                    LIMIT $3
                """

                rows = await conn.fetch(query, market_symbol, start_time, limit)

                if rows:
                    # 결과를 딕셔너리로 변환
                    market_results = []
                    for row in rows:
                        result_dict = dict(row)
                        market_results.append(result_dict)

                    # 가장 최신 결과를 메인 응답으로 사용
                    latest_result = market_results[0]

                    market_data = {
                        "market": market_symbol,
                        "timestamp": latest_result['created_at'].isoformat(),
                        "risk_grade": latest_result['market_risk_level'],
                        "risk_score": latest_result['risk_score'],
                        "analysis": {
                            "risk_indicators": latest_result['risk_indicators'],
                            "correlation_analysis": latest_result['correlation_analysis'],
                            "risk_off_signal": latest_result['risk_off_signal'],
                            "confidence": latest_result['confidence']
                        },
                        "metadata": {
                            "data_points": len(market_results),
                            "latest_analysis_at": latest_result['created_at'].isoformat(),
                            "expires_at": latest_result['expires_at'].isoformat()
                        },
                        "historical_data": market_results
                    }

                    all_results.append(market_data)

            if not all_results:
                return {
                    "status": "success",
                    "message": "요청된 마켓에 대한 리스크 분석 결과가 없습니다.",
                    "data": [],
                    "query": {
                        "markets": market_list,
                        "hours_back": hours_back,
                        "limit": limit
                    }
                }

            return {
                "status": "success",
                "data": all_results,
                "message": f"요청된 마켓 및 시간 범위에 대한 리스크 분석 결과를 성공적으로 조회했습니다.",
                "query": {
                    "markets": market_list,
                    "hours_back": hours_back,
                    "limit": limit
                }
            }

        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"❌ 리스크 분석 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"리스크 분석 조회 실패: {str(e)}"
        )

@router.post(
    "/ai/chart",
    summary="AI 차트 분석",
    description="LangChain을 사용한 AI 기반 차트 분석을 수행합니다."
)
async def analyze_chart_with_ai(
    tickers: str = Query("BTC/USDT,ETH/USDT", description="분석할 티커 목록 (콤마로 구분)"),
    timeframe: str = Query("minutes:60", description="시간 프레임 (예: minutes:60)"),
    count: int = Query(200, ge=50, le=1000, description="캔들 개수"),
    exchange: str = Query("binance", description="거래소")
):
    """
    AI 기반 차트 분석

    LangChain과 OpenAI를 사용하여 차트 데이터를 분석하고
    시장 레짐을 판단하여 정량적 점수를 제공합니다.
    """
    try:
        # 티커 목록 파싱
        ticker_list = [t.strip() for t in tickers.split(',') if t.strip()]
        logger.info(f"🤖 AI 차트 분석 요청: {len(ticker_list)}개 티커")

        # AI 분석 서비스 초기화
        ai_service = AIAnalysisService()
        analysis_service = AnalysisService()

        results = []

        # 1. 모든 코인의 차트 데이터 수집
        coins_data = []
        for ticker in ticker_list:
            try:
                chart_data = await analysis_service.get_chart_data_for_ai(
                    market=ticker,
                    timeframe=timeframe,
                    count=count,
                    exchange=exchange
                )
                coins_data.append(chart_data)
                logger.info(f"✅ {ticker} 차트 데이터 수집 완료")
            except Exception as e:
                logger.error(f"❌ {ticker} 차트 데이터 수집 실패: {str(e)}")

        # 2. 다중 코인 AI 분석 실행 (비용 효율적)
        if coins_data:
            try:
                ai_results = await ai_service.analyze_multiple_coins_with_ai(coins_data)

                # 3. 결과 정리
                analysis_results = ai_results.get('analysis_results', {})
                for coin_data in coins_data:
                    market = coin_data.get('market', 'Unknown')
                    result = {
                        "ticker": market,
                        "ai_analysis": analysis_results.get(market, None),
                        "raw_data": coin_data
                    }
                    results.append(result)

                logger.info(f"✅ 다중 코인 AI 분석 완료: {len(coins_data)}개 코인")

            except Exception as e:
                logger.error(f"❌ 다중 코인 AI 분석 실패: {str(e)}")
                # 실패시 기본 결과
                for coin_data in coins_data:
                    results.append({
                        "ticker": coin_data.get('market', 'Unknown'),
                        "ai_analysis": None,
                        "error": str(e)
                    })
        else:
            logger.error("❌ 수집된 차트 데이터가 없습니다")

        return {
            "status": "success",
            "data": results,
            "message": f"AI 차트 분석 완료: {len(results)}개 티커",
            "query": {
                "tickers": ticker_list,
                "timeframe": timeframe,
                "count": count,
                "exchange": exchange
            }
        }

    except Exception as e:
        logger.error(f"❌ AI 차트 분석 API 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI 차트 분석 실패: {str(e)}")