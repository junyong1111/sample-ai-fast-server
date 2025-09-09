import io
import re
from typing import List, Union

from fastapi.responses import JSONResponse
from src.app.information.repository import InformationRepository
from src.package.db import connection, transaction

# -------- 전처리: 코드펜스/개행/백슬래시 제거 --------
class InformationService:
    def __init__(self, logger):
        self.logger = logger
        self.information_repo = InformationRepository(logger)

    async def get_strategy_weights(
            self,
            personality: str
        ) -> JSONResponse:
        self.logger.info(f"특정 투자 성향에 해당하는 전략적 가중치를 조회합니다.: {personality}")
        async with connection() as session:
            weights = await self.information_repo.get_strategy_weights(
                session=session,
                personality=personality
            )
        message = ""
        if not weights:
            #1만약 전략적 가중치가 없다면 기본값 33.3, 33.3, 33.3 으로 설정
            message = "특정 투자 성향에 해당하는 전략적 가중치를 조회할 수 없습니다. 기본값 33.3, 33.3, 33.3 으로 설정합니다."
            weights = {
                "weight_quant": 0.33,
                "weight_social": 0.33,
                "weight_risk": 0.33
            }
        else:
            # asyncpg.Record를 딕셔너리로 변환하고 Decimal을 float로 변환
            weights_dict = {}
            for key, value in weights.items():
                weights_dict[key] = float(value)
            weights = weights_dict
            message = "전략적 가중치를 성공적으로 조회했습니다."

        return JSONResponse(
            content={
                "status": "success",
                "message": message,
                "data": weights
            }
        )