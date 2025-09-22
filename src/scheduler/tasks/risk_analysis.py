"""
리스크 분석 스케줄러 태스크
"""
import asyncio
import asyncpg
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone
import json

from src.common.utils.logger import set_logger
from src.scheduler.celery import app as celery_app
from src.app.autotrading_v2.risk_service import RiskAnalysisService

logger = set_logger(__name__)

@celery_app.task(name="scheduler.tasks.risk_analysis.analyze_top_20_risk")
def analyze_top_20_risk():
    """
    상위 20개 코인에 대한 리스크 분석 (1시간마다)
    """
    try:
        logger.info("🚨 리스크 분석 스케줄러 시작")

        # 1. 상위 20개 코인 조회
        top_coins = get_top_20_coins()
        logger.info(f"📊 분석 대상 코인: {len(top_coins)}개")

        # 2. 리스크 분석 실행
        risk_service = RiskAnalysisService()
        results = []

        for coin in top_coins:
            try:
                # 동기 함수에서 비동기 함수 호출
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    risk_result = loop.run_until_complete(risk_service.analyze_risk(
                        market=coin,
                        analysis_type="daily",
                        days_back=90,
                        personality="conservative",
                        include_analysis=True
                    ))

                    if risk_result and risk_result.get('status') == 'success':
                        # 데이터베이스에 저장
                        loop.run_until_complete(save_risk_analysis_to_database(coin, risk_result))
                        results.append({
                            "market": coin,
                            "status": "success",
                            "risk_score": risk_result.get('risk_score', 0),
                            "risk_level": risk_result.get('risk_level', 'UNKNOWN')
                        })
                        logger.info(f"✅ {coin} 리스크 분석 완료")
                    else:
                        logger.warning(f"⚠️ {coin} 리스크 분석 실패")

                finally:
                    loop.close()

            except Exception as e:
                logger.error(f"❌ {coin} 리스크 분석 실패: {str(e)}")
                results.append({
                    "market": coin,
                    "status": "error",
                    "error": str(e)
                })

        logger.info(f"🎉 리스크 분석 완료: {len(results)}개 코인")
        return {
            "status": "completed",
            "total_markets": len(top_coins),
            "success_count": len([r for r in results if r.get('status') == 'success']),
            "error_count": len([r for r in results if r.get('status') == 'error']),
            "results": results
        }

    except Exception as e:
        logger.error(f"❌ 리스크 분석 스케줄러 실패: {str(e)}")
        raise

@celery_app.task(name="scheduler.tasks.risk_analysis.analyze_top_20_risk_with_ai")
def analyze_top_20_risk_with_ai():
    """
    상위 20개 코인에 대한 AI 리스크 분석 (1시간마다, 기존 데이터 활용)
    """
    try:
        logger.info("🤖 AI 리스크 분석 스케줄러 시작")

        # 1. 최근 리스크 분석 데이터 조회 (기존 데이터 활용)
        risk_data = get_recent_risk_analysis_data()

        if not risk_data:
            logger.warning("⚠️ 최근 리스크 분석 데이터가 없습니다")
            return

        logger.info(f"📊 분석 대상 데이터: {len(risk_data)}개")

        # 2. AI 분석용 데이터 구조 변환
        coins_data = []
        risk_record_ids = []

        for record in risk_data:
            try:
                # 기존 리스크 분석 데이터를 AI 분석용으로 변환
                coin_data = convert_risk_data_for_ai(record)
                coins_data.append(coin_data)
                risk_record_ids.append(record['id'])
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
                from src.app.analysis.ai_service import AIAnalysisService
                ai_service = AIAnalysisService()
                ai_results = loop.run_until_complete(ai_service.analyze_multiple_coins_risk_with_ai(coins_data))

                # 4. 가중치 스냅샷 수집
                weights_snapshot = loop.run_until_complete(ai_service._get_regime_weights())

                # 5. AI 분석 결과를 종합 테이블에 저장
                loop.run_until_complete(save_ai_analysis_to_database(
                    ai_results=ai_results,
                    chart_record_ids=[],
                    risk_record_ids=risk_record_ids,
                    social_record_ids=[],
                    total_coins=len(coins_data),
                    weights_snapshot=weights_snapshot
                ))
                logger.info(f"🎉 AI 리스크 분석 완료: {len(coins_data)}개 코인")
            finally:
                loop.close()
        else:
            logger.warning("⚠️ 변환된 리스크 데이터가 없습니다")

    except Exception as e:
        logger.error(f"❌ AI 리스크 분석 스케줄러 실패: {str(e)}")
        raise

