#!/usr/bin/env python3
"""
포트폴리오 분석 테스트 스크립트
평균 매수가격 조회 및 손절/익절 판단 테스트
"""

import asyncio
import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from src.app.autotrading_v2.balance_service import BalanceService
from src.app.autotrading_v2.portfolio_utils import (
    calculate_pnl_percentage,
    determine_trade_signal,
    analyze_portfolio_risk
)
from src.app.autotrading_v2.models import BalanceRequest


async def test_portfolio_analysis():
    """포트폴리오 분석 테스트"""
    print("🔍 포트폴리오 분석 테스트 시작")

    # 환경변수 확인
    api_key = os.getenv("BINANCE_API_KEY")
    secret_key = os.getenv("BINANCE_SECRET_KEY")

    if not api_key or not secret_key:
        print("❌ 바이낸스 API 키가 설정되지 않았습니다")
        print("환경변수 설정:")
        print("export BINANCE_API_KEY='your_api_key'")
        print("export BINANCE_SECRET_KEY='your_secret_key'")
        return

    print(f"✅ API 키 확인: {api_key[:8]}***{api_key[-4:]}")

    # 잔고 서비스 초기화
    balance_service = BalanceService()

    try:
        # 잔고 조회
        print("\n📊 잔고 조회 중...")
        request = BalanceRequest(
            tickers=["BTC", "USDT"],
            include_zero_balances=False,
            user_id="test_user"
        )

        response = await balance_service.get_balance(request)

        if response.status == "error":
            print(f"❌ 잔고 조회 실패: {response.metadata.get('error', 'Unknown error')}")
            return

        print(f"✅ 잔고 조회 성공")
        print(f"총 USDT 가치: {response.total_usdt_value:.2f} USDT")

        # BTC 잔고 분석
        btc_balance = None
        btc_price = None
        avg_entry_price = None

        for asset in response.balances:
            if asset.asset == "BTC":
                btc_balance = asset.total
                avg_entry_price = asset.avg_entry_price
                print(f"BTC 잔고: {btc_balance:.6f} BTC")
                print(f"BTC 평균 매수가격: {avg_entry_price:.2f} USDT" if avg_entry_price else "BTC 평균 매수가격: 없음")
            elif asset.asset == "USDT":
                print(f"USDT 잔고: {asset.total:.2f} USDT")

        # BTC 가격 조회 (간단한 방법)
        if btc_balance and btc_balance > 0:
            try:
                from src.common.utils.bitcoin.binace import BinanceUtils
                binance_utils = BinanceUtils(api_key, secret_key)
                ticker = await binance_utils.get_ticker("BTC/USDT")
                btc_price = float(ticker.get("last", 0))
                print(f"BTC 현재가: {btc_price:.2f} USDT")

                # 손익률 계산
                if avg_entry_price:
                    pnl_percentage = calculate_pnl_percentage(btc_price, avg_entry_price)
                    print(f"손익률: {pnl_percentage:.2f}%")

                    # 거래 신호 판단
                    trade_signal = determine_trade_signal(btc_price, avg_entry_price)
                    print(f"\n🎯 거래 신호: {trade_signal['signal']}")
                    print(f"판단 근거: {trade_signal['reason']}")
                    print(f"손절가: {trade_signal['stop_loss_price']:.2f} USDT")
                    print(f"목표가: {trade_signal['take_profit_price']:.2f} USDT")

                    # 포트폴리오 리스크 분석
                    btc_percentage = (btc_balance * btc_price / response.total_usdt_value * 100) if response.total_usdt_value > 0 else 0
                    risk_analysis = analyze_portfolio_risk(
                        btc_balance, btc_price, avg_entry_price,
                        response.total_usdt_value, btc_percentage
                    )

                    print(f"\n📈 포트폴리오 리스크 분석:")
                    print(f"BTC 비중: {btc_percentage:.1f}%")
                    print(f"리스크 레벨: {risk_analysis['risk_level']}")
                    for rec in risk_analysis['recommendations']:
                        print(f"권장사항: {rec}")
                else:
                    print("⚠️ 평균 매수가격 정보가 없어 손익 계산이 불가능합니다")

            except Exception as e:
                print(f"❌ BTC 가격 조회 실패: {str(e)}")
        else:
            print("ℹ️ BTC 잔고가 없습니다")

    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_portfolio_analysis())
