"""
AI 분석 서비스 - LangChain을 사용한 차트 분석 AI 에이전트
"""
import json
import asyncio
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from src.common.utils.logger import set_logger

logger = set_logger(__name__)

class ChartAnalysisResult(BaseModel):
    """차트 분석 결과 모델"""
    agent_name: str = Field(description="에이전트 이름")
    quant_score: float = Field(description="정량적 점수 (-1 ~ +1)")
    evidence: Dict[str, Any] = Field(description="분석 근거 데이터")
    regime: str = Field(description="시장 레짐 (trend/range)")
    confidence: float = Field(description="신뢰도 (0 ~ 1)")

class RegimeWeights(BaseModel):
    """레짐별 가중치 모델"""
    range: Dict[str, str] = Field(description="횡보장 가중치")
    trend: Dict[str, str] = Field(description="추세장 가중치")

class AIChartAnalysisResult(BaseModel):
    """AI 차트 분석 최종 결과"""
    chart_result: ChartAnalysisResult
    regime_weights: RegimeWeights
    used_regime_weights: Dict[str, str]

class AIAnalysisService:
    """AI 분석 서비스"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
            max_tokens=2000
        )
        self.parser = PydanticOutputParser(pydantic_object=AIChartAnalysisResult)

    async def analyze_multiple_coins_with_ai(self, coins_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        여러 코인을 한 번에 AI로 분석 (비용 효율적)

        Args:
            coins_data: 여러 코인의 차트 분석 데이터 리스트

        Returns:
            각 코인별 AI 분석 결과
        """
        try:
            # 1. 레짐 가중치 조회
            regime_weights = await self._get_regime_weights()

            # 2. AI 프롬프트 생성 (여러 코인용)
            prompt = self._create_multi_coin_analysis_prompt(coins_data, regime_weights)

            # 3. AI 분석 실행
            messages = [
                SystemMessage(content=self._get_multi_coin_system_message()),
                HumanMessage(content=prompt)
            ]

            response = await self.llm.ainvoke(messages)

            # 4. JSON 파싱
            result = self._parse_ai_response(response.content)

            logger.info(f"✅ AI 다중 코인 분석 완료: {len(coins_data)}개 코인")
            return result

        except Exception as e:
            logger.error(f"❌ AI 다중 코인 분석 실패: {str(e)}")
            # 실패시 기본 분석 결과 반환
            return self._create_fallback_multi_analysis(coins_data)

    async def _get_regime_weights(self) -> Dict[str, Any]:
        """레짐별 가중치 조회 (내부 서비스 사용)"""
        try:
            # 내부 InformationService 직접 사용
            from src.app.information.service import InformationService
            from src.common.utils.logger import set_logger

            info_service = InformationService(set_logger(__name__))
            result = await info_service.get_chart_weights()

            if result.status == "success":
                logger.info(f"✅ 레짐별 가중치 조회 성공: {result.data}")
                return result.data
            else:
                logger.warning(f"⚠️ 가중치 조회 실패: {result.message}")
        except Exception as e:
            logger.warning(f"⚠️ 가중치 조회 실패, 기본값 사용: {str(e)}")

        # n8n과 동일한 기본 가중치 반환
        return {
            "range": {
                "RSI": "0.2500",
                "STOCHASTIC": "0.2000",
                "BOLLINGER_BANDS": "0.2500",
                "WILLIAMS_R": "0.1500",
                "CCI": "0.1000",
                "VOLUME": "0.0500"
            },
            "trend": {
                "RSI": "0.1500",
                "MACD": "0.2000",
                "ADX": "0.2500",
                "BOLLINGER_BANDS": "0.1500",
                "MOVING_AVERAGE": "0.1500",
                "VOLUME": "0.1000"
            }
        }

    def _determine_market_regime(self, chart_data: Dict[str, Any]) -> str:
        """시장 레짐 판단 (ADX 기반)"""
        try:
            indicators = chart_data.get('indicators', {})
            adx = indicators.get('adx', 0)

            # ADX 25 이상이면 trend, 미만이면 range
            return "trend" if adx >= 25 else "range"
        except Exception:
            return "range"  # 기본값

    def _create_multi_coin_analysis_prompt(self, coins_data: List[Dict[str, Any]], regime_weights: Dict[str, Any]) -> str:
        """다중 코인 AI 분석 프롬프트 생성"""

        # 각 코인별 데이터 요약
        coins_summary = []
        for coin_data in coins_data:
            indicators = coin_data.get('indicators', {})
            scores = coin_data.get('scores', {})
            regime_info = coin_data.get('regime_info', {})

            coin_summary = {
                "market": coin_data.get('market', 'Unknown'),
                "timeframe": coin_data.get('timeframe', 'Unknown'),
                "indicators": {
                    "adx": indicators.get('adx', 0),
                    "rsi": indicators.get('rsi', 0),
                    "macd": indicators.get('macd', 0),
                    "macd_histogram": indicators.get('macd_histogram', 0),
                    "bb_pct_b": indicators.get('bb_pct_b', 0),
                    "volume_z_score": indicators.get('volume_z_score', 0)
                },
                "scores": {
                    "rsi": scores.get('rsi', 0),
                    "macd": scores.get('macd', 0),
                    "bollinger": scores.get('bollinger', 0),
                    "volume": scores.get('volume', 0)
                },
                "regime": regime_info.get('regime', 'range')
            }
            coins_summary.append(coin_summary)

        prompt = f"""
Mission: Analyze multiple cryptocurrency charts and generate structured, purely analytical JSON reports for each coin. Your role is to provide objective scores based on data, not trading recommendations.

Coins Data ({len(coins_summary)} coins):
{json.dumps(coins_summary, indent=2)}

Regime Weights:
{json.dumps(regime_weights, indent=2)}

Analysis Instructions:
1. For each coin, determine the market regime based on ADX value (≥25: trend, <25: range)
2. Use the appropriate regime weights to calculate quant_score for each coin
3. Provide evidence including key technical indicators
4. Calculate confidence based on data quality and indicator consistency

CRITICAL RULES:
1. Your response MUST be ONLY the valid JSON object.
2. Do NOT include signal (BUY, SELL, HOLD) fields.
3. Each coin's regime field MUST be either "trend" or "range".
4. quant_score should be between -1 and +1 for each coin.
5. Analyze all {len(coins_summary)} coins in a single response.

Output Format:
{{
  "analysis_results": {{
    "BTC/USDT": {{
      "chart_result": {{
        "agent_name": "AXIS-Quant",
        "quant_score": 0.45,
        "evidence": {{
          "timeframe": "minutes:60",
          "regime": "trend",
          "adx": 25.1,
          "rsi": 60.3,
          "macd_histogram": 15.7,
          "confidence": 0.8
        }}
      }},
      "regime_weights": {json.dumps(regime_weights)},
      "used_regime_weights": {json.dumps(regime_weights["trend"])}
    }},
    "ETH/USDT": {{
      "chart_result": {{
        "agent_name": "AXIS-Quant",
        "quant_score": -0.23,
        "evidence": {{
          "timeframe": "minutes:60",
          "regime": "range",
          "adx": 18.5,
          "rsi": 45.2,
          "macd_histogram": -8.3,
          "confidence": 0.7
        }}
      }},
      "regime_weights": {json.dumps(regime_weights)},
      "used_regime_weights": {json.dumps(regime_weights["range"])}
    }}
  }},
  "summary": {{
    "total_coins": {len(coins_summary)},
    "trend_coins": 0,
    "range_coins": 0,
    "average_confidence": 0.0
  }}
}}
"""
        return prompt

    def _get_multi_coin_system_message(self) -> str:
        """다중 코인 분석용 시스템 메시지"""
        return """You are a JSON-only data generation AI specialized in multi-coin cryptocurrency analysis. Your ONLY purpose is to analyze multiple coins and respond with a valid JSON object.

CRITICAL RULES:
- Your response MUST be ONLY the valid JSON object.
- Your response MUST start with { and end with }.
- DO NOT include ANY text, explanations, apologies, or markdown formatting.
- Analyze ALL provided coins in a single response.
- Adhere strictly to the JSON format. Use double quotes for all keys and string values."""

    def _parse_ai_response(self, response: str) -> Dict[str, Any]:
        """AI 응답 파싱"""
        try:
            # JSON 파싱 시도
            if response.strip().startswith('```json'):
                # 마크다운 제거
                response = response.strip()[7:-3]
            elif response.strip().startswith('```'):
                response = response.strip()[3:-3]

            return json.loads(response.strip())
        except json.JSONDecodeError as e:
            logger.error(f"❌ AI 응답 JSON 파싱 실패: {str(e)}")
            logger.error(f"응답 내용: {response}")
            raise

    def _create_fallback_multi_analysis(self, coins_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """AI 분석 실패시 기본 분석 결과 (다중 코인용)"""
        analysis_results = {}

        for coin_data in coins_data:
            market = coin_data.get('market', 'Unknown')
            indicators = coin_data.get('indicators', {})
            regime = self._determine_market_regime(coin_data)

            analysis_results[market] = {
                "chart_result": {
                    "agent_name": "AXIS-Quant-Fallback",
                    "quant_score": 0.0,
                    "evidence": {
                        "timeframe": coin_data.get('timeframe', 'Unknown'),
                        "regime": regime,
                        "adx": indicators.get('adx', 0),
                        "rsi": indicators.get('rsi', 0),
                        "macd_histogram": indicators.get('macd_histogram', 0),
                        "confidence": 0.5
                    }
                },
                "regime_weights": {
                    "range": {"RSI": "0.2500", "STOCHASTIC": "0.2000", "BOLLINGER_BANDS": "0.2500", "WILLIAMS_R": "0.1500", "CCI": "0.1000", "VOLUME": "0.0500"},
                    "trend": {"RSI": "0.1500", "MACD": "0.2000", "ADX": "0.2500", "BOLLINGER_BANDS": "0.1500", "MOVING_AVERAGE": "0.1500", "VOLUME": "0.1000"}
                },
                "used_regime_weights": {
                    "RSI": "0.1500" if regime == "trend" else "0.2500",
                    "MACD": "0.2000" if regime == "trend" else "0.0000",
                    "ADX": "0.2500" if regime == "trend" else "0.0000",
                    "BOLLINGER_BANDS": "0.1500",
                    "MOVING_AVERAGE": "0.1500" if regime == "trend" else "0.0000",
                    "VOLUME": "0.1000" if regime == "trend" else "0.0500"
                }
            }

        return {
            "analysis_results": analysis_results,
            "summary": {
                "total_coins": len(coins_data),
                "trend_coins": sum(1 for coin in coins_data if self._determine_market_regime(coin) == "trend"),
                "range_coins": sum(1 for coin in coins_data if self._determine_market_regime(coin) == "range"),
                "average_confidence": 0.5
            }
        }
