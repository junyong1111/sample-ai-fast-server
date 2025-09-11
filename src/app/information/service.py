import io
import re
from typing import List, Union

from src.common.utils.response import JSendResponse
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
        ) -> JSendResponse:
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
            weights = {
                "weight_quant": weights.get("weight_quant"),
                "weight_social": weights.get("weight_social"),
                "weight_risk": weights.get("weight_risk")
            }
            message = "전략적 가중치를 성공적으로 조회했습니다."

        return JSendResponse(
            status="success",
            message=message,
            data=weights,
        )
    async def get_chart_weights(
        self
    ) -> JSendResponse:
        self.logger.info("차트 분석 에이전트 필요 가중치 데이터를 조회합니다.")
        async with connection() as session:
            weights = await self.information_repo.get_chart_weights(
                session=session
            )

        chart_weights = {
            "range": {},
            "trend": {}
        }
        for weight in weights:
            if weight.get("regime") == "range":
                chart_weights["range"][weight.get("indicator")] = weight.get("weight")
            elif weight.get("regime") == "trend":
                chart_weights["trend"][weight.get("indicator")] = weight.get("weight")

        return JSendResponse(
            status="success",
            data=chart_weights
        )