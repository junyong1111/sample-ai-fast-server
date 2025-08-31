"""
자동 매매 서비스
거래 신호를 기반으로 Binance API를 통해 자동 매매 실행
"""

import asyncio
from typing import Dict, Any, Optional, Literal
from datetime import datetime, timezone
from src.common.utils.bitcoin.binace import BinanceUtils
from src.config.setting import settings


class TradingService:
    """자동 매매 서비스"""

    def __init__(self, testnet: bool = True):
        """
        거래 서비스 초기화

        Args:
            testnet: 테스트넷 사용 여부 (기본값: True)
        """
        self.testnet = testnet

        # Binance API 설정
        if testnet:
            api_key = settings.BINANCE_TESTNET_API_KEY
            secret_key = settings.BINANCE_TESTNET_SECRET_KEY
        else:
            api_key = settings.BINANCE_API_KEY
            secret_key = settings.BINANCE_SECRET_KEY

        # Binance 유틸리티 초기화
        self.binance = BinanceUtils(
            api_key=api_key,
            secret=secret_key,
            testnet=testnet
        )

    async def get_account_status(self) -> Dict[str, Any]:
        """계정 상태 확인"""
        try:
            account_info = await self.binance.get_account_info()
            return {
                "status": "success",
                "testnet": self.testnet,
                "account_info": account_info,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "testnet": self.testnet,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    async def execute_trading_signal(
        self,
        market: str,
        signal: str,
        quantity: float,
        order_type: Literal['market', 'limit'] = 'market',
        price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        거래 신호에 따른 매매 실행

        Args:
            market: 거래 마켓 (예: 'BTC/USDT')
            signal: 거래 신호 ('BUY', 'SELL', 'HOLD')
            quantity: 거래 수량
            order_type: 주문 타입 ('market' 또는 'limit')
            price: 지정가 주문 시 가격 (order_type이 'limit'일 때만)

        Returns:
            거래 실행 결과
        """
        try:
            if signal == "HOLD":
                return {
                    "status": "skipped",
                    "reason": "HOLD signal - no action taken",
                    "market": market,
                    "signal": signal,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }

            # 거래 방향 결정
            side = "buy" if signal == "BUY" else "sell"

            # 주문 실행
            if order_type == "market":
                result = await self.binance.place_market_order(market, side, quantity)
            elif order_type == "limit" and price:
                result = await self.binance.place_limit_order(market, side, quantity, price)
            else:
                raise ValueError("Invalid order type or missing price for limit order")

            return {
                "status": "success",
                "market": market,
                "signal": signal,
                "order_type": order_type,
                "side": side,
                "quantity": quantity,
                "price": price if order_type == "limit" else None,
                "order_result": result,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            return {
                "status": "error",
                "market": market,
                "signal": signal,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    async def get_order_status(self, order_id: str, market: str) -> Dict[str, Any]:
        """주문 상태 조회"""
        try:
            status = await self.binance.get_order_status(order_id, market)
            return {
                "status": "success",
                "order_status": status,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    async def cancel_order(self, order_id: str, market: str) -> Dict[str, Any]:
        """주문 취소"""
        try:
            result = await self.binance.cancel_order(order_id, market)
            return {
                "status": "success",
                "cancel_result": result,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    async def get_open_orders(self, market: Optional[str] = None) -> Dict[str, Any]:
        """미체결 주문 조회"""
        try:
            orders = await self.binance.get_open_orders(market)
            return {
                "status": "success",
                "open_orders": orders,
                "count": len(orders),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    async def execute_strategy(
        self,
        market: str,
        signal_data: Dict[str, Any],
        risk_per_trade: float = 0.01,
        order_type: Literal['market', 'limit'] = 'market'
    ) -> Dict[str, Any]:
        """
        거래 전략 실행 (리스크 관리 포함)

        Args:
            market: 거래 마켓
            signal_data: 거래 신호 데이터
            risk_per_trade: 거래당 리스크 비율 (기본값: 1%)
            order_type: 주문 타입

        Returns:
            전략 실행 결과
        """
        try:
            # 계정 잔고 조회
            account_info = await self.binance.get_account_info()

            # USDT 잔고 확인
            usdt_balance = account_info.get('free_balance', {}).get('USDT', 0)

            if usdt_balance <= 0:
                return {
                    "status": "error",
                    "reason": "Insufficient USDT balance",
                    "usdt_balance": usdt_balance,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }

            # 거래 신호 추출
            overall_signal = signal_data.get('overall_signal', 'HOLD')

            # 리스크 기반 거래 수량 계산
            risk_amount = usdt_balance * risk_per_trade

            # 현재 가격 조회
            ticker = await self.binance.get_ticker(market)
            current_price = ticker.get('last', 0)

            if current_price <= 0:
                return {
                    "status": "error",
                    "reason": "Invalid current price",
                    "current_price": current_price,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }

            # 거래 수량 계산 (USDT 기준)
            quantity = risk_amount / current_price

            # 거래 실행
            trading_result = await self.execute_trading_signal(
                market=market,
                signal=overall_signal,
                quantity=quantity,
                order_type=order_type,
                price=current_price if order_type == 'limit' else None
            )

            return {
                "status": "success",
                "strategy_execution": {
                    "market": market,
                    "signal": overall_signal,
                    "usdt_balance": usdt_balance,
                    "risk_amount": risk_amount,
                    "current_price": current_price,
                    "quantity": quantity,
                    "order_type": order_type
                },
                "trading_result": trading_result,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
