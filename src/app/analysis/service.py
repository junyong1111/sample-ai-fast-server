"""
분석 보고서 관련 서비스
"""

from typing import Optional, List
from src.app.analysis.models import AnalysisReportRequest, AnalysisReportResponse, AnalysisReportData
from src.app.analysis.repository import AnalysisRepository
from src.common.utils.response import JSendResponse
from src.common.error import JSendError, ErrorCode
from src.package.db import connection


class AnalysisService:
    """분석 보고서 서비스"""

    def __init__(self, logger):
        self.logger = logger
        self.analysis_repository = AnalysisRepository(logger)

    async def save_analysis_report(self, request: AnalysisReportRequest) -> JSendResponse:
        """분석 보고서 저장"""
        try:
            self.logger.info(f"분석 보고서 저장 시작: user_idx={request.user_idx}")

            async with connection() as session:
                analysis_report_idx = await self.analysis_repository.save_analysis_report(
                    session=session,
                    request=request
                )

            self.logger.info(f"분석 보고서 저장 성공: analysis_report_idx={analysis_report_idx}")

            return JSendResponse(
                status="success",
                data={
                    "analysis_report_idx": analysis_report_idx,
                    "message": "분석 보고서가 성공적으로 저장되었습니다."
                }
            )

        except Exception as e:
            self.logger.error(f"분석 보고서 저장 실패: {e}")
            raise JSendError(
                code=ErrorCode.Common.DEFAULT_ERROR[0],
                message=f"분석 보고서 저장 중 오류가 발생했습니다: {str(e)}"
            )

    async def get_analysis_report(self, analysis_report_idx: int) -> JSendResponse:
        """분석 보고서 조회"""
        try:
            self.logger.info(f"분석 보고서 조회 시작: analysis_report_idx={analysis_report_idx}")

            async with connection() as session:
                report = await self.analysis_repository.get_analysis_report(
                    session=session,
                    analysis_report_idx=analysis_report_idx
                )

            if not report:
                raise JSendError(
                    code=ErrorCode.Common.NOT_FOUND[0],
                    message="분석 보고서를 찾을 수 없습니다."
                )

            self.logger.info(f"분석 보고서 조회 성공: analysis_report_idx={analysis_report_idx}")

            return JSendResponse(
                status="success",
                data=report.dict()
            )

        except JSendError:
            raise
        except Exception as e:
            self.logger.error(f"분석 보고서 조회 실패: {e}")
            raise JSendError(
                code=ErrorCode.Common.DEFAULT_ERROR[0],
                message=f"분석 보고서 조회 중 오류가 발생했습니다: {str(e)}"
            )

    async def get_user_analysis_reports(self, user_idx: int, limit: int = 10) -> JSendResponse:
        """사용자의 분석 보고서 목록 조회"""
        try:
            self.logger.info(f"사용자 분석 보고서 목록 조회 시작: user_idx={user_idx}, limit={limit}")

            async with connection() as session:
                reports = await self.analysis_repository.get_user_analysis_reports(
                    session=session,
                    user_idx=user_idx,
                    limit=limit
                )

            self.logger.info(f"사용자 분석 보고서 목록 조회 성공: count={len(reports)}")

            return JSendResponse(
                status="success",
                data={
                    "reports": [report.dict() for report in reports],
                    "count": len(reports)
                }
            )

        except Exception as e:
            self.logger.error(f"사용자 분석 보고서 목록 조회 실패: {e}")
            raise JSendError(
                code=ErrorCode.Common.DEFAULT_ERROR[0],
                message=f"사용자 분석 보고서 목록 조회 중 오류가 발생했습니다: {str(e)}"
            )
