"""
간단한 차트 분석 Celery 태스크
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List

from celery import Celery
from src.scheduler.celery import app as celery_app
from src.common.utils.logger import set_logger
from src.app.autotrading_v2.quantitative_service import QuantitativeServiceV2
from src.app.analysis.ai_service import AIAnalysisService

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

@celery_app.task(bind=True, name='scheduler.tasks.chart_analysis.analyze_top_20_coins')
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

@celery_app.task(name='scheduler.tasks.chart_analysis.get_all_analyses')
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

@celery_app.task(name='scheduler.tasks.chart_analysis.health_check')
def health_check() -> Dict[str, Any]:
    """
    간단한 헬스 체크
    """
    return {
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'message': 'Simple chart analysis system is running'
    }

@celery_app.task(name="scheduler.tasks.chart_analysis.analyze_top_20_coins_with_ai")
def analyze_top_20_coins_with_ai():
    """
    상위 20개 코인에 대한 AI 차트 분석 (1시간마다, 기존 데이터 활용)
    """
    try:
        logger.info("🤖 AI 차트 분석 스케줄러 시작")

        # 1. 최근 차트 분석 데이터 조회 (기존 데이터 활용)
        chart_data = get_recent_chart_analysis_data()

        if not chart_data:
            logger.warning("⚠️ 최근 차트 분석 데이터가 없습니다")
            return

        logger.info(f"📊 분석 대상 데이터: {len(chart_data)}개")

        # 2. AI 분석용 데이터 구조 변환
        coins_data = []
        chart_record_ids = []

        for record in chart_data:
            try:
                # 기존 차트 분석 데이터를 AI 분석용으로 변환
                coin_data = convert_chart_data_for_ai(record)
                coins_data.append(coin_data)
                chart_record_ids.append(record['id'])
                logger.info(f"✅ {record['asset_symbol']} 데이터 변환 완료")

            except Exception as e:
                logger.error(f"❌ {record.get('asset_symbol', 'Unknown')} 데이터 변환 실패: {str(e)}")

        # 3. AI 분석 실행 (다중 코인)
        if coins_data:
            # 동기 함수에서 비동기 함수 호출
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                ai_service = AIAnalysisService()
                ai_results = loop.run_until_complete(ai_service.analyze_multiple_coins_with_ai(coins_data))

                # 4. 가중치 스냅샷 수집
                weights_snapshot = loop.run_until_complete(ai_service._get_regime_weights())

                # 5. AI 분석 결과를 종합 테이블에 저장
                loop.run_until_complete(save_ai_analysis_to_database(
                    ai_results=ai_results,
                    chart_record_ids=chart_record_ids,
                    risk_record_ids=[],
                    social_record_ids=[],
                    total_coins=len(coins_data),
                    weights_snapshot=weights_snapshot
                ))
                logger.info(f"🎉 AI 차트 분석 완료: {len(coins_data)}개 코인")
            finally:
                loop.close()
        else:
            logger.warning("⚠️ 변환된 차트 데이터가 없습니다")

    except Exception as e:
        logger.error(f"❌ AI 차트 분석 스케줄러 실패: {str(e)}")
        raise

def get_recent_chart_analysis_data() -> List[Dict[str, Any]]:
    """
    최근 차트 분석 데이터 조회 (AI 분석용)
    """
    import asyncio
    import asyncpg
    from src.config.database import database_config
    from datetime import datetime, timedelta, timezone

    async def _get_data():
        conn = await asyncpg.connect(
            host=database_config.POSTGRESQL_DB_HOST,
            port=int(database_config.POSTGRESQL_DB_PORT),
            database=database_config.POSTGRESQL_DB_DATABASE,
            user=database_config.POSTGRESQL_DB_USER,
            password=database_config.POSTGRESQL_DB_PASSWORD
        )

        try:
            # 최근 1시간 내의 차트 분석 데이터 조회
            query = """
                SELECT id, asset_symbol, quant_score, overall_score, market_regime, created_at
                FROM chart_analysis_reports
                WHERE created_at >= NOW() - INTERVAL '1 hour'
                ORDER BY created_at DESC
                LIMIT 20
            """

            rows = await conn.fetch(query)
            return [dict(row) for row in rows]

        finally:
            await conn.close()

    # 동기 함수에서 비동기 함수 호출
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_get_data())
    finally:
        loop.close()

def convert_chart_data_for_ai(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    기존 차트 분석 데이터를 AI 분석용으로 변환
    """
    try:
        # 기본 데이터로 AI 분석용 구조 생성
        return {
            "market": record.get('asset_symbol', 'Unknown'),
            "timeframe": "minutes:60",
            "exchange": "binance",
            "indicators": {
                "adx": 0,  # 기본값
                "rsi": 0,
                "macd": 0,
                "macd_histogram": 0,
                "bb_pct_b": 0,
                "volume_z_score": 0,
                "ema_20": 0,
                "ema_50": 0,
                "ema_200": 0
            },
            "scores": {
                "rsi": 0,
                "macd": 0,
                "bollinger": 0,
                "volume": 0,
                "momentum": 0
            },
            "regime_info": {
                "regime": record.get('market_regime', 'range'),
                "confidence": 0.5,
                "trend_strength": 'weak'
            },
            "quant_score": record.get('quant_score', 0),
            "overall_score": record.get('overall_score', 0)
        }
    except Exception as e:
        logger.error(f"❌ 데이터 변환 실패: {str(e)}")
        return {
            "market": record.get('asset_symbol', 'Unknown'),
            "timeframe": "minutes:60",
            "exchange": "binance",
            "indicators": {},
            "scores": {},
            "regime_info": {"regime": "range", "confidence": 0.5, "trend_strength": "weak"},
            "quant_score": 0,
            "overall_score": 0
        }

