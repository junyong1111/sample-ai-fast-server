"""
간단한 리스크 분석 스케줄러
1시간마다 상위 20개 코인에 대한 리스크 분석을 실행하고 데이터베이스에 저장
"""

import asyncio
import json
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from celery import Celery
import ccxt

from src.common.utils.logger import set_logger
from src.config.database import database_config
from src.app.autotrading_v2.risk_service import RiskAnalysisService
import ccxt
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

logger = set_logger(__name__)

# Celery 앱 인스턴스 (celery.py에서 가져옴)
from src.scheduler.celery import app as celery_app

def get_top_20_coins():
    """ccxt를 사용하여 상위 20개 코인 조회"""
    try:
        exchange = ccxt.binance()
        markets = exchange.load_markets()

        # USDT 페어만 필터링하고 거래량 기준으로 정렬
        usdt_pairs = []
        for symbol, market in markets.items():
            if market['quote'] == 'USDT' and market['active']:
                try:
                    ticker = exchange.fetch_ticker(symbol)
                    if ticker['quoteVolume'] and ticker['quoteVolume'] > 0:
                        usdt_pairs.append({
                            'symbol': symbol,
                            'volume': ticker['quoteVolume']
                        })
                except:
                    continue

        # 거래량 기준으로 정렬하고 상위 20개 선택
        usdt_pairs.sort(key=lambda x: x['volume'], reverse=True)
        top_20 = [pair['symbol'] for pair in usdt_pairs[:20]]

        logger.info(f"✅ 상위 20개 코인 조회 완료: {len(top_20)}개")
        return top_20
    except Exception as e:
        logger.error(f"❌ 상위 코인 조회 실패: {str(e)}")
        # 기본값 반환
        return [
            "BTC/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT",
            "SOL/USDT", "DOGE/USDT", "DOT/USDT", "AVAX/USDT", "MATIC/USDT",
            "LINK/USDT", "UNI/USDT", "LTC/USDT", "ATOM/USDT", "XLM/USDT",
            "BCH/USDT", "FIL/USDT", "TRX/USDT", "ETC/USDT", "ALGO/USDT"
        ]

async def analyze_individual_coin_risk(coin_symbol: str, risk_service: RiskAnalysisService, days_back: int = 90) -> Dict[str, Any]:
    """
    개별 코인별 고유 리스크 특성을 고려한 분석
    """
    try:
        # 1. 글로벌 시장 리스크 분석 (기존)
        global_risk = await risk_service.analyze_risk(
            market=coin_symbol,
            analysis_type="daily",
            days_back=days_back,
            personality="neutral",
            include_analysis=False  # AI 분석 비활성화
        )

        # 2. 개별 코인 변동성 분석
        coin_volatility = await analyze_coin_volatility(coin_symbol, days_back)

        # 3. 코인별 리스크 등급 조정
        adjusted_risk = adjust_risk_for_coin(global_risk, coin_volatility, coin_symbol)

        return adjusted_risk

    except Exception as e:
        logger.error(f"❌ {coin_symbol} 개별 리스크 분석 실패: {str(e)}")
        # 실패시 기본 글로벌 리스크 반환
        return await risk_service.analyze_risk(
            market=coin_symbol,
            analysis_type="daily",
            days_back=days_back,
            personality="neutral",
            include_analysis=False
        )

