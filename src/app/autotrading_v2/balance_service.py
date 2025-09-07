"""
잔고 조회 서비스 V2
바이낸스 API를 통해 현재 계좌의 실시간 잔고를 조회
"""

import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from fastapi.concurrency import run_in_threadpool
from src.common.utils.logger import set_logger
from src.common.utils.bitcoin.binace import BinanceUtils
from src.app.autotrading_v2.models import BalanceRequest, BalanceResponse, AssetBalance

logger = set_logger("balance_service_v2")


class BalanceService:
    """잔고 조회 서비스 V2"""

    def __init__(self):
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.secret = os.getenv("BINANCE_SECRET_KEY")

        if self.api_key and self.secret:
            logger.info(f"환경변수에서 바이낸스 API 키를 로드했습니다: {self.api_key[:8]}***{self.api_key[-4:]}")
        else:
            logger.warning("환경변수에 BINANCE_API_KEY 또는 BINANCE_SECRET_KEY가 설정되지 않았습니다.")

    async def get_balance(self, request: BalanceRequest) -> BalanceResponse:
        """잔고 조회"""
        try:
            logger.info(f"잔고 조회 시작: tickers={request.tickers}, include_zero={request.include_zero_balances}")

            # API 키 확인
            if not self.api_key or not self.secret:
                return BalanceResponse(
                    status="error",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    balances=[],
                    total_usdt_value=0.0,
                    requested_tickers=request.tickers,
                    metadata={"error": "API 키가 설정되지 않았습니다. 환경변수(BINANCE_API_KEY, BINANCE_SECRET_KEY) 설정이 필요합니다."}
                )

            # 바이낸스 유틸리티 초기화
            binance_utils = BinanceUtils(
                api_key=self.api_key,
                secret=self.secret,
                testnet=False
            )

            # 연결 테스트
            try:
                health_check = await binance_utils.get_chart_health()
                if health_check.get("status") != "ok":
                    return BalanceResponse(
                        status="error",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        balances=[],
                        total_usdt_value=0.0,
                        requested_tickers=request.tickers,
                        metadata={
                            "error": f"바이낸스 API 연결 실패: {health_check.get('error', 'Unknown error')}",
                            "suggestion": "API 키 권한, IP 제한을 확인해주세요."
                        }
                    )
            except Exception as health_error:
                return BalanceResponse(
                    status="error",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    balances=[],
                    total_usdt_value=0.0,
                    requested_tickers=request.tickers,
                    metadata={
                        "error": f"바이낸스 API 연결 테스트 실패: {str(health_error)}",
                        "suggestion": "API 키 권한, IP 제한을 확인해주세요."
                    }
                )

            # 계정 정보 조회
            account_info = await binance_utils.get_account_info()
            logger.info(f"계정 정보 조회 결과: {account_info}")

            # 자산 정보 파싱
            balances = []
            total_usdt_value = 0.0

            # 요청된 티커가 있으면 필터링, 없으면 모든 자산 조회
            target_assets = request.tickers if request.tickers else None
            logger.info(f"요청된 티커: {target_assets}")

            # 바이낸스 API는 free, used, total 구조로 반환
            free_balance = account_info.get("free_balance", {})
            used_balance = account_info.get("used_balance", {})

            # 모든 자산에 대해 처리
            all_assets = set(free_balance.keys()) | set(used_balance.keys())
            logger.info(f"발견된 자산들: {list(all_assets)}")

            for asset in all_assets:
                free = float(free_balance.get(asset, 0))
                locked = float(used_balance.get(asset, 0))
                total = free + locked

                # 0 잔고 제외 처리
                if not request.include_zero_balances and total == 0:
                    continue

                # 특정 티커만 조회하는 경우 필터링
                if target_assets and asset not in target_assets:
                    continue

                # USDT가 아닌 자산의 경우 가격 조회
                usdt_value = None
                if asset != "USDT" and total > 0:
                    try:
                        # 직접 CCXT를 사용해서 가격 조회
                        import ccxt
                        exchange = ccxt.binance({
                            'sandbox': False,
                            'enableRateLimit': True,
                        })
                        ticker = await run_in_threadpool(exchange.fetch_ticker, f"{asset}/USDT")
                        price = float(ticker.get("last", 0))
                        usdt_value = total * price
                        total_usdt_value += usdt_value
                        logger.info(f"{asset} 가격: {price}, USDT 가치: {usdt_value}")
                    except Exception as price_error:
                        logger.warning(f"{asset} 가격 조회 실패: {price_error}")
                        usdt_value = 0
                elif asset == "USDT":
                    usdt_value = total
                    total_usdt_value += usdt_value

                balances.append(AssetBalance(
                    asset=asset,
                    free=free,
                    locked=locked,
                    total=total,
                    usdt_value=usdt_value
                ))

            # USDT 기준 가치로 정렬
            balances.sort(key=lambda x: x.usdt_value or 0, reverse=True)

            # 요약 정보 생성
            summary = self._create_summary(balances, total_usdt_value, target_assets)

            return BalanceResponse(
                status="success",
                timestamp=datetime.now(timezone.utc).isoformat(),
                balances=balances,
                total_usdt_value=total_usdt_value,
                requested_tickers=target_assets,
                metadata={
                    "total_assets": len(balances),
                    "api_key_masked": f"{self.api_key[:8]}***{self.api_key[-4:]}",
                    "summary": summary
                }
            )

        except Exception as e:
            logger.error(f"잔고 조회 실패: {e}")
            return BalanceResponse(
                status="error",
                timestamp=datetime.now(timezone.utc).isoformat(),
                balances=[],
                total_usdt_value=0.0,
                requested_tickers=request.tickers,
                metadata={"error": f"잔고 조회 중 오류가 발생했습니다: {str(e)}"}
            )

    def _create_summary(self, balances: List[AssetBalance], total_usdt_value: float, requested_tickers: Optional[List[str]]) -> Dict[str, Any]:
        """잔고 요약 정보 생성"""
        try:
            if not balances or total_usdt_value == 0:
                return {
                    "message": "조회된 잔고가 없습니다",
                    "total_assets": 0,
                    "total_value": "$0.00"
                }

            # 주요 자산 정보
            major_assets = []
            for balance in balances[:5]:  # 상위 5개 자산
                if balance.usdt_value and balance.usdt_value > 0:
                    percentage = (balance.usdt_value / total_usdt_value) * 100
                    major_assets.append({
                        "asset": balance.asset,
                        "value": f"${balance.usdt_value:,.2f}",
                        "percentage": f"{percentage:.1f}%"
                    })

            # 요청된 티커 정보
            ticker_info = ""
            if requested_tickers:
                ticker_info = f"요청된 티커: {', '.join(requested_tickers)}"
            else:
                ticker_info = "전체 자산 조회"

            return {
                "message": f"총 {len(balances)}개 자산, 총 가치: ${total_usdt_value:,.2f}",
                "total_assets": len(balances),
                "total_value": f"${total_usdt_value:,.2f}",
                "major_assets": major_assets,
                "ticker_info": ticker_info
            }

        except Exception as e:
            logger.error(f"요약 정보 생성 실패: {e}")
            return {"error": "요약 정보 생성 실패"}

    async def health_check(self) -> Dict[str, Any]:
        """서비스 헬스체크"""
        try:
            has_api_keys = bool(self.api_key and self.secret)

            if has_api_keys:
                # API 연결 테스트
                binance_utils = BinanceUtils(
                    api_key=self.api_key,
                    secret=self.secret,
                    testnet=False
                )
                health_check = await binance_utils.get_chart_health()
                connection_status = "ok" if health_check.get("status") == "ok" else "error"
            else:
                connection_status = "no_api_key"

            return {
                "status": "healthy" if connection_status == "ok" else "unhealthy",
                "api_key_configured": has_api_keys,
                "connection_status": connection_status,
                "service": "balance_service_v2"
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "api_key_configured": bool(self.api_key and self.secret),
                "connection_status": "error",
                "service": "balance_service_v2",
                "error": str(e)
            }