async def save_ai_analysis_to_database(
    ai_results: Dict[str, Any],
    chart_record_ids: List[int],
    risk_record_ids: List[int],
    social_record_ids: List[int],
    total_coins: int,
    weights_snapshot: Dict[str, Any] = None
):
    """
    AI 종합 분석 결과를 데이터베이스에 저장
    """
    import asyncpg
    from src.config.database import database_config
    from datetime import datetime, timedelta, timezone
    import json

    try:
        conn = await asyncpg.connect(
            host=database_config.POSTGRESQL_DB_HOST,
            port=int(database_config.POSTGRESQL_DB_PORT),
            database=database_config.POSTGRESQL_DB_DATABASE,
            user=database_config.POSTGRESQL_DB_USER,
            password=database_config.POSTGRESQL_DB_PASSWORD
        )

        try:
            analysis_results = ai_results.get('analysis_results', {})
            summary = ai_results.get('summary', {})

            # 데이터 소스 정보 구성
            data_sources = {
                "chart_data": {
                    "source_table": "chart_analysis_reports",
                    "record_ids": chart_record_ids,
                    "total_records": len(chart_record_ids),
                    "timeframe": "minutes:60",
                    "exchange": "binance"
                },
                "risk_data": {
                    "source_table": "risk_analysis_reports",
                    "record_ids": risk_record_ids,
                    "total_records": len(risk_record_ids),
                    "analysis_type": "daily"
                },
                "social_data": {
                    "source_table": "social_analysis_reports",
                    "record_ids": social_record_ids,
                    "total_records": len(social_record_ids),
                    "platforms": ["reddit", "twitter"]
                },
                "weights_snapshot": {
                    "source": "information_service",
                    "api_endpoint": "/api/v2/information/weights/chart",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "description": "AI 분석에 사용된 레짐별 가중치 스냅샷",
                    "weights_data": weights_snapshot or {}
                }
            }

            # 만료 시간 설정 (2시간)
            expires_at = datetime.now(timezone.utc) + timedelta(hours=2)

            query = """
                INSERT INTO ai_analysis_reports
                (analysis_timestamp, chart_analysis, risk_analysis, social_analysis,
                 final_analysis, data_sources, total_coins, expires_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """

            await conn.execute(
                query,
                datetime.now(timezone.utc),
                json.dumps(analysis_results),  # chart_analysis
                json.dumps({}),  # risk_analysis (빈 객체)
                json.dumps({}),  # social_analysis (빈 객체)
                json.dumps({}),  # final_analysis (빈 객체 - 별도 에이전트가 처리)
                json.dumps(data_sources),  # data_sources
                total_coins,
                expires_at
            )

            logger.info(f"✅ AI 종합 분석 결과 저장 완료: {total_coins}개 코인")

        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"❌ AI 종합 분석 저장 실패: {str(e)}")
        raise

async def save_ai_chart_analysis_to_database(ai_results: Dict[str, Any], total_coins: int):
    """
    AI 차트 분석 결과를 JSONB 형태로 데이터베이스에 저장
    """
    import asyncpg
    from src.config.database import database_config
    from datetime import datetime, timedelta, timezone
    import json

    try:
        conn = await asyncpg.connect(
            host=database_config.POSTGRESQL_DB_HOST,
            port=int(database_config.POSTGRESQL_DB_PORT),
            database=database_config.POSTGRESQL_DB_DATABASE,
            user=database_config.POSTGRESQL_DB_USER,
            password=database_config.POSTGRESQL_DB_PASSWORD
        )

        try:
            analysis_results = ai_results.get('analysis_results', {})
            summary = ai_results.get('summary', {})

            # 통계 계산
            trend_coins = summary.get('trend_coins', 0)
            range_coins = summary.get('range_coins', 0)
            average_confidence = summary.get('average_confidence', 0.0)

            # JSONB 데이터 준비
            analysis_data_json = json.dumps(analysis_results)

            # 만료 시간 설정 (2시간)
            expires_at = datetime.now(timezone.utc) + timedelta(hours=2)

            query = """
                INSERT INTO ai_chart_analysis_reports
                (analysis_timestamp, analysis_data, total_coins, trend_coins, range_coins, average_confidence, expires_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """

            await conn.execute(
                query,
                datetime.now(timezone.utc),
                analysis_data_json,
                total_coins,
                trend_coins,
                range_coins,
                average_confidence,
                expires_at
            )

            logger.info(f"✅ AI 차트 분석 결과 저장 완료: {total_coins}개 코인 | 추세: {trend_coins} | 횡보: {range_coins}")

        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"❌ AI 차트 분석 저장 실패: {str(e)}")
        raise