async def analyze_coin_volatility(coin_symbol: str, days_back: int) -> Dict[str, float]:
    """
    개별 코인의 변동성 특성 분석
    """
    try:
        exchange = ccxt.binance()

        # 최근 데이터 수집
        since = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)
        ohlcv = exchange.fetch_ohlcv(coin_symbol, '1d', since=since, limit=days_back)

        if len(ohlcv) < 30:  # 최소 30일 데이터 필요
            return {"volatility_7d": 0.0, "volatility_30d": 0.0, "max_drawdown": 0.0, "sharpe_ratio": 0.0}

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['returns'] = df['close'].pct_change().dropna()

        # 7일 변동성
        volatility_7d = df['returns'].tail(7).std() * np.sqrt(365) * 100

        # 30일 변동성
        volatility_30d = df['returns'].tail(30).std() * np.sqrt(365) * 100

        # 최대 낙폭 (Max Drawdown)
        cumulative = (1 + df['returns']).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = abs(drawdown.min()) * 100

        # 샤프 비율 (연간화)
        sharpe_ratio = (df['returns'].mean() * 365) / (df['returns'].std() * np.sqrt(365)) if df['returns'].std() > 0 else 0

        return {
            "volatility_7d": float(volatility_7d),
            "volatility_30d": float(volatility_30d),
            "max_drawdown": float(max_drawdown),
            "sharpe_ratio": float(sharpe_ratio)
        }

    except Exception as e:
        logger.error(f"❌ {coin_symbol} 변동성 분석 실패: {str(e)}")
        return {"volatility_7d": 0.0, "volatility_30d": 0.0, "max_drawdown": 0.0, "sharpe_ratio": 0.0}

def adjust_risk_for_coin(global_risk: Dict[str, Any], coin_volatility: Dict[str, float], coin_symbol: str) -> Dict[str, Any]:
    """
    하이브리드 리스크 분석: 글로벌 리스크 + 개별 코인 특성
    """
    try:
        # 1. 글로벌 리스크 베이스라인
        base_risk_score = global_risk.get('analysis', {}).get('risk_indicators', {}).get('overall_risk_score', 50.0)
        global_risk_level = global_risk.get('risk_grade', 'LOW')

        # 2. 개별 코인 변동성 특성
        volatility_30d = coin_volatility.get('volatility_30d', 0.0)
        max_drawdown = coin_volatility.get('max_drawdown', 0.0)
        sharpe_ratio = coin_volatility.get('sharpe_ratio', 0.0)

        # 3. 코인별 리스크 가중치 (대장주 vs 알트코인)
        coin_weight = get_coin_risk_weight(coin_symbol)

        # 4. 변동성 기반 조정 계수 (더 보수적으로)
        volatility_factor = min(1.0 + (volatility_30d - 30.0) / 100.0, 2.0)  # 30% 기준으로 조정
        drawdown_factor = min(1.0 + max_drawdown / 50.0, 2.0)  # 50% 낙폭 기준
        sharpe_factor = max(0.7, min(1.3, 1.0 - sharpe_ratio / 10.0))  # 샤프 비율 보수적 반영

        # 5. 최종 리스크 점수 계산 (글로벌 베이스 + 코인 특성)
        adjusted_risk_score = base_risk_score * volatility_factor * drawdown_factor * sharpe_factor * coin_weight

        # 6. 리스크 등급 결정 (글로벌 리스크를 고려한 범위 내에서)
        if global_risk_level == "LOW":
            if adjusted_risk_score < 25:
                risk_level = "LOW"
            elif adjusted_risk_score < 45:
                risk_level = "MEDIUM"
            else:
                risk_level = "HIGH"
        elif global_risk_level == "MEDIUM":
            if adjusted_risk_score < 35:
                risk_level = "LOW"
            elif adjusted_risk_score < 55:
                risk_level = "MEDIUM"
            else:
                risk_level = "HIGH"
        else:  # HIGH or CRITICAL
            if adjusted_risk_score < 45:
                risk_level = "MEDIUM"
            elif adjusted_risk_score < 65:
                risk_level = "HIGH"
            else:
                risk_level = "CRITICAL"

        # 7. 신뢰도 계산 (데이터 품질 + 글로벌 일관성)
        base_confidence = global_risk.get('analysis', {}).get('confidence', 0.6)
        volatility_confidence = 0.8 if volatility_30d > 0 else 0.3
        final_confidence = (base_confidence + volatility_confidence) / 2

        # 8. 결과 구성 (하이브리드 구조)
        result = global_risk.copy()

        # 글로벌 리스크 정보 유지
        result['global_risk'] = {
            'level': global_risk_level,
            'score': base_risk_score,
            'indicators': global_risk.get('analysis', {}).get('risk_indicators', {})
        }

        # 개별 코인 리스크 정보
        result['individual_risk'] = {
            'level': risk_level,
            'score': adjusted_risk_score,
            'volatility_30d': volatility_30d,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'coin_weight': coin_weight,
            'adjustment_factors': {
                'volatility_factor': volatility_factor,
                'drawdown_factor': drawdown_factor,
                'sharpe_factor': sharpe_factor
            }
        }

        # 기존 구조와 호환성 유지
        result['analysis']['risk_indicators']['overall_risk_score'] = adjusted_risk_score
        result['analysis']['risk_indicators']['coin_volatility_30d'] = volatility_30d
        result['analysis']['risk_indicators']['coin_max_drawdown'] = max_drawdown
        result['analysis']['risk_indicators']['coin_sharpe_ratio'] = sharpe_ratio
        result['analysis']['risk_indicators']['coin_risk_factor'] = coin_weight
        result['risk_grade'] = risk_level
        result['analysis']['confidence'] = final_confidence

        logger.info(f"📊 {coin_symbol} 하이브리드 리스크: 글로벌({global_risk_level}:{base_risk_score:.1f}) + 개별({risk_level}:{adjusted_risk_score:.1f})")

        return result

    except Exception as e:
        logger.error(f"❌ {coin_symbol} 하이브리드 리스크 조정 실패: {str(e)}")
        return global_risk

