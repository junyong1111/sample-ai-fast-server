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

def get_top_20_coins() -> List[str]:
    """
    ccxt를 통해 상위 20개 코인 목록을 가져옵니다.

    Returns:
        List[str]: 상위 20개 코인 심볼 리스트 (USDT 페어)
    """
    try:
        import ccxt

        # Binance 거래소 인스턴스 생성
        exchange = ccxt.binance({
            'apiKey': '',  # 공개 API만 사용
            'secret': '',
            'sandbox': False,
            'enableRateLimit': True,
        })

        # 모든 거래 가능한 심볼 가져오기
        markets = exchange.load_markets()

        # USDT 페어만 필터링하고 거래량 기준으로 정렬
        usdt_pairs = []
        for symbol, market in markets.items():
            if (market['quote'] == 'USDT' and
                market['active'] and
                market['type'] == 'spot' and
                market['base'] not in ['USDT', 'USDC', 'DAI', 'BUSD']):  # 스테이블코인 제외
                usdt_pairs.append(symbol)

        # 거래량 기준으로 정렬 (24시간 거래량)
        try:
            tickers = exchange.fetch_tickers(usdt_pairs)
            sorted_pairs = sorted(
                usdt_pairs,
                key=lambda x: tickers[x]['quoteVolume'] if x in tickers else 0,
                reverse=True
            )
            top_20 = sorted_pairs[:20]
        except:
            # 거래량 정렬 실패 시 기본 순서로 상위 20개
            top_20 = usdt_pairs[:20]

        logger.info(f"✅ ccxt를 통한 상위 20개 코인 목록 가져오기 성공: {len(top_20)}개")
        logger.info(f"📋 상위 5개 코인: {', '.join(top_20[:5])}")
        return top_20

    except Exception as e:
        logger.error(f"❌ ccxt를 통한 상위 20개 코인 목록 가져오기 실패: {str(e)}")
        return get_fallback_coins()

def get_fallback_coins() -> List[str]:
    """
    API 호출 실패 시 사용할 기본 코인 목록

    Returns:
        List[str]: 기본 코인 목록
    """
    return [
        "BTC/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT", "SOL/USDT",
        "ADA/USDT", "DOGE/USDT", "TRX/USDT", "AVAX/USDT", "LINK/USDT",
        "DOT/USDT", "MATIC/USDT", "LTC/USDT", "BCH/USDT", "UNI/USDT",
        "ATOM/USDT", "FIL/USDT", "XLM/USDT", "VET/USDT", "ICP/USDT"
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
                    asset_symbol, overall_score, quant_score, market_regime,
                    weight_snapshot, indicator_scores, full_analysis_data, expires_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8
                )
                ON CONFLICT (asset_symbol, created_at)
                DO UPDATE SET
                    overall_score = EXCLUDED.overall_score,
                    quant_score = EXCLUDED.quant_score,
                    market_regime = EXCLUDED.market_regime,
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

@app.task(bind=True, name='scheduler.tasks.simple_chart_analysis.analyze_top_20_coins')
def analyze_top_20_coins(self, timeframe: str = "minutes:60", count: int = 200, exchange: str = "binance"):
    """
    상위 20개 코인 차트 분석 (API를 통한 동적 코인 목록)

    Args:
        timeframe: 시간프레임
        count: 캔들 개수
        exchange: 거래소

    Returns:
        Dict[str, Any]: 분석 결과
    """
    task_id = self.request.id
    logger.info(f"🚀 [TOP20-{task_id}] 상위 20개 코인 차트 분석 시작")

    try:
        # QuantitativeServiceV2 인스턴스 생성
        service = QuantitativeServiceV2()

        results = {}
        success_count = 0
        error_count = 0

        # 비동기 함수 실행을 위한 루프 생성
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # ccxt를 통해 상위 20개 코인 목록 가져오기
            top_coins = get_top_20_coins()
            logger.info(f"📊 [TOP20-{task_id}] 분석 대상 코인: {len(top_coins)}개")
            logger.info(f"📋 [TOP20-{task_id}] 코인 목록: {', '.join(top_coins[:5])}...")

            # 각 코인별로 분석 (비동기 루프)
            for i, market in enumerate(top_coins):
                try:
                    logger.info(f"📊 [TOP20-{task_id}] 분석 중: {market} ({i+1}/{len(top_coins)})")

                    # 차트 분석 실행 (비동기)
                    result = loop.run_until_complete(service.analyze_market(
                        market=market,
                        timeframe=timeframe,
                        count=count,
                        exchange=exchange
                    ))

                    if result and result.get('status') == 'success':
                        # 간단한 데이터 추출
                        detailed_data = result.get('detailed_data', {})

                        # 핵심 정보만 추출
                        simple_result = {
                            'market': market,
                            'overall_score': detailed_data.get('weighted_score', 0.0),
                            'market_regime': detailed_data.get('regime', 'unknown'),
                            'regime_confidence': detailed_data.get('regime_confidence', 0.0),
                            'adx_value': detailed_data.get('indicators', {}).get('adx', 0.0),
                            'rsi_value': detailed_data.get('indicators', {}).get('rsi', 0.0),
                            'macd_value': detailed_data.get('indicators', {}).get('macd', 0.0),
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        }

                        results[market] = simple_result
                        success_count += 1
                        logger.info(f"✅ [TOP20-{task_id}] 분석 완료: {market}")

                        # 데이터베이스에 저장
                        try:
                            loop.run_until_complete(save_to_database(market, simple_result, task_id))
                            logger.info(f"💾 [TOP20-{task_id}] DB 저장 완료: {market}")
                        except Exception as db_e:
                            logger.error(f"❌ [TOP20-{task_id}] DB 저장 실패: {market} - {str(db_e)}")
                            error_count += 1
                    else:
                        logger.error(f"❌ [TOP20-{task_id}] 분석 실패: {market}")
                        error_count += 1

                except Exception as e:
                    logger.error(f"❌ [TOP20-{task_id}] 분석 에러: {market} - {str(e)}")
                    error_count += 1

        finally:
            loop.close()

        # 결과 요약
        result_summary = {
            'status': 'completed',
            'task_id': task_id,
            'total_markets': len(top_coins),
            'success_count': success_count,
            'error_count': error_count,
            'success_rate': success_count / len(top_coins) if top_coins else 0,
            'results': results,
            'coins_analyzed': top_coins,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        logger.info(f"🎯 [TOP20-{task_id}] 분석 완료: 성공 {success_count}/{len(top_coins)}")
        return result_summary

    except Exception as e:
        logger.error(f"❌ [TOP20-{task_id}] 전체 분석 실패: {str(e)}")
        return {
            'status': 'failed',
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
