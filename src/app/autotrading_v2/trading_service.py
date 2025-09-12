"""
거래 실행 서비스 V2
바이낸스 API를 통해 실제 매수/매도 주문을 실행
"""

import os
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from fastapi.concurrency import run_in_threadpool
from src.app.autotrading_v2.repository import TradingRepository
from src.common.utils.logger import set_logger
from src.common.utils.bitcoin.binace import BinanceUtils
from src.app.autotrading_v2.models import TradeExecutionRequest, TradeExecutionResponse

logger = set_logger("trading_service_v2")


class TradingService:
    """거래 실행 서비스 V2"""

    def __init__(self):
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.secret = os.getenv("BINANCE_SECRET_KEY")
        self.trading_repository = TradingRepository(logger)

        if self.api_key and self.secret:
            logger.info(f"환경변수에서 바이낸스 API 키를 로드했습니다: {self.api_key[:8]}***{self.api_key[-4:]}")
        else:
            logger.warning("환경변수에 BINANCE_API_KEY 또는 BINANCE_SECRET_KEY가 설정되지 않았습니다.")

    async def execute_trade(self, request: TradeExecutionRequest) -> TradeExecutionResponse:
        """거래 실행"""
        try:
            logger.info(f"거래 실행 시작: {request.action} {request.market} {request.amount_quote} USDT")

            # API 키 확인
            if not self.api_key or not self.secret:
                return TradeExecutionResponse(
                    status="error",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    action=request.action,
                    market=request.market,
                    amount_quote=request.amount_quote,
                    order_id=None,
                    executed_amount=None,
                    executed_price=None,
                    commission=None,
                    order_status=None,
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
                    return TradeExecutionResponse(
                        status="error",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        action=request.action,
                        market=request.market,
                        amount_quote=request.amount_quote,
                        order_id=None,
                        executed_amount=None,
                        executed_price=None,
                        commission=None,
                        order_status=None,
                        metadata={
                            "error": f"바이낸스 API 연결 실패: {health_check.get('error', 'Unknown error')}",
                            "suggestion": "API 키 권한, IP 제한을 확인해주세요."
                        }
                    )
            except Exception as health_error:
                return TradeExecutionResponse(
                    status="error",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    action=request.action,
                    market=request.market,
                    amount_quote=request.amount_quote,
                    order_id=None,
                    executed_amount=None,
                    executed_price=None,
                    commission=None,
                    order_status=None,
                    metadata={
                        "error": f"바이낸스 API 연결 테스트 실패: {str(health_error)}",
                        "suggestion": "API 키 권한, IP 제한을 확인해주세요."
                    }
                )

            # 거래 실행
            if request.action == "BUY":
                result = await self._execute_buy_order(binance_utils, request)
            elif request.action == "SELL":
                result = await self._execute_sell_order(binance_utils, request)
            else:
                return TradeExecutionResponse(
                    status="error",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    action=request.action,
                    market=request.market,
                    amount_quote=request.amount_quote,
                    order_id=None,
                    executed_amount=None,
                    executed_price=None,
                    commission=None,
                    order_status=None,
                    metadata={"error": f"지원하지 않는 거래 액션: {request.action}"}
                )
            try:
                await self.save_trade_execution(result)
            except Exception as e:
                logger.error(f"데이터베이스 저장 실패: {e}")

            return result

        except Exception as e:
            logger.error(f"거래 실행 실패: {e}")
            return TradeExecutionResponse(
                status="error",
                timestamp=datetime.now(timezone.utc).isoformat(),
                action=request.action,
                market=request.market,
                amount_quote=request.amount_quote,
                order_id=None,
                executed_amount=None,
                executed_price=None,
                commission=None,
                order_status=None,
                metadata={"error": f"거래 실행 중 오류가 발생했습니다: {str(e)}"}
            )

    async def _execute_buy_order(self, binance_utils: BinanceUtils, request: TradeExecutionRequest) -> TradeExecutionResponse:
        """매수 주문 실행"""
        try:
            # 직접 ccxt를 사용해서 현재 가격 조회
            import ccxt
            exchange = ccxt.binance({
                'apiKey': self.api_key or '',
                'secret': self.secret or '',
                'sandbox': False,
                'enableRateLimit': True,
            })

            ticker = await run_in_threadpool(exchange.fetch_ticker, request.market)
            current_price = float(str(ticker.get("last", 0)))

            if current_price <= 0:
                return TradeExecutionResponse(
                    status="error",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    action=request.action,
                    market=request.market,
                    amount_quote=request.amount_quote,
                    order_id=None,
                    executed_amount=None,
                    executed_price=None,
                    commission=None,
                    order_status=None,
                    metadata={"error": f"가격 조회 실패: {request.market}"}
                )

            # USDT 금액을 BTC 수량으로 변환
            btc_quantity = request.amount_quote / current_price

            # 시장가 매수 주문 실행
            order_result = await binance_utils.place_market_order(
                market=request.market,
                side='buy',
                quantity=btc_quantity  # BTC 수량으로 매수
            )

            logger.info(f"매수 주문 성공: {order_result}")

            return TradeExecutionResponse(
                status="success",
                timestamp=datetime.now(timezone.utc).isoformat(),
                action=request.action,
                market=request.market,
                amount_quote=request.amount_quote,
                order_id=order_result.get("id"),
                executed_amount=order_result.get("filled"),
                executed_price=order_result.get("average"),
                commission=order_result.get("fee", {}).get("cost"),
                order_status=order_result.get("status"),
                metadata={
                    "reason": request.reason,
                    "evidence": request.evidence,
                    "order_details": order_result
                }
            )

        except Exception as e:
            logger.error(f"매수 주문 실패: {e}")
            return TradeExecutionResponse(
                status="error",
                timestamp=datetime.now(timezone.utc).isoformat(),
                action=request.action,
                market=request.market,
                amount_quote=request.amount_quote,
                order_id=None,
                executed_amount=None,
                executed_price=None,
                commission=None,
                order_status=None,
                metadata={"error": f"매수 주문 실패: {str(e)}"}
            )

    async def _execute_sell_order(self, binance_utils: BinanceUtils, request: TradeExecutionRequest) -> TradeExecutionResponse:
        """매도 주문 실행"""
        try:
            # 현재 잔고 확인
            account_info = await binance_utils.get_account_info()
            free_balance = account_info.get("free_balance", {})

            # 매도할 자산 추출 (예: BTC/USDT에서 BTC)
            base_asset = request.market.split("/")[0]
            available_balance = float(free_balance.get(base_asset, 0))

            if available_balance <= 0:
                return TradeExecutionResponse(
                    status="error",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    action=request.action,
                    market=request.market,
                    amount_quote=request.amount_quote,
                    order_id=None,
                    executed_amount=None,
                    executed_price=None,
                    commission=None,
                    order_status=None,
                    metadata={"error": f"{base_asset} 잔고가 부족합니다. 사용 가능: {available_balance}"}
                )

            # 매도할 수량 계산 (USDT 기준으로 BTC 수량 계산)
            # request.amount_quote는 USDT 금액, 이를 BTC 수량으로 변환
            # 직접 ccxt를 사용해서 현재 가격 조회
            import ccxt
            exchange = ccxt.binance({
                'apiKey': self.api_key or '',
                'secret': self.secret or '',
                'sandbox': False,
                'enableRateLimit': True,
            })

            ticker = await run_in_threadpool(exchange.fetch_ticker, request.market)
            current_price = float(str(ticker.get("last", 0)))

            if current_price <= 0:
                return TradeExecutionResponse(
                    status="error",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    action=request.action,
                    market=request.market,
                    amount_quote=request.amount_quote,
                    order_id=None,
                    executed_amount=None,
                    executed_price=None,
                    commission=None,
                    order_status=None,
                    metadata={"error": f"가격 조회 실패: {request.market}"}
                )

            btc_quantity = request.amount_quote / current_price

            # 잔고 부족 체크
            if btc_quantity > available_balance:
                return TradeExecutionResponse(
                    status="error",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    action=request.action,
                    market=request.market,
                    amount_quote=request.amount_quote,
                    order_id=None,
                    executed_amount=None,
                    executed_price=None,
                    commission=None,
                    order_status=None,
                    metadata={"error": f"매도 수량이 잔고를 초과합니다. 요청: {btc_quantity:.8f} {base_asset}, 보유: {available_balance:.8f} {base_asset}"}
                )

            # 시장가 매도 주문 실행
            order_result = await binance_utils.place_market_order(
                market=request.market,
                side='sell',
                quantity=btc_quantity  # 정확한 수량만 매도
            )

            logger.info(f"매도 주문 성공: {order_result}")

            return TradeExecutionResponse(
                status="success",
                timestamp=datetime.now(timezone.utc).isoformat(),
                action=request.action,
                market=request.market,
                amount_quote=request.amount_quote,
                order_id=order_result.get("id"),
                executed_amount=order_result.get("filled"),
                executed_price=order_result.get("average"),
                commission=order_result.get("fee", {}).get("cost"),
                order_status=order_result.get("status"),
                metadata={
                    "reason": request.reason,
                    "evidence": request.evidence,
                    "available_balance": available_balance,
                    "order_details": order_result
                }
            )

        except Exception as e:
            logger.error(f"매도 주문 실패: {e}")
            return TradeExecutionResponse(
                status="error",
                timestamp=datetime.now(timezone.utc).isoformat(),
                action=request.action,
                market=request.market,
                amount_quote=request.amount_quote,
                order_id=None,
                executed_amount=None,
                executed_price=None,
                commission=None,
                order_status=None,
                metadata={"error": f"매도 주문 실패: {str(e)}"}
            )

    async def save_trade_execution(self, result: TradeExecutionResponse):
        """거래 실행 결과 저장"""
        try:
            logger.info(f"거래 실행 결과 저장: {result}")
            # await self.trading_repository.save_trade_execution(result.cycle_id, result.position_id, result.action, result.market, result.quantity, result.price, result.value_usdt, result.fee_usdt, result.binance_order_id, result.timestamp, result.metadata)
        except Exception as e:
            logger.error(f"거래 실행 결과 저장 실패: {e}")


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
                "service": "trading_service_v2"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "api_key_configured": bool(self.api_key and self.secret),
                "connection_status": "error",
                "service": "trading_service_v2",
                "error": str(e)
            }
