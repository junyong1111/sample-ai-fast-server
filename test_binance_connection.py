#!/usr/bin/env python3
"""
바이낸스 Testnet 연결 테스트 스크립트
"""

import asyncio
import os
import ccxt

async def test_binance_testnet_connection():
    """바이낸스 testnet 연결 테스트"""
    print("🔌 바이낸스 Testnet 연결 테스트")
    print("=" * 50)

    # 환경변수 확인
    BINANCE_TESTNET_API_KEY="NSdQ8nBkN77FxUlrtApiOdqV3xnGkY8UNBFAMnQPyIGtPtNS4aZEwGvPj7v2ArXa"
    BINANCE_TESTNET_SECRET_KEY="G5CmRrTzQ49wfjPKqVBbr48hyZKZA4nbrTWvwK4TUrXpi7zoeE3CMipTVgWWZndm"
    api_key = BINANCE_TESTNET_API_KEY
    secret_key = BINANCE_TESTNET_SECRET_KEY



    print(f"환경변수 API Key: {'설정됨' if api_key else '설정되지 않음'}")
    print(f"환경변수 Secret Key: {'설정됨' if secret_key else '설정되지 않음'}")
    print()

        # API 키가 이미 설정되어 있는지 확인
    if api_key and secret_key:
        print("✅ API 키가 이미 설정되어 있습니다.")
    else:
        print("⚠️ API 키가 설정되지 않았습니다.")
        return

    print(f"\n입력된 API Key: {api_key[:10]}...")
    print(f"입력된 Secret Key: {secret_key[:10]}...")
    print()

    try:
        # CCXT를 사용하여 바이낸스 testnet 연결
        config = {
            'apiKey': api_key,
            'secret': secret_key,
            'enableRateLimit': True,
            'sandbox': True,  # testnet 모드
            'urls': {
                'api': {
                    'public': 'https://testnet.binance.vision/api',
                    'private': 'https://testnet.binance.vision/api',
                }
            }
        }

        print("1. CCXT 바이낸스 인스턴스 생성...")
        exchange = ccxt.binance(config)
        print("✅ CCXT 인스턴스 생성 완료")

        print("\n2. 시장 정보 로드...")
        markets = exchange.load_markets()
        print(f"✅ 시장 정보 로드 완료 (총 {len(markets)}개 시장)")

        print("\n3. 계정 잔고 조회...")
        balance = exchange.fetch_balance()
        print("✅ 계정 잔고 조회 완료")

        # USDT 잔고 확인
        usdt_balance = balance.get('USDT', {})
        free_usdt = usdt_balance.get('free', 0)
        total_usdt = usdt_balance.get('total', 0)

        print(f"\n💰 USDT 잔고:")
        print(f"  사용 가능: {free_usdt}")
        print(f"  총 잔고: {total_usdt}")

        print("\n4. BTC/USDT 티커 조회...")
        ticker = exchange.fetch_ticker('BTC/USDT')
        print(f"✅ 티커 조회 완료")
        print(f"  현재가: ${ticker['last']}")
        print(f"  24시간 변동: {ticker['percentage']:.2f}%")

        print("\n5. OHLCV 데이터 조회...")
        ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=5)
        print(f"✅ OHLCV 데이터 조회 완료 (최근 5개 캔들)")

        for candle in ohlcv[-3:]:  # 최근 3개만 출력
            timestamp, open_price, high, low, close, volume = candle
            print(f"  {timestamp}: O:{open_price:.2f} H:{high:.2f} L:{low:.2f} C:{close:.2f} V:{volume:.4f}")

        print("\n" + "=" * 50)
        print("🎉 바이낸스 Testnet 연결 테스트 성공!")

    except Exception as e:
        print(f"\n❌ 연결 테스트 실패: {str(e)}")
        print(f"오류 타입: {type(e).__name__}")

        # 자세한 오류 정보 출력
        if hasattr(e, 'response'):
            print(f"응답 상태: {e.response.status_code if hasattr(e.response, 'status_code') else 'N/A'}")
            print(f"응답 내용: {e.response.text if hasattr(e.response, 'text') else 'N/A'}")

if __name__ == "__main__":
    asyncio.run(test_binance_testnet_connection())
