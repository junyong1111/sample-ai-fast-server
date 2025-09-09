

class InformationRepository:
    def __init__(self, logger):
        self.logger = logger

    async def get_strategy_weights(
            self,
            session,
            personality: str
        ) -> str:
        self.logger.info(f"특정 투자 성향에 해당하는 전략적 가중치를 조회합니다.: {personality}")
        query = """
            SELECT weight_quant, weight_social, weight_risk
            FROM strategy_weights
            WHERE personality = $1 AND is_active = TRUE
        """
        return await session.fetchrow(query, personality)
