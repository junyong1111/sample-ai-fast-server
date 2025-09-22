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
    market: str = Query(..., description="조회할 마켓 (예: BTC/USDT)"),
    hours_back: int = Query(24, ge=1, le=168, description="몇 시간 전까지의 데이터를 조회할지 (최대 168시간 = 7일)"),
    limit: int = Query(10, ge=1, le=100, description="조회할 최대 결과 수")
):
    """
    리스크 분석 결과 조회 (GET 방식)

    스케줄러에서 1시간마다 미리 분석한 리스크 분석 결과를 데이터베이스에서 조회합니다.
    """
    try:
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

            # 최신 리스크 분석 결과 조회
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

            rows = await conn.fetch(query, market, start_time, limit)

            if not rows:
                return {
                    "status": "success",
                    "market": market,
                    "message": "해당 마켓에 대한 리스크 분석 결과가 없습니다.",
                    "data": [],
                    "query_info": {
                        "market": market,
                        "hours_back": hours_back,
                        "limit": limit,
                        "queried_at": datetime.now().isoformat()
                    }
                }

            # 결과를 딕셔너리로 변환
            results = []
            for row in rows:
                result_dict = dict(row)
                results.append(result_dict)

            # 가장 최신 결과를 메인 응답으로 사용
            latest_result = results[0]

            return {
                "status": "success",
                "market": market,
                "timestamp": latest_result['created_at'].isoformat(),
                "risk_grade": latest_result['market_risk_level'],
                "analysis": {
                    "risk_indicators": latest_result['risk_indicators'],
                    "correlation_analysis": latest_result['correlation_analysis'],
                    "risk_off_signal": latest_result['risk_off_signal'],
                    "confidence": latest_result['confidence']
                },
                "metadata": {
                    "analysis_period": f"{hours_back}시간",
                    "data_points": len(results),
                    "latest_analysis_at": latest_result['created_at'].isoformat(),
                    "expires_at": latest_result['expires_at'].isoformat()
                },
                "historical_data": results
            }

        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"❌ 리스크 분석 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"리스크 분석 조회 실패: {str(e)}"
        )