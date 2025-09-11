from src.app.user.model import User


class UserRepository:
    def __init__(self, logger):
        self.logger = logger
        pass

    async def get_user_by_user_idx(self, session, user_idx: int):
        query = """
            SELECT id, user_id
            FROM user_master
            WHERE id = $1
        """
        return await session.fetchrow(query, user_idx)

    async def get_user_by_user_id(
            self,
            session,
            user_id: str,
            status: bool = True
    ):
        query = """
            SELECT id, user_id
            FROM user_master
            WHERE user_id = $1
                AND status = $2
        """
        return await session.fetchrow(query, user_id, status)
    async def get_user_by_user_id_and_password(self, session, user_id: str, user_password: str, status: bool = True):
        query = """
            SELECT id, user_id
            FROM user_master
            WHERE user_id = $1
                AND password = $2
                AND status = $3
        """
        return await session.fetchrow(query, user_id, user_password, status)


    async def create_user(self, session, user: User):
        query = """
            INSERT INTO user_master (user_id, password, name, memo, role, created_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
        """
        return await session.execute(query, user.id, user.password, user.name, user.memo, user.role)

    async def get_user_account_state(self, session, user_idx: int):
        query = """
            SELECT
                -- COALESCE: 만약 LEFT JOIN 결과가 NULL이면 (포지션이 없으면), '[]' (빈 JSON 배열)을 반환합니다.
                COALESCE(p.positions_data, '[]'::json) AS positions,

                -- 만약 스냅샷이 없으면, 현금 보유액을 0으로 간주합니다.
                COALESCE(s.usdt_balance, 0.0)::numeric AS cash_balance,

                -- 마지막 거래 기록이 없으면, NULL을 반환합니다. 이는 "거래한 적 없음"을 의미하는 명확한 신호입니다.
                t.last_trade_timestamp

            FROM
                -- 조회 기준이 되는 user_master 테이블부터 시작하여 항상 1개의 행이 반환되도록 보장합니다.
                user_master um
            LEFT JOIN
                -- 이 서브쿼리는 유저별로 'OPEN' 상태인 포지션들을 단 하나의 JSON 배열로 묶어주는 역할을 합니다.
                (
                    SELECT
                        tc.user_id,
                        json_agg(json_build_object(
                            'market', p.market,
                            'quantity', p.quantity,
                            'average_buy_price', p.entry_price
                        )) AS positions_data
                    FROM positions p
                    -- trading_cycles을 통해 주인을 찾습니다.
                    JOIN trading_cycles tc ON p.entry_cycle_id = tc.id
                    WHERE p.status = 'OPEN'
                    GROUP BY tc.user_id
                ) p ON um.id = p.user_id
            LEFT JOIN
                -- 이 서브쿼리는 유저별로 가장 최근의 자산 스냅샷을 가져옵니다.
                (
                    SELECT DISTINCT ON (user_id)
                        user_id,
                        usdt_balance
                    FROM portfolio_snapshots
                    ORDER BY user_id, "timestamp" DESC
                ) s ON um.id = s.user_id
            LEFT JOIN
                -- 이 서브쿼리는 유저별로 가장 마지막 거래 시간을 찾아냅니다.
                (
                    SELECT
                        tc.user_id,
                        MAX(t."timestamp") as last_trade_timestamp
                    FROM trades t
                    JOIN trading_cycles tc ON t.cycle_id = tc.id
                    GROUP BY tc.user_id
                ) t ON um.id = t.user_id
            WHERE
                um.id = $1;
        """
        return await session.fetchrow(query, user_idx)
