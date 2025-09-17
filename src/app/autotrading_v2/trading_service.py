"""
거래 실행 서비스 V2
바이낸스 API를 통해 실제 매수/매도 주문을 실행
"""

import os
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from fastapi.concurrency import run_in_threadpool
from src.app.user.service import UserService
from src.app.autotrading_v2.repository import TradingRepository
from src.common.utils.logger import set_logger
from src.common.utils.bitcoin.binace import BinanceUtils
from src.app.autotrading_v2.models import (
    TradeExecutionRequest, TradeExecutionResponse,
    TradeExecutionData, TradeExecutionDataResponse, TradeExecutionListResponse
)
from src.package.db import connection
import json

logger = set_logger("trading_service_v2")


class TradingService:
    """거래 실행 서비스 V2"""

    def __init__(self):
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.secret = os.getenv("BINANCE_SECRET_KEY")
        self.trading_repository = TradingRepository(logger)
        self.user_service = UserService(logger)

        if self.api_key and self.secret:
            logger.info(f"환경변수에서 바이낸스 API 키를 로드했습니다: {self.api_key[:8]}***{self.api_key[-4:]}")
        else:
            logger.warning("환경변수에 BINANCE_API_KEY 또는 BINANCE_SECRET_KEY가 설정되지 않았습니다.")

    def set_api_key(self, api_key: str, secret: str):
        self.api_key = api_key
        self.secret = secret

    async def execute_trade(self, request: TradeExecutionRequest) -> TradeExecutionResponse:
        """거래 실행"""
        try:
            logger.info(f"거래 실행 시작: {request.action} {request.market} {request.amount_quote} USDT")

            user_info = await self.user_service.get_user_exchange_by_user_idx(
                user_idx=request.user_idx
            )

            if not user_info:
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
                    metadata={"error": "사용자 정보를 찾을 수 없습니다."}
                )

            self.api_key = user_info.get("access_key_ref")
            self.secret = user_info.get("secret_key_ref")

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

            self.set_api_key(api_key=self.api_key, secret=self.secret)

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
                # 거래 실행 데이터 저장
                user_idx = request.user_idx

                # 포트폴리오 스냅샷 정보를 metadata에 추가
                if 'portfolio_snapshot' not in result.metadata:
                    result.metadata['portfolio_snapshot'] = {
                        "total_value_usdt": 0.0,  # TODO: 실제 포트폴리오 값으로 업데이트
                        "asset_balances": {}  # TODO: 실제 자산 잔고로 업데이트
                    }

                await self.save_trade_execution(result, user_idx, request)
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

    async def save_trade_execution(self, result: TradeExecutionResponse, user_idx: int, request: TradeExecutionRequest, analysis_report_idx: int = 1):
        """거래 실행 결과 저장 (기존 데이터베이스 구조 사용)"""
        try:
            logger.info(f"거래 실행 결과 저장 시작: {result}")

            # 거래 실행 시간 파싱
            trade_timestamp = datetime.fromisoformat(result.timestamp.replace('Z', '+00:00'))

            async with connection() as session:
                # 1. 거래 사이클 생성
                cycle_idx = await self.trading_repository.create_trading_cycle(
                    session=session,
                    user_idx=user_idx,
                    analysis_report_idx=analysis_report_idx,
                    used_strategy_weights=result.metadata.get('strategy_weights'),
                    prime_agent_decision={
                        "action": result.action,
                        "market": result.market,
                        "amount_quote": result.amount_quote,
                        "reason": request.reason,
                        "evidence": request.evidence,
                        "timestamp": result.timestamp
                    }
                )

                # 2. 포트폴리오 스냅샷 생성 (현재 잔고 정보)
                if 'portfolio_snapshot' in result.metadata:
                    await self.trading_repository.create_portfolio_snapshot(
                        session=session,
                        cycle_idx=cycle_idx,
                        total_value_usdt=result.metadata['portfolio_snapshot'].get('total_value_usdt', 0.0),
                        asset_balances=result.metadata['portfolio_snapshot'].get('asset_balances', {})
                    )

                # 3. 거래 실행 데이터 저장
                trade_idx = await self.trading_repository.save_trade_execution(
                    session=session,
                    cycle_idx=cycle_idx,
                    action=result.action,
                    market=result.market,
                    quantity=result.executed_amount or 0.0,
                    price=result.executed_price or 0.0,
                    value_usdt=result.amount_quote,
                    fee_usdt=result.commission or 0.0,
                    exchange_order_id=result.order_id,
                    timestamp=trade_timestamp
                )

            logger.info(f"거래 실행 데이터 저장 완료: Cycle ID={cycle_idx}, Trade ID={trade_idx}")
            return {"cycle_idx": cycle_idx, "trade_idx": trade_idx}

        except Exception as e:
            logger.error(f"거래 실행 결과 저장 실패: {e}")
            raise e

    async def get_trades(
            self,
            user_idx: int,
            page: int = 1,
            page_size: int = 20,
            action: Optional[str] = None,
            market: Optional[str] = None,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None
        ) -> TradeExecutionListResponse:
        """거래 데이터 목록 조회 (기존 데이터베이스 구조 사용)"""
        try:
            async with connection() as session:
                # 거래 데이터 조회
                trades = await self.trading_repository.get_trades_by_user(
                    session=session,
                    user_idx=user_idx,
                    page=page,
                    page_size=page_size,
                    action=action,
                    market=market,
                    start_date=start_date,
                    end_date=end_date
                )

                # 전체 개수 조회
                total_count = await self.trading_repository.get_trades_count_by_user(
                    session=session,
                    user_idx=user_idx,
                    action=action,
                    market=market,
                    start_date=start_date,
                    end_date=end_date
                )

                # 응답 데이터 변환
                trade_responses = []
                for trade in trades:
                    # JSON 데이터 파싱
                    used_strategy_weights = json.loads(trade['used_strategy_weights']) if trade['used_strategy_weights'] else {}
                    prime_agent_decision = json.loads(trade['prime_agent_decision']) if trade['prime_agent_decision'] else {}
                    asset_balances = json.loads(trade['asset_balances']) if trade['asset_balances'] else {}

                    trade_response = TradeExecutionDataResponse(
                        id=trade['trade_idx'],
                        user_idx=trade['user_idx'],
                        cycle_id=trade['cycle_idx'],
                        position_id=None,  # positions 테이블과의 연동은 추후 구현
                        action=trade['action'],
                        market=trade['market'],
                        quantity=float(trade['quantity']),
                        price=float(trade['price']),
                        value_usdt=float(trade['value_usdt']),
                        fee_usdt=float(trade['fee_usdt']),
                        binance_order_id=trade['exchange_order_id'],
                        order_status=None,  # trades 테이블에는 order_status가 없음
                        reason=prime_agent_decision.get('reason', ''),
                        evidence=prime_agent_decision.get('evidence', {}),
                        ai_analysis_data={
                            "used_strategy_weights": used_strategy_weights,
                            "prime_agent_decision": prime_agent_decision,
                            "portfolio_snapshot": {
                                "total_value_usdt": float(trade['total_value_usdt']) if trade['total_value_usdt'] else 0.0,
                                "asset_balances": asset_balances
                            }
                        },
                        timestamp=trade['timestamp'].isoformat(),
                        created_at=trade['timestamp'].isoformat(),  # trades 테이블에는 created_at이 없음
                        metadata={
                            "cycle_idx": trade['cycle_idx'],
                            "used_strategy_weights": used_strategy_weights,
                            "prime_agent_decision": prime_agent_decision
                        }
                    )
                    trade_responses.append(trade_response)

                return TradeExecutionListResponse(
                    status="success",
                    message="거래 데이터 조회 성공",
                    data=trade_responses,
                    total_count=total_count,
                    page=page,
                    page_size=page_size,
                    metadata={
                        "filters": {
                            "action": action,
                            "market": market,
                            "start_date": start_date.isoformat() if start_date else None,
                            "end_date": end_date.isoformat() if end_date else None
                        }
                    }
                )

        except Exception as e:
            logger.error(f"거래 데이터 조회 실패: {e}")
            return TradeExecutionListResponse(
                status="error",
                message=f"거래 데이터 조회 실패: {str(e)}",
                data=[],
                total_count=0,
                page=page,
                page_size=page_size,
                metadata={}
            )

    async def get_trade_by_id(self, trade_idx: int, user_idx: int) -> Optional[TradeExecutionDataResponse]:
        """특정 거래 데이터 조회 (기존 데이터베이스 구조 사용)"""
        try:
            async with connection() as session:
                trade = await self.trading_repository.get_trade_by_id(
                    session=session,
                    trade_idx=trade_idx,
                    user_idx=user_idx
                )

                if not trade:
                    return None

                # JSON 데이터 파싱
                used_strategy_weights = json.loads(trade['used_strategy_weights']) if trade['used_strategy_weights'] else {}
                prime_agent_decision = json.loads(trade['prime_agent_decision']) if trade['prime_agent_decision'] else {}
                asset_balances = json.loads(trade['asset_balances']) if trade['asset_balances'] else {}

                return TradeExecutionDataResponse(
                    id=trade['trade_idx'],
                    user_idx=trade['user_idx'],
                    cycle_id=trade['cycle_idx'],
                    position_id=None,  # positions 테이블과의 연동은 추후 구현
                    action=trade['action'],
                    market=trade['market'],
                    quantity=float(trade['quantity']),
                    price=float(trade['price']),
                    value_usdt=float(trade['value_usdt']),
                    fee_usdt=float(trade['fee_usdt']),
                    binance_order_id=trade['exchange_order_id'],
                    order_status=None,  # trades 테이블에는 order_status가 없음
                    reason=prime_agent_decision.get('reason', ''),
                    evidence=prime_agent_decision.get('evidence', {}),
                    ai_analysis_data={
                        "used_strategy_weights": used_strategy_weights,
                        "prime_agent_decision": prime_agent_decision,
                        "portfolio_snapshot": {
                            "total_value_usdt": float(trade['total_value_usdt']) if trade['total_value_usdt'] else 0.0,
                            "asset_balances": asset_balances
                        }
                    },
                    timestamp=trade['timestamp'].isoformat(),
                    created_at=trade['timestamp'].isoformat(),  # trades 테이블에는 created_at이 없음
                    metadata={
                        "cycle_idx": trade['cycle_idx'],
                        "used_strategy_weights": used_strategy_weights,
                        "prime_agent_decision": prime_agent_decision
                    }
                )

        except Exception as e:
            logger.error(f"거래 데이터 조회 실패: {e}")
            return None


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
