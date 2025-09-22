"""
차트 분석 조회 서비스
"""
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
import asyncpg

from src.common.utils.logger import set_logger
from src.config.database import database_config

logger = set_logger(__name__)

class AnalysisService:
    """차트 분석 조회 서비스"""

    async def _get_db_connection(self):
        """데이터베이스 연결"""
        return await asyncpg.connect(
            host=database_config.POSTGRESQL_DB_HOST,
            port=int(database_config.POSTGRESQL_DB_PORT),
            database=database_config.POSTGRESQL_DB_DATABASE,
            user=database_config.POSTGRESQL_DB_USER,
            password=database_config.POSTGRESQL_DB_PASSWORD
        )

    async def get_chart_analysis_by_tickers(
        self,
        tickers: List[str],
        hours_back: int = 24,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        특정 티커들의 차트 분석 결과 조회

        Args:
            tickers: 조회할 티커 리스트
            hours_back: 몇 시간 전부터 조회할지
            limit: 최대 조회 개수

        Returns:
            List[Dict]: 분석 결과 리스트
        """
        try:
            conn = await self._get_db_connection()
            try:
                # 시간 범위 계산 (timezone 정보 제거)
                now_utc = datetime.now(timezone.utc)
                start_time_naive = now_utc.replace(tzinfo=None) - timedelta(hours=hours_back)
                start_time = start_time_naive  # timezone 정보가 없는 datetime 객체

                # 티커 리스트를 SQL IN 절에 사용할 수 있도록 변환
                ticker_placeholders = ','.join([f'${i+1}' for i in range(len(tickers))])
                start_time_param = len(tickers) + 1
                limit_param = len(tickers) + 2

                query = f"""
                    SELECT
                        asset_symbol,
                        overall_score,
                        quant_score,
                        market_regime,
                        weight_snapshot,
                        indicator_scores,
                        full_analysis_data,
                        created_at,
                        expires_at
                    FROM chart_analysis_reports
                    WHERE asset_symbol IN ({ticker_placeholders})
                    AND created_at >= ${start_time_param}::timestamp
                    ORDER BY created_at DESC
                    LIMIT ${limit_param}
                """

                # 쿼리 실행 (파라미터 순서: tickers, start_time, limit)
                rows = await conn.fetch(query, *tickers, start_time, limit)

                # 결과를 딕셔너리로 변환
                results = []
                for row in rows:
                    result_dict = dict(row)
                    # JSONB 필드는 자동으로 파싱되므로 추가 처리 불필요
                    results.append(result_dict)

                logger.info(f"✅ 차트 분석 조회 성공: {len(results)}개 결과")
                return results

            finally:
                await conn.close()

        except Exception as e:
            logger.error(f"❌ 차트 분석 조회 실패: {str(e)}")
            raise