def get_coin_risk_weight(coin_symbol: str) -> float:
    """
    코인별 리스크 가중치 (대장주 vs 알트코인)
    """
    # 대장주 (낮은 리스크)
    major_coins = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT"]

    # 중간 규모 코인
    mid_caps = ["SOL/USDT", "DOT/USDT", "AVAX/USDT", "MATIC/USDT", "LINK/USDT", "UNI/USDT"]

    if coin_symbol in major_coins:
        return 0.8  # 20% 리스크 감소
    elif coin_symbol in mid_caps:
        return 1.0  # 기본 리스크
    else:
        return 1.3  # 30% 리스크 증가 (알트코인)

async def save_risk_analysis_to_database(analysis_data: Dict[str, Any]):
    """리스크 분석 결과를 데이터베이스에 저장"""
    import asyncpg

    try:
        # 데이터베이스 연결
        conn = await asyncpg.connect(
            host=database_config.POSTGRESQL_DB_HOST,
            port=int(database_config.POSTGRESQL_DB_PORT),
            database=database_config.POSTGRESQL_DB_DATABASE,
            user=database_config.POSTGRESQL_DB_USER,
            password=database_config.POSTGRESQL_DB_PASSWORD
        )

        try:
            # 기존 리스크 분석 서비스 결과 구조에 맞게 데이터 추출
            asset_symbol = analysis_data.get('market', '')
            risk_grade = analysis_data.get('risk_grade', 'unknown')
            analysis = analysis_data.get('analysis', {})

            # analysis에서 세부 데이터 추출
            risk_indicators = analysis.get('risk_indicators', {})
            correlation_analysis = analysis.get('correlation_analysis', {})
            risk_off_signal = analysis.get('risk_off_signal', False)
            confidence = analysis.get('confidence', 0.0)

            # risk_score는 risk_indicators에서 계산하거나 기본값 사용
            risk_score = 0.0
            if isinstance(risk_indicators, dict) and 'overall_risk_score' in risk_indicators:
                risk_score = risk_indicators['overall_risk_score']

            # JSON 직렬화
            risk_indicators_json = json.dumps(risk_indicators) if risk_indicators else '{}'
            correlation_analysis_json = json.dumps(correlation_analysis) if correlation_analysis else '{}'
            full_analysis_data_json = json.dumps(analysis_data)

            # 만료 시간 (1시간 후)
            expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

            # INSERT 쿼리 (기존 데이터와 충돌 방지를 위해 단순 INSERT)
            query = """
                INSERT INTO risk_analysis_reports
                (asset_symbol, risk_score, market_risk_level, risk_off_signal, confidence,
                 risk_indicators, correlation_analysis, full_analysis_data, expires_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """

            await conn.execute(
                query,
                asset_symbol, risk_score, risk_grade, risk_off_signal, confidence,
                risk_indicators_json, correlation_analysis_json,
                full_analysis_data_json, expires_at
            )

            logger.info(f"✅ 리스크 분석 저장 완료: {asset_symbol} | {risk_grade} | Risk-Off: {risk_off_signal}")

        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"❌ 리스크 분석 저장 실패: {str(e)}")
        raise

