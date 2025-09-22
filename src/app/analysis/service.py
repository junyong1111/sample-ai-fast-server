"""
차트 분석 조회 서비스
"""
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
import asyncpg

from src.common.utils.logger import set_logger
from src.config.database import database_config
from src.app.autotrading_v2.quantitative_service import QuantitativeServiceV2

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

    async def get_chart_data_for_ai(
        self,
        market: str,
        timeframe: str = "minutes:60",
        count: int = 200,
        exchange: str = "binance"
    ) -> Dict[str, Any]:
        """
        AI 분석을 위한 차트 데이터 조회

        Args:
            market: 마켓 심볼 (예: BTC/USDT)
            timeframe: 시간 프레임 (예: minutes:60)
            count: 캔들 개수
            exchange: 거래소

        Returns:
            AI 분석용 차트 데이터
        """
        try:
            # QuantitativeServiceV2를 사용하여 실시간 차트 분석
            quantitative_service = QuantitativeServiceV2()

            # 차트 분석 실행
            analysis_result = await quantitative_service.analyze_market(
                market=market,
                timeframe=timeframe,
                count=count,
                exchange=exchange
            )

            if not analysis_result or analysis_result.get('status') != 'success':
                raise Exception(f"차트 분석 실패: {analysis_result}")

            # AI 분석에 필요한 데이터 추출
            detailed_data = analysis_result.get('detailed_data', {})
            indicators = detailed_data.get('indicators', {})
            scores = detailed_data.get('scores', {})
            regime_info = detailed_data.get('regime_info', {})

            # AI 분석용 데이터 구조 생성
            chart_data = {
                "market": market,
                "timeframe": timeframe,
                "exchange": exchange,
                "indicators": {
                    "adx": indicators.get('adx', 0),
                    "rsi": indicators.get('rsi', 0),
                    "macd": indicators.get('macd', 0),
                    "macd_histogram": indicators.get('macd_histogram', 0),
                    "bb_pct_b": indicators.get('bb_pct_b', 0),
                    "volume_z_score": indicators.get('volume_z_score', 0),
                    "ema_20": indicators.get('ema_20', 0),
                    "ema_50": indicators.get('ema_50', 0),
                    "ema_200": indicators.get('ema_200', 0)
                },
                "scores": {
                    "rsi": scores.get('rsi', 0),
                    "macd": scores.get('macd', 0),
                    "bollinger": scores.get('bollinger', 0),
                    "volume": scores.get('volume', 0),
                    "momentum": scores.get('momentum', 0)
                },
                "regime_info": {
                    "regime": regime_info.get('regime', 'range'),
                    "confidence": regime_info.get('confidence', 0.5),
                    "trend_strength": regime_info.get('trend_strength', 'weak')
                },
                "metadata": {
                    "data_points": detailed_data.get('metadata', {}).get('data_points', count),
                    "config": detailed_data.get('metadata', {}).get('config', {})
                }
            }

            logger.info(f"✅ AI용 차트 데이터 조회 완료: {market}")
            return chart_data

        except Exception as e:
            logger.error(f"❌ AI용 차트 데이터 조회 실패: {str(e)}")
            raise