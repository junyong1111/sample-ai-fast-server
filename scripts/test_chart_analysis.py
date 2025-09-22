#!/usr/bin/env python3
"""
차트 분석 시스템 테스트 스크립트
"""

import asyncio
import sys
import os
from datetime import datetime, timezone

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.scheduler.tasks.chart_analysis_task.func import ChartAnalysisFunc
from src.common.utils.logger import set_logger

logger = set_logger("test_chart_analysis")

async def test_chart_analysis_system():
    """차트 분석 시스템 테스트"""
    print("🧪 차트 분석 시스템 테스트 시작")
    print("=" * 50)

    try:
        # Function 인스턴스 생성
        func = ChartAnalysisFunc(logger)
        print("✅ ChartAnalysisFunc 인스턴스 생성 성공")

        # 1. 단일 코인 분석 테스트
        print("\n📊 1. 단일 코인 분석 테스트 (BTC/USDT)")
        test_market = "BTC/USDT"

        # 캐시 확인
        cached_result = await func.get_latest_analysis(test_market)
        if cached_result:
            print(f"✅ 캐시된 결과 발견: {test_market}")
            print(f"   - 정량 점수: {cached_result.get('quant_score', 'N/A')}")
            print(f"   - 시장 레짐: {cached_result.get('market_regime', 'N/A')}")
            print(f"   - 생성 시간: {cached_result.get('created_at', 'N/A')}")
            print(f"   - 만료 시간: {cached_result.get('expires_at', 'N/A')}")
        else:
            print(f"ℹ️  캐시된 결과 없음: {test_market}")

        # 2. 모든 코인 조회 테스트
        print("\n📋 2. 모든 코인 조회 테스트")
        all_results = await func.get_all_latest_analyses()
        print(f"✅ 조회된 코인 수: {len(all_results)}개")

        for result in all_results[:3]:  # 처음 3개만 출력
            print(f"   - {result.get('asset_symbol', 'N/A')}: {result.get('quant_score', 'N/A')}점")

        # 3. 통계 조회 테스트
        print("\n📈 3. 분석 통계 조회 테스트")
        stats = await func.get_analysis_statistics()
        print(f"✅ 성공: {stats.get('success_count', 0)}개")
        print(f"✅ 실패: {stats.get('error_count', 0)}개")
        print(f"✅ 성공률: {stats.get('success_rate', 0):.2%}")

        print("\n🎉 모든 테스트 통과!")
        return True

    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")
        logger.error(f"테스트 실패: {str(e)}")
        return False

async def test_celery_tasks():
    """Celery 태스크 테스트"""
    print("\n🔄 Celery 태스크 테스트")
    print("=" * 50)

    try:
        from scheduler.tasks.chart_analysis_task import (
            analyze_major_coins,
            analyze_single_coin,
            get_latest_analysis,
            get_all_analyses
        )

        print("✅ Celery 태스크 import 성공")

        # 태스크 실행 (동기적으로)
        print("\n📊 주요 코인 배치 분석 태스크 테스트")
        result = analyze_major_coins.delay("minutes:60", 200, "binance")
        print(f"✅ 태스크 ID: {result.id}")
        print(f"✅ 태스크 상태: {result.status}")

        print("\n📊 단일 코인 분석 태스크 테스트")
        single_result = analyze_single_coin.delay("DOGE/USDT", "minutes:60", 200, "binance")
        print(f"✅ 태스크 ID: {single_result.id}")
        print(f"✅ 태스크 상태: {single_result.status}")

        print("\n🎉 Celery 태스크 테스트 완료!")
        return True

    except Exception as e:
        print(f"❌ Celery 태스크 테스트 실패: {str(e)}")
        logger.error(f"Celery 태스크 테스트 실패: {str(e)}")
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 차트 분석 시스템 종합 테스트")
    print("=" * 60)
    print(f"⏰ 테스트 시작 시간: {datetime.now(timezone.utc).isoformat()}")
    print()

    # 비동기 테스트 실행
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # 1. 차트 분석 시스템 테스트
        system_test_result = loop.run_until_complete(test_chart_analysis_system())

        # 2. Celery 태스크 테스트
        celery_test_result = loop.run_until_complete(test_celery_tasks())

        # 결과 요약
        print("\n" + "=" * 60)
        print("📋 테스트 결과 요약")
        print("=" * 60)
        print(f"✅ 차트 분석 시스템: {'PASS' if system_test_result else 'FAIL'}")
        print(f"✅ Celery 태스크: {'PASS' if celery_test_result else 'FAIL'}")

        if system_test_result and celery_test_result:
            print("\n🎉 모든 테스트 통과! 시스템이 정상적으로 작동합니다.")
            return 0
        else:
            print("\n❌ 일부 테스트 실패. 로그를 확인해주세요.")
            return 1

    except Exception as e:
        print(f"\n❌ 테스트 실행 중 오류 발생: {str(e)}")
        logger.error(f"테스트 실행 중 오류: {str(e)}")
        return 1

    finally:
        loop.close()

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