def get_top_20_coins() -> List[str]:
    """
    상위 20개 코인 목록 조회 (ccxt 사용)
    """
    try:
        import ccxt

        # 바이낸스 거래소 초기화
        exchange = ccxt.binance({
            'apiKey': '',
            'secret': '',
            'sandbox': False,
            'enableRateLimit': True,
        })

        # 24시간 통계 조회
        tickers = exchange.fetch_tickers()

        # USDT 페어만 필터링하고 거래량 기준으로 정렬
        usdt_pairs = []
        for symbol, ticker in tickers.items():
            if symbol.endswith('/USDT') and ticker['quoteVolume'] and float(ticker['quoteVolume']) > 0:
                usdt_pairs.append((symbol, ticker['quoteVolume']))

        # 거래량 기준으로 정렬하고 상위 20개 선택
        usdt_pairs.sort(key=lambda x: x[1], reverse=True)
        top_20 = [pair[0] for pair in usdt_pairs[:20]]

        logger.info(f"✅ ccxt를 통한 상위 20개 코인 목록 가져오기 성공: {len(top_20)}개")
        logger.info(f"📋 상위 5개 코인: {', '.join(top_20[:5])}")

        return top_20

    except Exception as e:
        logger.error(f"❌ 상위 20개 코인 목록 조회 실패: {str(e)}")
        # 기본 코인 목록 반환
        return [
            "BTC/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT",
            "SOL/USDT", "DOGE/USDT", "TRX/USDT", "AVAX/USDT", "LINK/USDT",
            "DOT/USDT", "MATIC/USDT", "LTC/USDT", "BCH/USDT", "UNI/USDT",
            "ATOM/USDT", "FIL/USDT", "XLM/USDT", "VET/USDT", "ICP/USDT"
        ]

def get_recent_risk_analysis_data() -> List[Dict[str, Any]]:
    """
    최근 리스크 분석 데이터 조회 (AI 분석용)
    """
    import asyncio
    import asyncpg
    from src.config.database import database_config

    async def _get_data():
        conn = await asyncpg.connect(
            host=database_config.POSTGRESQL_DB_HOST,
            port=int(database_config.POSTGRESQL_DB_PORT),
            database=database_config.POSTGRESQL_DB_DATABASE,
            user=database_config.POSTGRESQL_DB_USER,
            password=database_config.POSTGRESQL_DB_PASSWORD
        )

        try:
            # 최근 1시간 내의 리스크 분석 데이터 조회
            query = """
                SELECT id, asset_symbol, risk_score, market_risk_level,
                       risk_off_signal, confidence, created_at
                FROM risk_analysis_reports
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

def convert_risk_data_for_ai(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    기존 리스크 분석 데이터를 AI 분석용으로 변환
    """
    try:
        # Decimal 타입을 float로 변환
        risk_score = record.get('risk_score', 0)
        if hasattr(risk_score, '__float__'):
            risk_score = float(risk_score)

        confidence = record.get('confidence', 0.5)
        if hasattr(confidence, '__float__'):
            confidence = float(confidence)

        return {
            "market": record.get('asset_symbol', 'Unknown'),
            "analysis_type": "daily",
            "days_back": 90,
            "personality": "conservative",
            "risk_score": risk_score,
            "risk_level": record.get('market_risk_level', 'UNKNOWN'),
            "risk_off_signal": record.get('risk_off_signal', False),
            "confidence": confidence
        }
    except Exception as e:
        logger.error(f"❌ 데이터 변환 실패: {str(e)}")
        return {
            "market": record.get('asset_symbol', 'Unknown'),
            "analysis_type": "daily",
            "days_back": 90,
            "personality": "conservative",
            "risk_score": 0,
            "risk_level": "UNKNOWN",
            "risk_off_signal": False,
            "confidence": 0.5
        }

async def save_risk_analysis_to_database(market: str, risk_result: Dict[str, Any]):
    """
    리스크 분석 결과를 데이터베이스에 저장
    """
    import asyncpg
    from src.config.database import database_config
    from datetime import datetime, timedelta, timezone

    try:
        conn = await asyncpg.connect(
            host=database_config.POSTGRESQL_DB_HOST,
            port=int(database_config.POSTGRESQL_DB_PORT),
            database=database_config.POSTGRESQL_DB_DATABASE,
            user=database_config.POSTGRESQL_DB_USER,
            password=database_config.POSTGRESQL_DB_PASSWORD
        )

        try:
            # 만료 시간 설정 (1시간)
            expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

            query = """
                INSERT INTO risk_analysis_reports
                (asset_symbol, risk_score, market_risk_level, risk_off_signal,
                 confidence, risk_indicators, correlation_analysis, full_analysis_data,
                 created_at, expires_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """

            await conn.execute(
                query,
                market,
                risk_result.get('risk_score', 0),
                risk_result.get('risk_level', 'UNKNOWN'),
                risk_result.get('risk_off_signal', False),
                risk_result.get('confidence', 0.5),
                json.dumps(risk_result.get('risk_indicators', {})),
                json.dumps(risk_result.get('correlation_analysis', {})),
                json.dumps(risk_result),
                datetime.now(timezone.utc),
                expires_at
            )

            logger.info(f"✅ 리스크 분석 결과 저장 완료: {market}")

        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"❌ 리스크 분석 저장 실패: {str(e)}")
        raise

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
                    "weights_data": weights_snapshot if weights_snapshot is not None else {}
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
                json.dumps({}),  # chart_analysis (빈 객체)
                json.dumps(analysis_results),  # risk_analysis
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