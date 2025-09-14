"""
잔고 조회 서비스 V2
바이낸스 API를 통해 현재 계좌의 실시간 잔고를 조회
"""

import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from fastapi.concurrency import run_in_threadpool
from src.app.user.service import UserService
from src.common.utils.logger import set_logger
from src.common.utils.bitcoin.binace import BinanceUtils
from src.app.autotrading_v2.models import (
    BalanceRequest, BalanceResponse, AssetBalance,
    LastTradeInfo, RecentTradeInfo, AIAnalysisData
)
from src.app.autotrading_v2.portfolio_utils import analyze_asset_with_fees

logger = set_logger("balance_service_v2")


class BalanceService:
    """잔고 조회 서비스 V2"""

    def __init__(self):
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.secret = os.getenv("BINANCE_SECRET_KEY")
        self.user_service = UserService(logger)

        if self.api_key and self.secret:
            logger.info(f"환경변수에서 바이낸스 API 키를 로드했습니다: {self.api_key[:8]}***{self.api_key[-4:]}")
        else:
            logger.warning("환경변수에 BINANCE_API_KEY 또는 BINANCE_SECRET_KEY가 설정되지 않았습니다.")

    def set_api_key(self, api_key: str, secret: str):
        self.api_key = api_key
        self.secret = secret

    async def get_balance(self, request: BalanceRequest) -> BalanceResponse:
        """잔고 조회"""
        try:
            logger.info(f"잔고 조회 시작: tickers={request.tickers}, include_zero={request.include_zero_balances}")

            user_info = await self.user_service.get_user_exchange_by_user_idx(
                user_idx=request.user_idx
            )

            if not user_info:
                return BalanceResponse(
                    status="error",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    balances=[],
                    total_usdt_value=0.0,
                    requested_tickers=request.tickers,
                    last_trade=None,
                    recent_trades=None,
                    ai_analysis_data=None,
                    metadata={"error": "사용자 정보를 찾을 수 없습니다."}
                )
            api_key = user_info.get("access_key_ref")
            secret = user_info.get("secret_key_ref")
            if not api_key or not secret:
                return BalanceResponse(
                    status="error",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    balances=[],
                    total_usdt_value=0.0,
                    requested_tickers=request.tickers,
                    last_trade=None,
                    recent_trades=None,
                    ai_analysis_data=None,
                    metadata={"error": "API 키가 설정되지 않았습니다. 환경변수(BINANCE_API_KEY, BINANCE_SECRET_KEY) 설정이 필요합니다."}
                )
            # API 키 확인
            self.set_api_key(api_key=api_key, secret=secret)
            if not self.api_key or not self.secret:
                return BalanceResponse(
                    status="error",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    balances=[],
                    total_usdt_value=0.0,
                    requested_tickers=request.tickers,
                    last_trade=None,
                    recent_trades=None,
                    ai_analysis_data=None,
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
                        last_trade=None,
                        recent_trades=None,
                        ai_analysis_data=None,
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
                    last_trade=None,
                    recent_trades=None,
                    ai_analysis_data=None,
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
                        usdt_value = float(total) * price
                        total_usdt_value += usdt_value
                        logger.info(f"{asset} 가격: {price}, USDT 가치: {usdt_value}")
                    except Exception as price_error:
                        logger.warning(f"{asset} 가격 조회 실패: {price_error}")
                        usdt_value = 0.0
                elif asset == "USDT":
                    usdt_value = float(total)
                    total_usdt_value += usdt_value

                # 평균 매수가격 조회 (BTC인 경우만)
                avg_entry_price = None
                if asset == "BTC" and total > 0:
                    try:
                        avg_entry_price = await self._get_avg_entry_price("BTC/USDT")
                        logger.info(f"BTC 평균 매수가격: {avg_entry_price}")
                    except Exception as e:
                        logger.warning(f"BTC 평균 매수가격 조회 실패: {str(e)}")

                # 수수료 분석 (요청된 경우만)
                trading_fees = None
                profit_loss = None
                sell_analysis = None

                if request.include_fees_analysis and total > 0 and usdt_value and usdt_value > 0:
                    try:
                        current_price = usdt_value / total
                        fees_analysis = analyze_asset_with_fees(
                            asset, total, current_price, avg_entry_price, request.fee_rate
                        )
                        trading_fees = fees_analysis["trading_fees"]
                        profit_loss = fees_analysis["profit_loss"]
                        sell_analysis = fees_analysis["sell_analysis"]
                    except Exception as e:
                        logger.warning(f"{asset} 수수료 분석 실패: {str(e)}")

                balances.append(AssetBalance(
                    asset=asset,
                    free=free,
                    locked=locked,
                    total=total,
                    usdt_value=usdt_value,
                    avg_entry_price=avg_entry_price,
                    trading_fees=trading_fees,
                    profit_loss=profit_loss,
                    sell_analysis=sell_analysis
                ))

            # USDT 기준 가치로 정렬
            balances.sort(key=lambda x: x.usdt_value or 0, reverse=True)

            # 요약 정보 생성
            summary = self._create_summary(balances, total_usdt_value, target_assets)

            # 거래 내역 조회 (요청된 경우만)
            last_trade = None
            recent_trades = None
            ai_analysis_data = None

            logger.info(f"거래 내역 조회 요청: include_trade_history={request.include_trade_history}")

            if request.include_trade_history:
                try:
                    logger.info("거래 내역 조회 시작...")
                    last_trade, recent_trades, ai_analysis_data = await self._get_trade_history(
                        binance_utils, request.recent_trades_count
                    )
                    logger.info(f"거래 내역 조회 완료: last_trade={last_trade is not None}, recent_trades={len(recent_trades) if recent_trades else 0}")
                except Exception as e:
                    logger.error(f"거래 내역 조회 실패: {str(e)}", exc_info=True)

            return BalanceResponse(
                status="success",
                timestamp=datetime.now(timezone.utc).isoformat(),
                balances=balances,
                total_usdt_value=total_usdt_value,
                requested_tickers=target_assets,
                last_trade=last_trade,
                recent_trades=recent_trades,
                ai_analysis_data=ai_analysis_data,
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
                last_trade=None,
                recent_trades=None,
                ai_analysis_data=None,
                metadata={"error": f"잔고 조회 중 오류가 발생했습니다: {str(e)}"}
            )

    def _create_summary(self, balances: List[AssetBalance], total_usdt_value: float, requested_tickers: Optional[List[str]]) -> Dict[str, Any]:
        """잔고 요약 정보 생성"""
        try:
            if not balances or total_usdt_value == 0:
                return {
                    "total_assets": 0,
                    "total_value": 0.0
                }

            # 주요 자산 정보 (숫자 데이터만)
            major_assets = []
            for balance in balances[:5]:  # 상위 5개 자산
                if balance.usdt_value and balance.usdt_value > 0:
                    percentage = (balance.usdt_value / total_usdt_value) * 100
                    major_assets.append({
                        "asset": balance.asset,
                        "value": balance.usdt_value,
                        "percentage": round(percentage, 2)
                    })

            return {
                "total_assets": len(balances),
                "total_value": total_usdt_value,
                "major_assets": major_assets,
                "requested_tickers": requested_tickers
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

    async def _get_avg_entry_price(self, market: str) -> Optional[float]:
        """평균 매수가격 조회"""
        try:
            if not self.api_key or not self.secret:
                logger.warning("바이낸스 API 키가 설정되지 않아 평균 매수가격을 조회할 수 없습니다")
                return None

            binance_utils = BinanceUtils(self.api_key, self.secret)
            avg_price = await binance_utils.calculate_avg_entry_price(market, limit=100)
            return avg_price

        except Exception as e:
            logger.error(f"평균 매수가격 조회 실패: {str(e)}")
            return None

    async def _get_trade_history(self, binance_utils: BinanceUtils, recent_trades_count: int) -> tuple[Optional[LastTradeInfo], Optional[List[RecentTradeInfo]], Optional[AIAnalysisData]]:
        """거래 내역 조회 및 AI 분석 데이터 생성"""
        try:
            # 바이낸스 API를 통해 모든 거래 내역 조회
            all_trades = []

            try:
                # CCXT를 직접 사용하여 거래 내역 조회
                import ccxt
                if not self.api_key or not self.secret:
                    logger.error("API 키가 설정되지 않아 거래 내역을 조회할 수 없습니다")
                    return None, None, None

                exchange = ccxt.binance({
                    'apiKey': self.api_key,
                    'secret': self.secret,
                    'sandbox': False,
                    'enableRateLimit': True,
                })
                # 최근 30일간의 거래 내역 조회
                since = int((datetime.now(timezone.utc) - timedelta(days=30)).timestamp() * 1000)

                # 주요 거래 쌍들 조회
                markets = ["BTC/USDT", "ETH/USDT", "BNB/USDT"]

                for market in markets:
                    try:
                        logger.info(f"{market} 거래 내역 조회 시작...")
                        trades = await run_in_threadpool(
                            exchange.fetch_my_trades,
                            market,
                            since=since,
                            limit=100
                        )
                        logger.info(f"{market} 거래 내역 {len(trades)}개 조회됨")

                        for trade in trades:
                            trade['market'] = market
                            all_trades.append(trade)

                    except Exception as e:
                        logger.error(f"{market} 거래 내역 조회 실패: {str(e)}", exc_info=True)
                        continue

            except Exception as e:
                logger.error(f"바이낸스 API 거래 내역 조회 실패: {str(e)}")
                return None, None, None

            if not all_trades:
                logger.info("거래 내역이 없습니다.")
                return None, None, None

            # 시간순으로 정렬 (최신순)
            all_trades.sort(key=lambda x: x.get('timestamp', 0), reverse=True)

            # 마지막 거래 정보
            last_trade = None
            if all_trades:
                last_trade_data = all_trades[0]
                last_trade = LastTradeInfo(
                    date=datetime.fromtimestamp(last_trade_data.get('timestamp', 0) / 1000, tz=timezone.utc).isoformat(),
                    symbol=last_trade_data.get('symbol', ''),
                    side=last_trade_data.get('side', ''),
                    amount=float(last_trade_data.get('amount', 0)),
                    price=float(last_trade_data.get('price', 0)),
                    cost=float(last_trade_data.get('cost', 0)),
                    fee=float(last_trade_data.get('fee', {}).get('cost', 0)) if isinstance(last_trade_data.get('fee'), dict) else float(last_trade_data.get('fee', 0)),
                    fee_asset=last_trade_data.get('fee', {}).get('currency', 'USDT') if isinstance(last_trade_data.get('fee'), dict) else 'USDT'
                )

            # 최근 거래 내역
            recent_trades = []
            for trade_data in all_trades[:recent_trades_count]:
                recent_trades.append(RecentTradeInfo(
                    date=datetime.fromtimestamp(trade_data.get('timestamp', 0) / 1000, tz=timezone.utc).isoformat(),
                    symbol=trade_data.get('symbol', ''),
                    side=trade_data.get('side', ''),
                    amount=float(trade_data.get('amount', 0)),
                    price=float(trade_data.get('price', 0)),
                    cost=float(trade_data.get('cost', 0)),
                    fee=float(trade_data.get('fee', {}).get('cost', 0)) if isinstance(trade_data.get('fee'), dict) else float(trade_data.get('fee', 0)),
                    fee_asset=trade_data.get('fee', {}).get('currency', 'USDT') if isinstance(trade_data.get('fee'), dict) else 'USDT'
                ))

            # AI 분석 데이터 생성
            ai_analysis_data = self._create_ai_analysis_data(all_trades)

            return last_trade, recent_trades, ai_analysis_data

        except Exception as e:
            logger.error(f"거래 내역 조회 실패: {str(e)}")
            return None, None, None

    def _create_ai_analysis_data(self, trades: List[Dict[str, Any]]) -> AIAnalysisData:
        """AI 분석용 거래 데이터 생성"""
        try:
            if not trades:
                return AIAnalysisData(
                    total_trades_count=0,
                    buy_trades_count=0,
                    sell_trades_count=0,
                    avg_trade_amount=0.0,
                    avg_trade_quantity=0.0,
                    total_fees_paid=0.0,
                    recent_activity_score=0.0,
                    buy_sell_ratio=0.0,
                    trading_frequency=0.0,
                    avg_trade_interval_hours=0.0,
                    fee_efficiency=0.0
                )

            # 기본 통계
            total_trades = len(trades)
            buy_trades = [t for t in trades if t.get('side') == 'buy']
            sell_trades = [t for t in trades if t.get('side') == 'sell']

            buy_count = len(buy_trades)
            sell_count = len(sell_trades)

            # 거래 금액 및 수량 통계
            total_amount = sum(float(t.get('cost', 0)) for t in trades)
            total_quantity = sum(float(t.get('amount', 0)) for t in trades)
            avg_trade_amount = total_amount / total_trades if total_trades > 0 else 0.0
            avg_trade_quantity = total_quantity / total_trades if total_trades > 0 else 0.0

            # 수수료 통계
            total_fees = sum(
                float(t.get('fee', {}).get('cost', 0)) if isinstance(t.get('fee'), dict)
                else float(t.get('fee', 0))
                for t in trades
            )
            fee_efficiency = (total_fees / total_amount) * 100 if total_amount > 0 else 0.0

            # 매수/매도 비율
            buy_sell_ratio = buy_count / sell_count if sell_count > 0 else float('inf') if buy_count > 0 else 0.0

            # 거래 빈도 계산 (최근 30일 기준)
            now = datetime.now(timezone.utc)
            thirty_days_ago = now - timedelta(days=30)
            recent_trades = [t for t in trades if datetime.fromtimestamp(t.get('timestamp', 0) / 1000, tz=timezone.utc) >= thirty_days_ago]
            trading_frequency = len(recent_trades) / 30.0  # 거래/일

            # 거래 간격 계산
            if len(trades) > 1:
                timestamps = sorted([t.get('timestamp', 0) for t in trades])
                intervals = [(timestamps[i+1] - timestamps[i]) / (1000 * 3600) for i in range(len(timestamps)-1)]  # 시간 단위
                avg_trade_interval_hours = sum(intervals) / len(intervals) if intervals else 0.0
            else:
                avg_trade_interval_hours = 0.0

            # 최근 활동성 점수 (0-1)
            recent_activity_score = min(trading_frequency / 2.0, 1.0)  # 하루 2회 거래를 1.0으로 정규화

            return AIAnalysisData(
                total_trades_count=total_trades,
                buy_trades_count=buy_count,
                sell_trades_count=sell_count,
                avg_trade_amount=round(avg_trade_amount, 2),
                avg_trade_quantity=round(avg_trade_quantity, 6),
                total_fees_paid=round(total_fees, 2),
                recent_activity_score=round(recent_activity_score, 3),
                buy_sell_ratio=round(buy_sell_ratio, 2),
                trading_frequency=round(trading_frequency, 2),
                avg_trade_interval_hours=round(avg_trade_interval_hours, 1),
                fee_efficiency=round(fee_efficiency, 3)
            )

        except Exception as e:
            logger.error(f"AI 분석 데이터 생성 실패: {str(e)}")
            return AIAnalysisData(
                total_trades_count=0,
                buy_trades_count=0,
                sell_trades_count=0,
                avg_trade_amount=0.0,
                avg_trade_quantity=0.0,
                total_fees_paid=0.0,
                recent_activity_score=0.0,
                buy_sell_ratio=0.0,
                trading_frequency=0.0,
                avg_trade_interval_hours=0.0,
                fee_efficiency=0.0
            )
