from fastapi import APIRouter, Depends, Request
from src.common.utils.response import JSendResponse
from src.app.information import service as information_service
from src.app.user import service as user_service
from src.common.utils.logger import set_logger

router = APIRouter()
logger = set_logger("information_router")

"""
필요한 데이터베이스 접근 API
- 분석 에이전트가 사용할만한 레짐 필터링 가중치 조회, 업데이트
- 각각의 분석 에이전트들에 대한 분석 내용 및 판단 근거 조회
"""

def get_information_service():
    return information_service.InformationService(logger)


def get_user_service():
    return user_service.UserService(logger)



@router.get(
    "/information/weights/strategy/{personality}",
    tags=["Information"],
    summary="특정 투자 성향에 해당하는 전략적 가중치를 조회합니다.",
    description="특정 투자 성향에 해당하는 전략적 가중치를 조회합니다.",
)
async def get_strategy_weights(
        personality: str,
        information_service: information_service.InformationService = Depends(get_information_service)
    ) -> JSendResponse:
    return await information_service.get_strategy_weights(personality)

#차트 분석 에이전트 필요 데이터 GET
@router.get(
    "/information/weights/chart",
    tags=["Information"],
    summary="차트 분석 에이전트 필요 가중치 데이터를 조회합니다.",
    description="차트 분석 에이전트 필요 가중치 데이터를 조회합니다.",
)
async def get_chart_weights(
    information_service: information_service.InformationService = Depends(get_information_service)
):
    return await information_service.get_chart_weights()


#유저 정보 가져오기
@router.get(
    "/information/users/{user_idx}",
    tags=["Information"],
    summary="특정 유저의 정보를 조회합니다.",
    description="특정 유저의 정보를 조회합니다.",
)
async def get_regime_weights(
    user_idx: int,
    user_service: user_service.UserService = Depends(get_user_service)
) -> JSendResponse:
    return await user_service.get_user_trading_info(user_idx)




# GET /weights/strategy/{personality}
# 설명: 특정 투자 성향(aggressive, neutral 등)에 해당하는 전략적 가중치를 조회합니다.

# 사용 주체: The Brain (마스터 에이전트)

# 근거: The Brain이 의사결정을 내리기 직전, strategy_weights 테이블에서 현재 적용할 가중치(weight_quant, weight_social 등)를 가져오기 위해 사용합니다.

# GET /weights/regime/{regime_type}
# 설명: 시장 레짐(trend 또는 range)에 해당하는 전술적 가중치 목록을 조회합니다.

# 사용 주체: AXIS-Quant (퀀트 분석 에이전트)

# 근거: AXIS-Quant가 시장 레짐을 판단한 후, regime_weights_trend 또는 regime_weights_range 테이블에서 어떤 기술 지표에 더 높은 가중치를 부여할지 동적으로 가져오기 위해 사용합니다.

# PUT /weights/strategy/{personality}
# 설명: 특정 투자 성향의 전략적 가중치를 업데이트합니다.

# 사용 주체: Learning Agent (학습 에이전트) 또는 관리자

# 근거: 자가 학습 루프가 과거 성과를 분석한 결과, 특정 가중치를 수정하는 것이 더 낫다고 판단했을 때 AI의 두뇌를 직접 수정하기 위해 사용합니다.