@celery_app.task(bind=True, name='scheduler.tasks.risk_analysis.analyze_top_20_risk')
def analyze_top_20_risk(self):
    """상위 20개 코인에 대한 리스크 분석 실행"""
    try:
        logger.info("🚀 리스크 분석 스케줄러 시작")

        # 상위 20개 코인 조회
        top_coins = get_top_20_coins()
        logger.info(f"📊 분석 대상 코인: {len(top_coins)}개")

        # 리스크 분석 서비스 초기화
        risk_service = RiskAnalysisService()

        # 배치 처리: 5개씩 나누어서 처리 (타임아웃 방지)
        batch_size = 5
        total_batches = (len(top_coins) + batch_size - 1) // batch_size

        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(top_coins))
            batch_coins = top_coins[start_idx:end_idx]

            logger.info(f"📦 배치 {batch_idx + 1}/{total_batches} 처리 시작: {len(batch_coins)}개 코인")

            # 배치 내 각 코인별 리스크 분석 및 저장
            for i, coin in enumerate(batch_coins):
                try:
                    logger.info(f"🔍 리스크 분석 진행: {coin} ({start_idx + i + 1}/{len(top_coins)})")

                    # 비동기 리스크 분석 실행
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    try:
                        # 개별 코인별 변동성과 특성을 고려한 리스크 분석
                        analysis_result = loop.run_until_complete(
                            analyze_individual_coin_risk(
                                coin, risk_service, days_back=90
                            )
                        )

                        # 데이터베이스에 저장
                        loop.run_until_complete(
                            save_risk_analysis_to_database(analysis_result)
                        )

                        logger.info(f"✅ {coin} 리스크 분석 완료")

                    finally:
                        loop.close()

                except Exception as e:
                    logger.error(f"❌ {coin} 리스크 분석 실패: {str(e)}")
                    continue

            # 배치 간 잠시 대기 (API 제한 방지)
            if batch_idx < total_batches - 1:
                logger.info("⏳ 다음 배치 처리 전 10초 대기...")
                time.sleep(10)

        logger.info("🎉 리스크 분석 스케줄러 완료")
        return {"status": "success", "analyzed_coins": len(top_coins)}

    except Exception as e:
        logger.error(f"❌ 리스크 분석 스케줄러 실패: {str(e)}")
        raise

@celery_app.task(bind=True, name='scheduler.tasks.risk_analysis.get_all_risk_analyses')
def get_all_risk_analyses(self):
    """저장된 모든 리스크 분석 결과 조회"""
    try:
        import asyncpg

        # 데이터베이스 연결
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            conn = loop.run_until_complete(asyncpg.connect(
                host=database_config.POSTGRESQL_DB_HOST,
                port=int(database_config.POSTGRESQL_DB_PORT),
                database=database_config.POSTGRESQL_DB_DATABASE,
                user=database_config.POSTGRESQL_DB_USER,
                password=database_config.POSTGRESQL_DB_PASSWORD
            ))

            try:
                # 최근 24시간 데이터 조회
                query = """
                    SELECT * FROM risk_analysis_reports
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                    ORDER BY created_at DESC
                """

                rows = loop.run_until_complete(conn.fetch(query))

                results = []
                for row in rows:
                    result_dict = dict(row)
                    # JSONB 필드는 자동으로 파싱되므로 추가 처리 불필요
                    results.append(result_dict)

                logger.info(f"✅ 리스크 분석 조회 완료: {len(results)}개")
                return results

            finally:
                loop.run_until_complete(conn.close())

        finally:
            loop.close()

    except Exception as e:
        logger.error(f"❌ 리스크 분석 조회 실패: {str(e)}")
        raise
