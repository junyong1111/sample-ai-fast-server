"""
분석 보고서 관련 라우터
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from src.app.analysis.models import AnalysisReportRequest, AnalysisReportResponse
from src.app.analysis.service import AnalysisService
from src.common.utils.logger import set_logger
from src.common.error import JSendError

logger = set_logger("analysis_router")

# 라우터 인스턴스 생성
router = APIRouter(tags=["Analysis"])

# 서비스 인스턴스 생성
analysis_service = AnalysisService(logger)


@router.post("/record_report", response_model=AnalysisReportResponse)
async def record_analysis_report(request: AnalysisReportRequest):
    """
    분석 보고서 저장 API

    The Analysts 워크플로우에서 호출하는 API입니다.
    모든 분석 에이전트의 결과를 종합하여 analysis_reports 테이블에 저장합니다.
    """
    try:
        logger.info(f"분석 보고서 저장 요청: user_idx={request.user_idx}")

        result = await analysis_service.save_analysis_report(request)

        return AnalysisReportResponse(
            status=result.status,
            message=result.data.get("message", "분석 보고서가 성공적으로 저장되었습니다."),
            data=result.data
        )

    except JSendError as e:
        logger.error(f"분석 보고서 저장 실패: {e.message}")
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        logger.error(f"분석 보고서 저장 중 예상치 못한 오류: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")


@router.get("/report/{analysis_report_idx}")
async def get_analysis_report(analysis_report_idx: int):
    """
    특정 분석 보고서 조회 API
    """
    try:
        logger.info(f"분석 보고서 조회 요청: analysis_report_idx={analysis_report_idx}")

        result = await analysis_service.get_analysis_report(analysis_report_idx)

        return result

    except JSendError as e:
        logger.error(f"분석 보고서 조회 실패: {e.message}")
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        logger.error(f"분석 보고서 조회 중 예상치 못한 오류: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")


@router.get("/user/{user_idx}/reports")
async def get_user_analysis_reports(
    user_idx: int,
    limit: int = Query(default=10, ge=1, le=100, description="조회할 보고서 수 (1-100)")
):
    """
    사용자의 분석 보고서 목록 조회 API
    """
    try:
        logger.info(f"사용자 분석 보고서 목록 조회 요청: user_idx={user_idx}, limit={limit}")

        result = await analysis_service.get_user_analysis_reports(user_idx, limit)

        return result

    except JSendError as e:
        logger.error(f"사용자 분석 보고서 목록 조회 실패: {e.message}")
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        logger.error(f"사용자 분석 보고서 목록 조회 중 예상치 못한 오류: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")


@router.get("/health")
async def health_check():
    """
    분석 서비스 헬스체크
    """
    return {
        "status": "healthy",
        "service": "analysis_service",
        "message": "분석 서비스가 정상적으로 작동 중입니다."
    }
