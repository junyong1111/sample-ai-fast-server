"""
간단한 차트 분석 Celery 태스크
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List

from celery import Celery
from src.scheduler.celery import app
from src.common.utils.logger import set_logger
from src.app.autotrading_v2.quantitative_service import QuantitativeServiceV2

logger = set_logger(__name__)

# 주요 코인 목록
MAJOR_COINS = [
    "BTC/USDT", "ETH/USDT", "XRP/USDT", "ADA/USDT",
    "SOL/USDT", "DOT/USDT", "MATIC/USDT", "AVAX/USDT"
]

async def save_to_database(market: str, analysis_data: Dict[str, Any], task_id: str) -> bool:
    """
    분석 결과를 데이터베이스에 저장 (asyncpg 사용)

    Args:
        market: 마켓 심볼
        analysis_data: 분석 데이터
        task_id: 태스크 ID

    Returns:
        bool: 저장 성공 여부
    """
    try:
        import asyncpg
        from src.config.database import database_config

        # 데이터베이스 연결
        conn = await asyncpg.connect(
            host=database_config.POSTGRESQL_DB_HOST,
            port=int(database_config.POSTGRESQL_DB_PORT),
            database=database_config.POSTGRESQL_DB_DATABASE,
            user=database_config.POSTGRESQL_DB_USER,
            password=database_config.POSTGRESQL_DB_PASSWORD
        )

        try:
            # 만료 시간 설정 (5분 후)
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

            query = """
                INSERT INTO chart_analysis_reports (
                    asset_symbol, overall_score, quant_score, market_regime, trading_signal,
                    weight_snapshot, indicator_scores, full_analysis_data, expires_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9
                )
                ON CONFLICT (asset_symbol, created_at)
                DO UPDATE SET
                    overall_score = EXCLUDED.overall_score,
                    quant_score = EXCLUDED.quant_score,
                    market_regime = EXCLUDED.market_regime,
                    trading_signal = EXCLUDED.trading_signal,
                    weight_snapshot = EXCLUDED.weight_snapshot,
                    indicator_scores = EXCLUDED.indicator_scores,
                    full_analysis_data = EXCLUDED.full_analysis_data,
                    expires_at = EXCLUDED.expires_at
            """

            # 가중치 스냅샷 생성
            weight_snapshot = {
                "regime_type": analysis_data.get('market_regime', 'unknown'),
                "regime_confidence": analysis_data.get('regime_confidence', 0.0),
                "adx_value": analysis_data.get('adx_value', 0.0),
                "analysis_timestamp": analysis_data.get('timestamp', datetime.now(timezone.utc).isoformat())
            }

            # 지표 점수들
            indicator_scores = {
                "rsi": analysis_data.get('rsi_value', 0.0),
                "macd": analysis_data.get('macd_value', 0.0),
                "adx": analysis_data.get('adx_value', 0.0)
            }

            await conn.execute(
                query,
                market,
                analysis_data.get('overall_score', 0.0),
                analysis_data.get('overall_score', 0.0),  # quant_score는 overall_score와 동일
                analysis_data.get('market_regime', 'unknown'),
                'HOLD',  # 기본값
                json.dumps(weight_snapshot),
                json.dumps(indicator_scores),
                json.dumps(analysis_data),
                expires_at
            )

            return True

        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"❌ [DB-{task_id}] 저장 실패: {market} - {str(e)}")
        return False

@app.task(bind=True, name='scheduler.tasks.simple_chart_analysis.analyze_major_coins')
def analyze_major_coins(self, timeframe: str = "minutes:60", count: int = 200, exchange: str = "binance"):
    """
    주요 코인 차트 분석 (간단 버전)

    Args:
        timeframe: 시간프레임
        count: 캔들 개수
        exchange: 거래소

    Returns:
        Dict[str, Any]: 분석 결과
    """
    task_id = self.request.id
    logger.info(f"🚀 [SIMPLE-{task_id}] 주요 코인 차트 분석 시작: {len(MAJOR_COINS)}개 코인")

    try:
        # QuantitativeServiceV2 인스턴스 생성
        service = QuantitativeServiceV2()

        results = {}
        success_count = 0

        # 비동기 함수 실행을 위한 루프 생성
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 각 코인별로 분석 (비동기 루프)
            for i, market in enumerate(MAJOR_COINS):
                try:
                    logger.info(f"📊 [SIMPLE-{task_id}] 분석 중: {market} ({i+1}/{len(MAJOR_COINS)})")

                    # 차트 분석 실행 (비동기)
                    result = loop.run_until_complete(service.analyze_market(
                        market=market,
                        timeframe=timeframe,
                        count=count,
                        exchange=exchange
                    ))

                    if result and result.get('status') == 'success':
                        # 간단한 데이터 추출
                        analysis = result.get('analysis', {})
                        detailed_data = result.get('detailed_data', {})

                        # 핵심 정보만 추출
                        simple_result = {
                            'market': market,
                            'overall_score': detailed_data.get('weighted_score', 0.0),  # weighted_score 사용
                            'market_regime': detailed_data.get('regime', 'unknown'),
                            'regime_confidence': detailed_data.get('regime_confidence', 0.0),
                            'adx_value': detailed_data.get('indicators', {}).get('adx', 0.0),
                            'rsi_value': detailed_data.get('indicators', {}).get('rsi', 0.0),
                            'macd_value': detailed_data.get('indicators', {}).get('macd', 0.0),
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        }

                        results[market] = simple_result
                        success_count += 1
                        logger.info(f"✅ [SIMPLE-{task_id}] 분석 완료: {market}")

                        # 데이터베이스에 저장
                        try:
                            loop.run_until_complete(save_to_database(market, simple_result, task_id))
                            logger.info(f"💾 [SIMPLE-{task_id}] DB 저장 완료: {market}")
                        except Exception as db_e:
                            logger.error(f"❌ [SIMPLE-{task_id}] DB 저장 실패: {market} - {str(db_e)}")
                    else:
                        logger.error(f"❌ [SIMPLE-{task_id}] 분석 실패: {market}")

                except Exception as e:
                    logger.error(f"❌ [SIMPLE-{task_id}] 분석 에러: {market} - {str(e)}")

        finally:
            loop.close()

        # 결과 요약
        result_summary = {
            'status': 'completed',
            'task_id': task_id,
            'total_markets': len(MAJOR_COINS),
            'success_count': success_count,
            'error_count': len(MAJOR_COINS) - success_count,
            'success_rate': success_count / len(MAJOR_COINS) if MAJOR_COINS else 0,
            'results': results,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        logger.info(f"🎯 [SIMPLE-{task_id}] 분석 완료: 성공 {success_count}/{len(MAJOR_COINS)}")
        return result_summary

    except Exception as e:
        logger.error(f"❌ [SIMPLE-{task_id}] 태스크 실행 실패: {str(e)}")
        return {
            'status': 'error',
            'task_id': task_id,
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

@app.task(name='scheduler.tasks.simple_chart_analysis.get_all_analyses')
def get_all_analyses() -> List[Dict[str, Any]]:
    """
    모든 분석 결과 조회 (asyncpg 사용)
    """
    try:
        import asyncio
        import asyncpg
        from src.config.database import database_config

        async def _fetch_data():
            # 데이터베이스 연결
            conn = await asyncpg.connect(
                host=database_config.POSTGRESQL_DB_HOST,
                port=int(database_config.POSTGRESQL_DB_PORT),
                database=database_config.POSTGRESQL_DB_DATABASE,
                user=database_config.POSTGRESQL_DB_USER,
                password=database_config.POSTGRESQL_DB_PASSWORD
            )

            try:
                query = """
                    SELECT * FROM chart_analysis_reports
                    WHERE expires_at > NOW()
                    ORDER BY created_at DESC
                """

                rows = await conn.fetch(query)
                results = []

                for row in rows:
                    result_dict = dict(row)
                    results.append(result_dict)

                return results

            finally:
                await conn.close()

        # 비동기 함수 실행
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_fetch_data())
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"❌ 분석 결과 조회 실패: {str(e)}")
        return []

@app.task(name='scheduler.tasks.simple_chart_analysis.health_check')
def health_check() -> Dict[str, Any]:
    """
    간단한 헬스 체크
    """
    return {
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'message': 'Simple chart analysis system is running'
    }
