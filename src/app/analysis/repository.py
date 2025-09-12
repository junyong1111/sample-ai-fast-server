"""
분석 보고서 관련 데이터베이스 레포지토리
"""

import json
from typing import Optional, Dict, Any
from asyncpg import Connection
from src.app.analysis.models import AnalysisReportRequest, AnalysisReportData


class AnalysisRepository:
    """분석 보고서 레포지토리"""

    def __init__(self, logger):
        self.logger = logger

    async def save_analysis_report(
        self,
        session: Connection,
        request: AnalysisReportRequest
    ) -> int:
        """분석 보고서 저장"""
        try:
            query = """
                INSERT INTO analysis_reports (
                    user_idx,
                    market_regime,
                    used_regime_weights,
                    quant_report,
                    social_report,
                    risk_report,
                    analyst_summary
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7
                ) RETURNING idx
            """

            result = await session.fetchval(
                query,
                request.user_idx,
                request.market_regime,
                json.dumps(request.used_regime_weights) if request.used_regime_weights else None,
                json.dumps(request.quant_report) if request.quant_report else None,
                json.dumps(request.social_report) if request.social_report else None,
                json.dumps(request.risk_report) if request.risk_report else None,
                json.dumps(request.analyst_summary) if request.analyst_summary else None
            )

            self.logger.info(f"분석 보고서 저장 완료: analysis_report_idx={result}")
            return result

        except Exception as e:
            self.logger.error(f"분석 보고서 저장 실패: {e}")
            raise

    async def get_analysis_report(
        self,
        session: Connection,
        analysis_report_idx: int
    ) -> Optional[AnalysisReportData]:
        """분석 보고서 조회"""
        try:
            query = """
                SELECT
                    idx,
                    user_idx,
                    timestamp,
                    market_regime,
                    used_regime_weights,
                    quant_report,
                    social_report,
                    risk_report,
                    analyst_summary
                FROM analysis_reports
                WHERE idx = $1
            """

            result = await session.fetchrow(query, analysis_report_idx)

            if not result:
                return None

            return AnalysisReportData(
                idx=result['idx'],
                user_idx=result['user_idx'],
                timestamp=result['timestamp'],
                market_regime=result['market_regime'],
                used_regime_weights=result['used_regime_weights'],
                quant_report=result['quant_report'],
                social_report=result['social_report'],
                risk_report=result['risk_report'],
                analyst_summary=result['analyst_summary']
            )

        except Exception as e:
            self.logger.error(f"분석 보고서 조회 실패: {e}")
            raise

    async def get_user_analysis_reports(
        self,
        session: Connection,
        user_idx: int,
        limit: int = 10
    ) -> list[AnalysisReportData]:
        """사용자의 분석 보고서 목록 조회"""
        try:
            query = """
                SELECT
                    idx,
                    user_idx,
                    timestamp,
                    market_regime,
                    used_regime_weights,
                    quant_report,
                    social_report,
                    risk_report,
                    analyst_summary
                FROM analysis_reports
                WHERE user_idx = $1
                ORDER BY timestamp DESC
                LIMIT $2
            """

            results = await session.fetch(query, user_idx, limit)

            return [
                AnalysisReportData(
                    idx=row['idx'],
                    user_idx=row['user_idx'],
                    timestamp=row['timestamp'],
                    market_regime=row['market_regime'],
                    used_regime_weights=row['used_regime_weights'],
                    quant_report=row['quant_report'],
                    social_report=row['social_report'],
                    risk_report=row['risk_report'],
                    analyst_summary=row['analyst_summary']
                )
                for row in results
            ]

        except Exception as e:
            self.logger.error(f"사용자 분석 보고서 목록 조회 실패: {e}")
            raise
