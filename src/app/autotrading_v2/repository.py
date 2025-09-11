class TradingRepository:
    def __init__(self, logger):
        self.logger = logger
        pass

    async def save_trade_execution(
            self,
            session,
            cycle_id,
            position_id,
            action,
            market,
            quantity,
            price,
            value_usdt,
            fee_usdt,
            binance_order_id,
            timestamp,
            metadata
        ):
        """
        1	id	int4	NO	NULL	"nextval('trades_id_seq'::regclass)"		NULL
        2	cycle_id	int4	NO	NULL	NULL	public.trading_cycles(id)	NULL
        3	position_id	int4	YES	NULL	NULL	public.positions(id)	NULL
        4	timestamp	timestamptz	NO	NULL	now()		NULL
        5	market	varchar(20)	NO	NULL	NULL		NULL
        6	action	varchar(10)	NO	NULL	NULL		NULL
        7	quantity	numeric(20,10)	NO	NULL	NULL		NULL
        8	price	numeric(20,8)	NO	NULL	NULL		NULL
        9	value_usdt	numeric(20,8)	NO	NULL	NULL		NULL
        10	fee_usdt	numeric(10,8)	NO	NULL	NULL		NULL
        11	binance_order_id	varchar(255)	YES	NULL	NULL		NULL
        """

        query = """
            INSERT INTO trades (cycle_id, position_id, timestamp, market, action, quantity, price, value_usdt, fee_usdt, binance_order_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)

            RETURNING id
        """
        return await session.execute(query, cycle_id, position_id, timestamp, market, action, quantity, price, value_usdt, fee_usdt, binance_order_id, metadata)