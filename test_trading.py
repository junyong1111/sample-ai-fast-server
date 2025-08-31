#!/usr/bin/env python3
"""
거래 기능 테스트 스크립트
Binance Testnet을 이용한 자동 매매 기능 테스트
"""

import asyncio
import os
from src.app.autotrading.trading_service import TradingService
from src.app.autotrading.service import ChartService


async def test_trading_functionality():
    """거래 기능 테스트"""
    print("🚀 Binance Testnet 거래 기능 테스트 시작")
    print("=" * 50)

    try:
        # 1. 거래 서비스 초기화
        print("1. 거래 서비스 초기화...")
        trading_service = TradingService(testnet=True)
        print("✅ 거래 서비스 초기화 완료")

        # 2. 계정 상태 확인
        print("\n2. 계정 상태 확인...")
        account_status = await trading_service.get_account_status()
        print(f"계정 상태: {account_status['status']}")
        if account_status['status'] == 'success':
            print("✅ 계정 상태 확인 성공")
        else:
            print(f"❌ 계정 상태 확인 실패: {account_status.get('error')}")

        # 3. 차트 서비스 초기화
        print("\n3. 차트 서비스 초기화...")
        chart_service = ChartService(exchange_type="binance")
        print("✅ 차트 서비스 초기화 완료")

        # 4. 거래 신호 생성
        print("\n4. 거래 신호 생성...")
        signal_data = await chart_service.get_trading_signal_with_storage(
            market="BTC/USDT",
            tf="minutes:60",
            count=100
        )
        print(f"거래 신호: {signal_data.get('overall_signal', 'UNKNOWN')}")
        print("✅ 거래 신호 생성 완료")

        # 5. 전략 실행 테스트 (실제 거래는 하지 않음)
        print("\n5. 전략 실행 테스트...")
        if account_status['status'] == 'success':
            strategy_result = await trading_service.execute_strategy(
                market="BTC/USDT",
                signal_data=signal_data,
                risk_per_trade=0.01,  # 1% 리스크
                order_type='market'
            )
            print(f"전략 실행 결과: {strategy_result['status']}")
            if strategy_result['status'] == 'success':
                print("✅ 전략 실행 테스트 성공")
            else:
                print(f"⚠️ 전략 실행 테스트 실패: {strategy_result.get('error')}")
        else:
            print("⚠️ 계정 상태 확인 실패로 전략 실행 테스트 건너뜀")

        # 6. 미체결 주문 조회
        print("\n6. 미체결 주문 조회...")
        open_orders = await trading_service.get_open_orders()
        print(f"미체결 주문 수: {open_orders.get('count', 0)}")
        print("✅ 미체결 주문 조회 완료")

        print("\n" + "=" * 50)
        print("🎉 모든 테스트 완료!")

    except Exception as e:
        print(f"\n❌ 테스트 중 오류 발생: {str(e)}")
        print("=" * 50)


async def test_binance_connection():
    """Binance 연결 테스트"""
    print("🔌 Binance 연결 테스트")
    print("-" * 30)

    try:
        from src.common.utils.bitcoin.binace import BinanceUtils

        # Binance 유틸리티 초기화
        binance = BinanceUtils(testnet=True)

        # 연결 테스트
        health = await binance.get_chart_health()
        print(f"연결 상태: {health['status']}")

        if health['status'] == 'ok':
            print("✅ Binance 연결 성공")
        else:
            print(f"❌ Binance 연결 실패: {health.get('error')}")

    except Exception as e:
        print(f"❌ Binance 연결 테스트 실패: {str(e)}")


if __name__ == "__main__":
    # 환경변수 설정 확인
    print("🔍 환경변수 확인:")
    print(f"BINANCE_TESTNET_API_KEY: {'설정됨' if os.getenv('BINANCE_TESTNET_API_KEY') else '설정되지 않음'}")
    print(f"BINANCE_TESTNET_SECRET_KEY: {'설정됨' if os.getenv('BINANCE_TESTNET_SECRET_KEY') else '설정되지 않음'}")
    print()

    # 테스트 실행
    asyncio.run(test_binance_connection())
    print()
    asyncio.run(test_trading_functionality())
