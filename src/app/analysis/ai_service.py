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

    async def analyze_multiple_coins_risk_with_ai(self, coins_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        여러 코인을 한 번에 AI로 리스크 분석 (비용 효율적)
        """
        try:
            prompt = self._create_multi_coin_risk_analysis_prompt(coins_data)
            messages = [
                SystemMessage(content=self._get_multi_coin_risk_system_message()),
                HumanMessage(content=prompt)
            ]
            response = await self.llm.ainvoke(messages)
            result = self._parse_ai_response(response.content)
            logger.info(f"✅ AI 다중 코인 리스크 분석 완료: {len(coins_data)}개 코인")
            return result
        except Exception as e:
            logger.error(f"❌ AI 다중 코인 리스크 분석 실패: {str(e)}")
            return self._create_fallback_multi_risk_analysis(coins_data)

    def _create_multi_coin_risk_analysis_prompt(self, coins_data: List[Dict[str, Any]]) -> str:
        """다중 코인 AI 리스크 분석 프롬프트 생성"""
        coins_summary = []
        for coin_data in coins_data:
            coin_summary = {
                "market": coin_data.get('market', 'Unknown'),
                "analysis_type": coin_data.get('analysis_type', 'daily'),
                "days_back": coin_data.get('days_back', 90),
                "personality": coin_data.get('personality', 'conservative'),
                "risk_score": coin_data.get('risk_score', 0),
                "risk_level": coin_data.get('risk_level', 'UNKNOWN'),
                "risk_off_signal": coin_data.get('risk_off_signal', False),
                "confidence": coin_data.get('confidence', 0.5)
            }
            coins_summary.append(coin_summary)

        prompt = f"""
Mission: Analyze multiple cryptocurrency risk profiles and generate structured, purely analytical JSON reports for each coin. Your role is to provide objective risk scores based on data, not trading recommendations.

Coins Data ({len(coins_summary)} coins):
{json.dumps(coins_summary, indent=2)}

Analysis Instructions:
1. For each coin, determine the risk level based on risk_score and other indicators
2. Provide evidence including risk indicators and market conditions
3. Calculate confidence based on data quality and consistency
4. Consider the personality type (conservative, aggressive, etc.)

CRITICAL RULES:
1. Your response MUST be ONLY the valid JSON object.
2. Do NOT include trading recommendations.
3. Each coin's risk_level field MUST be one of: "LOW", "MEDIUM", "HIGH", "CRITICAL".
4. risk_score should be between 0 and 100 for each coin.
5. Analyze all {len(coins_summary)} coins in a single response.

Output Format:
{{
  "analysis_results": {{
    "BTC/USDT": {{
      "risk_result": {{
        "agent_name": "AXIS-Risk",
        "risk_score": 45.5,
        "risk_level": "MEDIUM",
        "normalized_risk_score": 0.09,
        "evidence": {{
          "analysis_period": "90 days",
          "vix_index": 21.5,
          "correlation_btc_ndx": 0.65,
          "confidence": 0.8
        }}
      }}
    }},
    "ETH/USDT": {{
      "risk_result": {{
        "agent_name": "AXIS-Risk",
        "risk_score": 32.1,
        "risk_level": "LOW",
        "normalized_risk_score": -0.36,
        "evidence": {{
          "analysis_period": "90 days",
          "vix_index": 18.2,
          "correlation_btc_ndx": 0.72,
          "confidence": 0.75
        }}
      }}
    }}
  }},
  "summary": {{
    "total_coins": {len(coins_summary)},
    "low_risk_coins": 0,
    "medium_risk_coins": 0,
    "high_risk_coins": 0,
    "critical_risk_coins": 0,
    "average_risk_score": 0.0
  }}
}}
"""
        return prompt

    def _get_multi_coin_risk_system_message(self) -> str:
        """다중 코인 리스크 분석용 시스템 메시지"""
        return """You are a JSON-only data generation AI specialized in multi-coin cryptocurrency risk analysis. Your ONLY purpose is to analyze multiple coins and respond with a valid JSON object.

CRITICAL RULES:
- Your response MUST be ONLY the valid JSON object.
- Your response MUST start with { and end with }.
- DO NOT include ANY text, explanations, apologies, or markdown formatting.
- Analyze ALL provided coins in a single response.
- Adhere strictly to the JSON format. Use double quotes for all keys and string values."""

    def _create_fallback_multi_risk_analysis(self, coins_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """AI 리스크 분석 실패시 기본 분석 결과 (다중 코인용)"""
        analysis_results = {}

        for coin_data in coins_data:
            market = coin_data.get('market', 'Unknown')
            risk_score = coin_data.get('risk_score', 50)
            risk_level = self._determine_risk_level(risk_score)

            analysis_results[market] = {
                "risk_result": {
                    "agent_name": "AXIS-Risk-Fallback",
                    "risk_score": risk_score,
                    "risk_level": risk_level,
                    "normalized_risk_score": (risk_score - 50) / 50,  # -1 to +1
                    "evidence": {
                        "analysis_period": f"{coin_data.get('days_back', 90)} days",
                        "confidence": coin_data.get('confidence', 0.5)
                    }
                }
            }

        return {
            "analysis_results": analysis_results,
            "summary": {
                "total_coins": len(coins_data),
                "low_risk_coins": sum(1 for coin in coins_data if self._determine_risk_level(coin.get('risk_score', 50)) == "LOW"),
                "medium_risk_coins": sum(1 for coin in coins_data if self._determine_risk_level(coin.get('risk_score', 50)) == "MEDIUM"),
                "high_risk_coins": sum(1 for coin in coins_data if self._determine_risk_level(coin.get('risk_score', 50)) == "HIGH"),
                "critical_risk_coins": sum(1 for coin in coins_data if self._determine_risk_level(coin.get('risk_score', 50)) == "CRITICAL"),
                "average_risk_score": sum(coin.get('risk_score', 50) for coin in coins_data) / len(coins_data)
            }
        }

    def _determine_risk_level(self, risk_score: float) -> str:
        """리스크 점수에 따른 리스크 레벨 결정"""
        if risk_score >= 80:
            return "CRITICAL"
        elif risk_score >= 60:
            return "HIGH"
        elif risk_score >= 40:
            return "MEDIUM"
        else:
            return "LOW"

    async def analyze_multiple_coins_social_with_ai(self, coins_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        여러 코인을 한 번에 AI로 소셜 분석 (비용 효율적)
        """
        try:
            prompt = self._create_multi_coin_social_analysis_prompt(coins_data)
            messages = [
                SystemMessage(content=self._get_multi_coin_social_system_message()),
                HumanMessage(content=prompt)
            ]
            response = await self.llm.ainvoke(messages)
            result = self._parse_ai_response(response.content)
            logger.info(f"✅ AI 다중 코인 소셜 분석 완료: {len(coins_data)}개 코인")
            return result
        except Exception as e:
            logger.error(f"❌ AI 다중 코인 소셜 분석 실패: {str(e)}")
            return self._create_fallback_multi_social_analysis(coins_data)

    def _create_multi_coin_social_analysis_prompt(self, coins_data: List[Dict[str, Any]]) -> str:
        """다중 코인 AI 소셜 분석 프롬프트 생성"""
        coins_summary = []
        for coin_data in coins_data:
            coin_summary = {
                "market": coin_data.get('market', 'Unknown'),
                "social_score": coin_data.get('social_score', 50),
                "sentiment": coin_data.get('sentiment', 'neutral'),
                "social_sources": coin_data.get('social_sources', {}),
                "analysis_timestamp": coin_data.get('analysis_timestamp', '')
            }
            coins_summary.append(coin_summary)

        prompt = f"""
Mission: Analyze multiple cryptocurrency social sentiment profiles and generate structured, purely analytical JSON reports for each coin. Your role is to provide objective social sentiment scores based on data, not trading recommendations.

Coins Data ({len(coins_summary)} coins):
{json.dumps(coins_summary, indent=2)}

Analysis Instructions:
1. For each coin, determine the social sentiment level based on social_score and other indicators
2. Provide evidence including social metrics and community engagement
3. Calculate confidence based on data quality and consistency
4. Consider the sentiment trends and social buzz

CRITICAL RULES:
1. Your response MUST be ONLY the valid JSON object.
2. Do NOT include trading recommendations.
3. Each coin's sentiment_level field MUST be one of: "VERY_POSITIVE", "POSITIVE", "NEUTRAL", "NEGATIVE", "VERY_NEGATIVE".
4. social_score should be between 0 and 100 for each coin.
5. Analyze all {len(coins_summary)} coins in a single response.

Output Format:
{{
  "analysis_results": {{
    "BTC/USDT": {{
      "social_result": {{
        "agent_name": "AXIS-Social",
        "social_score": 75.5,
        "sentiment_level": "POSITIVE",
        "normalized_social_score": 0.51,
        "evidence": {{
          "reddit_mentions": 150,
          "reddit_sentiment": 0.6,
          "cryptocompare_volume": 1000,
          "perplexity_buzz": "high",
          "confidence": 0.8
        }}
      }}
    }},
    "ETH/USDT": {{
      "social_result": {{
        "agent_name": "AXIS-Social",
        "social_score": 65.2,
        "sentiment_level": "POSITIVE",
        "normalized_social_score": 0.30,
        "evidence": {{
          "reddit_mentions": 120,
          "reddit_sentiment": 0.55,
          "cryptocompare_volume": 800,
          "perplexity_buzz": "medium",
          "confidence": 0.75
        }}
      }}
    }}
  }},
  "summary": {{
    "total_coins": {len(coins_summary)},
    "very_positive_coins": 0,
    "positive_coins": 0,
    "neutral_coins": 0,
    "negative_coins": 0,
    "very_negative_coins": 0,
    "average_social_score": 0.0
  }}
}}
"""
        return prompt

    def _get_multi_coin_social_system_message(self) -> str:
        """다중 코인 소셜 분석용 시스템 메시지"""
        return """You are a JSON-only data generation AI specialized in multi-coin cryptocurrency social sentiment analysis. Your ONLY purpose is to analyze multiple coins and respond with a valid JSON object.

CRITICAL RULES:
- Your response MUST be ONLY the valid JSON object.
- Your response MUST start with { and end with }.
- DO NOT include ANY text, explanations, apologies, or markdown formatting.
- Analyze ALL provided coins in a single response.
- Adhere strictly to the JSON format. Use double quotes for all keys and string values."""

    def _create_fallback_multi_social_analysis(self, coins_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """AI 소셜 분석 실패시 기본 분석 결과 (다중 코인용)"""
        analysis_results = {}

        for coin_data in coins_data:
            market = coin_data.get('market', 'Unknown')
            social_score = coin_data.get('social_score', 50)
            sentiment_level = self._determine_sentiment_level(social_score)

            analysis_results[market] = {
                "social_result": {
                    "agent_name": "AXIS-Social-Fallback",
                    "social_score": social_score,
                    "sentiment_level": sentiment_level,
                    "normalized_social_score": (social_score - 50) / 50,  # -1 to +1
                    "evidence": {
                        "analysis_timestamp": coin_data.get('analysis_timestamp', ''),
                        "confidence": 0.5
                    }
                }
            }

        return {
            "analysis_results": analysis_results,
            "summary": {
                "total_coins": len(coins_data),
                "very_positive_coins": sum(1 for coin in coins_data if self._determine_sentiment_level(coin.get('social_score', 50)) == "VERY_POSITIVE"),
                "positive_coins": sum(1 for coin in coins_data if self._determine_sentiment_level(coin.get('social_score', 50)) == "POSITIVE"),
                "neutral_coins": sum(1 for coin in coins_data if self._determine_sentiment_level(coin.get('social_score', 50)) == "NEUTRAL"),
                "negative_coins": sum(1 for coin in coins_data if self._determine_sentiment_level(coin.get('social_score', 50)) == "NEGATIVE"),
                "very_negative_coins": sum(1 for coin in coins_data if self._determine_sentiment_level(coin.get('social_score', 50)) == "VERY_NEGATIVE"),
                "average_social_score": sum(coin.get('social_score', 50) for coin in coins_data) / len(coins_data)
            }
        }

    def _determine_sentiment_level(self, social_score: float) -> str:
        """소셜 점수에 따른 감정 레벨 결정"""
        if social_score >= 80:
            return "VERY_POSITIVE"
        elif social_score >= 60:
            return "POSITIVE"
        elif social_score >= 40:
            return "NEUTRAL"
        elif social_score >= 20:
            return "NEGATIVE"
        else:
            return "VERY_NEGATIVE"

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
