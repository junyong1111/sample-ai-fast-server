"""
차트 분석 조회 API 라우터
"""
from typing import List
from fastapi import APIRouter, HTTPException, Query

from src.common.utils.logger import set_logger
from src.app.analysis.service import AnalysisService

logger = set_logger(__name__)
router = APIRouter(tags=["analysis"])

@router.get(
    "",
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