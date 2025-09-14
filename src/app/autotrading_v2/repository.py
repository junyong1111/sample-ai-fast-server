from typing import List, Optional, Dict, Any
from datetime import datetime
import json


class TradingRepository:
    def __init__(self, logger):
        self.logger = logger
        pass

    async def save_trade_execution(
            self,
            session,
            cycle_idx: int,
            action: str,
            market: str,
            quantity: float,
            price: float,
            value_usdt: float,
            fee_usdt: float,
            exchange_order_id: Optional[str],
            timestamp: datetime
        ):
        """
        거래 실행 데이터를 trades 테이블에 저장
        """
        query = """
            INSERT INTO trades (
                cycle_idx, timestamp, market, action, quantity, price,
                value_usdt, fee_usdt, exchange_order_id
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING idx
        """

        return await session.fetchval(
            query,
            cycle_idx, timestamp, market, action, quantity, price,
            value_usdt, fee_usdt, exchange_order_id
        )

    async def create_trading_cycle(
            self,
            session,
            user_idx: int,
            analysis_report_idx: int,
            used_strategy_weights: Optional[Dict[str, Any]] = None,
            prime_agent_decision: Optional[Dict[str, Any]] = None
        ):
        """
        거래 사이클 생성
        """
        query = """
            INSERT INTO trading_cycles (
                user_idx, analysis_report_idx, used_strategy_weights, prime_agent_decision
            )
            VALUES ($1, $2, $3, $4)
            RETURNING idx
        """

        # JSON 데이터를 문자열로 변환
        weights_json = json.dumps(used_strategy_weights) if used_strategy_weights else None
        decision_json = json.dumps(prime_agent_decision) if prime_agent_decision else None

        return await session.fetchval(
            query,
            user_idx, analysis_report_idx, weights_json, decision_json
        )

    async def create_portfolio_snapshot(
            self,
            session,
            cycle_idx: int,
            total_value_usdt: float,
            asset_balances: Dict[str, Any]
        ):
        """
        포트폴리오 스냅샷 생성
        """
        query = """
            INSERT INTO portfolio_snapshots (
                cycle_idx, total_value_usdt, asset_balances
            )
            VALUES ($1, $2, $3)
            RETURNING idx
        """

        balances_json = json.dumps(asset_balances) if asset_balances else None

        return await session.fetchval(
            query,
            cycle_idx, total_value_usdt, balances_json
        )

    async def get_trades_by_user(
            self,
            session,
            user_idx: int,
            page: int = 1,
            page_size: int = 20,
            action: Optional[str] = None,
            market: Optional[str] = None,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None
        ) -> List[Dict[str, Any]]:
        """
        사용자별 거래 데이터 조회 (trades 테이블과 trading_cycles 조인)
        """
        offset = (page - 1) * page_size

        where_conditions = ["tc.user_idx = $1"]
        params: List[Any] = [user_idx]
        param_count = 1

        if action:
            param_count += 1
            where_conditions.append(f"t.action = ${param_count}")
            params.append(action)

        if market:
            param_count += 1
            where_conditions.append(f"t.market = ${param_count}")
            params.append(market)

        if start_date:
            param_count += 1
            where_conditions.append(f"t.timestamp >= ${param_count}")
            params.append(start_date)

        if end_date:
            param_count += 1
            where_conditions.append(f"t.timestamp <= ${param_count}")
            params.append(end_date)

        where_clause = " AND ".join(where_conditions)

        query = f"""
            SELECT
                t.idx as trade_idx, t.cycle_idx, t.timestamp, t.market, t.action,
                t.quantity, t.price, t.value_usdt, t.fee_usdt, t.exchange_order_id,
                tc.user_idx, tc.used_strategy_weights, tc.prime_agent_decision,
                ps.total_value_usdt, ps.asset_balances
            FROM trades t
            JOIN trading_cycles tc ON t.cycle_idx = tc.idx
            LEFT JOIN portfolio_snapshots ps ON t.cycle_idx = ps.cycle_idx
            WHERE {where_clause}
            ORDER BY t.timestamp DESC
            LIMIT ${param_count + 1} OFFSET ${param_count + 2}
        """

        params.extend([page_size, offset])

        return await session.fetch(query, *params)

    async def get_trades_count_by_user(
            self,
            session,
            user_idx: int,
            action: Optional[str] = None,
            market: Optional[str] = None,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None
        ) -> int:
        """
        사용자별 거래 데이터 개수 조회
        """
        where_conditions = ["tc.user_idx = $1"]
        params: List[Any] = [user_idx]
        param_count = 1

        if action:
            param_count += 1
            where_conditions.append(f"t.action = ${param_count}")
            params.append(action)

        if market:
            param_count += 1
            where_conditions.append(f"t.market = ${param_count}")
            params.append(market)

        if start_date:
            param_count += 1
            where_conditions.append(f"t.timestamp >= ${param_count}")
            params.append(start_date)

        if end_date:
            param_count += 1
            where_conditions.append(f"t.timestamp <= ${param_count}")
            params.append(end_date)

        where_clause = " AND ".join(where_conditions)

        query = f"""
            SELECT COUNT(*)
            FROM trades t
            JOIN trading_cycles tc ON t.cycle_idx = tc.idx
            WHERE {where_clause}
        """

        return await session.fetchval(query, *params)

    async def get_trade_by_id(
            self,
            session,
            trade_idx: int,
            user_idx: int
        ) -> Optional[Dict[str, Any]]:
        """
        특정 거래 데이터 조회
        """
        query = """
            SELECT
                t.idx as trade_idx, t.cycle_idx, t.timestamp, t.market, t.action,
                t.quantity, t.price, t.value_usdt, t.fee_usdt, t.exchange_order_id,
                tc.user_idx, tc.used_strategy_weights, tc.prime_agent_decision,
                ps.total_value_usdt, ps.asset_balances
            FROM trades t
            JOIN trading_cycles tc ON t.cycle_idx = tc.idx
            LEFT JOIN portfolio_snapshots ps ON t.cycle_idx = ps.cycle_idx
            WHERE t.idx = $1 AND tc.user_idx = $2
        """

        return await session.fetchrow(query, trade_idx, user_idx)

    async def create_position(
            self,
            session,
            user_idx: int,
            market: str,
            entry_cycle_idx: int,
            entry_timestamp: datetime,
            entry_price: float,
            quantity: float
        ):
        """
        포지션 생성
        """
        query = """
            INSERT INTO positions (
                user_idx, market, status, entry_cycle_idx, entry_timestamp,
                entry_price, quantity
            )
            VALUES ($1, $2, 'OPEN', $3, $4, $5, $6)
            RETURNING idx
        """

        return await session.fetchval(
            query,
            user_idx, market, entry_cycle_idx, entry_timestamp, entry_price, quantity
        )

    async def close_position(
            self,
            session,
            position_idx: int,
            exit_cycle_idx: int,
            exit_timestamp: datetime,
            exit_price: float,
            realized_pnl_usdt: float
        ):
        """
        포지션 종료
        """
        query = """
            UPDATE positions
            SET status = 'CLOSED', exit_cycle_idx = $1, exit_timestamp = $2,
                exit_price = $3, realized_pnl_usdt = $4
            WHERE idx = $5
            RETURNING idx
        """

        return await session.fetchval(
            query,
            exit_cycle_idx, exit_timestamp, exit_price, realized_pnl_usdt, position_idx
        )

    async def get_user_trading_summary(
            self,
            session,
            user_idx: int
        ) -> Dict[str, Any]:
        """
        사용자별 거래 요약 정보 조회 (모든 테이블 JOIN)
        """
        query = """
            SELECT
                tc.idx as cycle_idx,
                tc.user_idx,
                tc.timestamp as cycle_timestamp,
                tc.used_strategy_weights,
                tc.prime_agent_decision,
                ps.total_value_usdt,
                ps.asset_balances,
                COUNT(t.idx) as trade_count,
                SUM(CASE WHEN t.action = 'BUY' THEN t.value_usdt ELSE 0 END) as total_buy_value,
                SUM(CASE WHEN t.action = 'SELL' THEN t.value_usdt ELSE 0 END) as total_sell_value,
                SUM(t.fee_usdt) as total_fees
            FROM trading_cycles tc
            LEFT JOIN portfolio_snapshots ps ON tc.idx = ps.cycle_idx
            LEFT JOIN trades t ON tc.idx = t.cycle_idx
            WHERE tc.user_idx = $1
            GROUP BY tc.idx, tc.user_idx, tc.timestamp, tc.used_strategy_weights,
                     tc.prime_agent_decision, ps.total_value_usdt, ps.asset_balances
            ORDER BY tc.timestamp DESC
        """

        return await session.fetch(query, user_idx)