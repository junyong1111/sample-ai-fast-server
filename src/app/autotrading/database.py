"""
MongoDB 데이터베이스 서비스
거래 신호 저장 및 조회 기능 제공
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError, OperationFailure

from .model import TradingSignal, TradingSignalCreate, TradingSignalQuery, TradingSignalStats, TradingExecution, TradingExecutionCreate, TradingExecutionQuery, TradingExecutionStats


class MongoDBService:
    """MongoDB 비동기 서비스"""

    def __init__(self, connection_string: str = "mongodb://localhost:27017", database_name: str = "autotrading"):
        """
        MongoDB 서비스 초기화

        Args:
            connection_string: MongoDB 연결 문자열
            database_name: 데이터베이스 이름
        """
        self.client: AsyncIOMotorClient = None
        self.db: AsyncIOMotorDatabase = None
        self.connection_string = connection_string
        self.database_name = database_name

    async def connect(self):
        """MongoDB에 연결"""
        try:
            self.client = AsyncIOMotorClient(self.connection_string)
            self.db = self.client[self.database_name]

            # 연결 테스트
            await self.client.admin.command('ping')
            print(f"✅ MongoDB 연결 성공: {self.database_name}")

            # 인덱스 생성
            await self._create_indexes()

        except Exception as e:
            print(f"❌ MongoDB 연결 실패: {e}")
            raise

    async def disconnect(self):
        """MongoDB 연결 해제"""
        if self.client:
            self.client.close()
            print("🔌 MongoDB 연결 해제")

    async def _create_indexes(self):
        """필요한 인덱스 생성"""
        try:
            # 거래 신호 컬렉션
            signals_collection = self.db.trading_signals

            # 복합 인덱스 생성
            await signals_collection.create_index([
                ("exchange", ASCENDING),
                ("market", ASCENDING),
                ("timestamp", DESCENDING)
            ])

            # 시간 기반 인덱스
            await signals_collection.create_index([("timestamp", DESCENDING)])

            # 거래소별 인덱스
            await signals_collection.create_index([("exchange", ASCENDING)])

            # 시장별 인덱스
            await signals_collection.create_index([("market", ASCENDING)])

            # 신호별 인덱스
            await signals_collection.create_index([("overall_signal", ASCENDING)])

            print("✅ MongoDB 인덱스 생성 완료")

        except Exception as e:
            print(f"⚠️ 인덱스 생성 실패: {e}")

    # ===== 거래 실행 결과 저장 =====
    async def save_trading_execution(self, execution_data: TradingExecutionCreate) -> str:
        """
        거래 실행 결과를 MongoDB에 저장

        Args:
            execution_data: 저장할 거래 실행 결과 데이터

        Returns:
            저장된 문서의 ObjectId
        """
        try:
            collection = self.db.trading_executions

            # 현재 시간 추가
            execution_doc = execution_data.dict()
            execution_doc["timestamp"] = datetime.utcnow()
            execution_doc["created_at"] = datetime.utcnow()

            # MongoDB에 저장
            result = await collection.insert_one(execution_doc)

            print(f"✅ 거래 실행 결과 저장 완료: {result.inserted_id}")
            return str(result.inserted_id)

        except Exception as e:
            print(f"❌ 거래 실행 결과 저장 실패: {e}")
            raise

    async def save_trading_execution_with_result(
        self,
        exchange: str,
        market: str,
        testnet: bool,
        ai_signal: Dict[str, Any],
        action: str,
        quantity: float,
        order_type: str,
        price: Optional[float] = None,
        order_result: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        거래 실행 결과와 함께 저장

        Args:
            exchange: 거래소
            market: 시장
            testnet: 테스트넷 사용 여부
            ai_signal: AI가 보낸 거래 신호
            action: 거래 방향
            quantity: 거래 수량
            order_type: 주문 타입
            price: 거래 가격
            order_result: 주문 실행 결과

        Returns:
            저장된 문서의 ObjectId
        """
        try:
            # AI 신호에서 정보 추출
            signal_confidence = ai_signal.get('confidence')
            signal_reason = ai_signal.get('reason')

            # 주문 결과에서 정보 추출
            order_id = order_result.get('id') if order_result else None
            order_status = order_result.get('status') if order_result else None
            execution_price = order_result.get('price') if order_result else None

            # 저장할 데이터 구성
            execution_doc = {
                "exchange": exchange,
                "market": market,
                "testnet": testnet,
                "ai_signal": ai_signal,
                "signal_confidence": signal_confidence,
                "signal_reason": signal_reason,
                "action": action,
                "quantity": quantity,
                "order_type": order_type,
                "price": price,
                "order_id": order_id,
                "order_status": order_status,
                "execution_price": execution_price,
                "execution_time": datetime.utcnow() if order_result else None,
                "timestamp": datetime.utcnow(),
                "executed_at": datetime.utcnow() if order_result else None,
                "created_at": datetime.utcnow(),
                "metadata": {
                    "order_result": order_result,
                    "source": "trading_service"
                }
            }

            # MongoDB에 저장
            collection = self.db.trading_executions
            result = await collection.insert_one(execution_doc)

            print(f"✅ 거래 실행 결과 상세 저장 완료: {result.inserted_id}")
            return str(result.inserted_id)

        except Exception as e:
            print(f"❌ 거래 실행 결과 상세 저장 실패: {e}")
            raise

    # ===== 거래 실행 결과 조회 =====
    async def get_trading_executions(
        self,
        query: TradingExecutionQuery
    ) -> List[TradingExecution]:
        """
        조건에 맞는 거래 실행 결과 조회

        Args:
            query: 조회 조건

        Returns:
            거래 실행 결과 리스트
        """
        try:
            collection = self.db.trading_executions

            # 쿼리 조건 구성
            filter_conditions = {}

            if query.exchange:
                filter_conditions["exchange"] = query.exchange

            if query.market:
                filter_conditions["market"] = query.market

            if query.testnet is not None:
                filter_conditions["testnet"] = query.testnet

            if query.action:
                filter_conditions["action"] = query.action

            if query.order_type:
                filter_conditions["order_type"] = query.order_type

            # 날짜 범위 조건
            if query.start_date or query.end_date:
                date_filter = {}
                if query.start_date:
                    date_filter["$gte"] = query.start_date
                if query.end_date:
                    date_filter["$lte"] = query.end_date
                filter_conditions["timestamp"] = date_filter

            # MongoDB에서 조회
            cursor = collection.find(filter_conditions).sort("timestamp", DESCENDING)

            if query.skip > 0:
                cursor = cursor.skip(query.skip)

            if query.limit > 0:
                cursor = cursor.limit(query.limit)

            # 결과 변환
            executions = []
            async for doc in cursor:
                # ObjectId를 문자열로 변환
                doc["_id"] = str(doc["_id"])
                executions.append(TradingExecution(**doc))

            print(f"✅ 거래 실행 결과 조회 완료: {len(executions)}개")
            return executions

        except Exception as e:
            print(f"❌ 거래 실행 결과 조회 실패: {e}")
            raise

    async def get_latest_trading_execution(
        self,
        exchange: str,
        market: str,
        testnet: Optional[bool] = None
    ) -> Optional[TradingExecution]:
        """최신 거래 실행 결과 조회"""
        try:
            collection = self.db.trading_executions

            filter_conditions = {
                "exchange": exchange,
                "market": market
            }

            if testnet is not None:
                filter_conditions["testnet"] = testnet

            doc = await collection.find_one(
                filter_conditions,
                sort=[("timestamp", DESCENDING)]
            )

            if doc:
                doc["_id"] = str(doc["_id"])
                return TradingExecution(**doc)

            return None

        except Exception as e:
            print(f"❌ 최신 거래 실행 결과 조회 실패: {e}")
            return None

    # ===== 통합 조회 =====
    async def get_trading_data_integrated(
        self,
        exchange: str,
        market: str,
        testnet: bool = True,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        거래 신호와 거래 실행 결과를 통합하여 조회

        Args:
            exchange: 거래소
            market: 시장
            testnet: 테스트넷 사용 여부
            limit: 조회 개수 제한

        Returns:
            통합된 거래 데이터
        """
        try:
            # 거래 신호 조회
            signals_query = TradingSignalQuery(
                exchange=exchange,
                market=market,
                limit=limit,
                timeframe=None,
                signal=None,
                start_date=None,
                end_date=None,
                skip=0
            )
            signals = await self.get_trading_signals(signals_query)

            # 거래 실행 결과 조회
            executions_query = TradingExecutionQuery(
                exchange=exchange,
                market=market,
                testnet=testnet,
                limit=limit,
                action=None,
                order_type=None,
                start_date=None,
                end_date=None,
                skip=0
            )
            executions = await self.get_trading_executions(executions_query)

            # 통합 데이터 구성
            integrated_data = {
                "exchange": exchange,
                "market": market,
                "testnet": testnet,
                "signals_count": len(signals),
                "executions_count": len(executions),
                "latest_signal": signals[0].dict() if signals else None,
                "latest_execution": executions[0].dict() if executions else None,
                "recent_signals": [signal.dict() for signal in signals[:10]],
                "recent_executions": [execution.dict() for execution in executions[:10]],
                "timestamp": datetime.utcnow().isoformat()
            }

            print(f"✅ 통합 거래 데이터 조회 완료")
            return integrated_data

        except Exception as e:
            print(f"❌ 통합 거래 데이터 조회 실패: {e}")
            raise

    # ===== 거래 신호 저장 =====
    async def save_trading_signal(self, signal_data: TradingSignalCreate) -> str:
        """
        거래 신호를 MongoDB에 저장

        Args:
            signal_data: 저장할 거래 신호 데이터

        Returns:
            저장된 문서의 ObjectId
        """
        try:
            collection = self.db.trading_signals

            # 현재 시간 추가
            signal_doc = signal_data.dict()
            signal_doc["created_at"] = datetime.utcnow()

            # MongoDB에 저장
            result = await collection.insert_one(signal_doc)

            print(f"✅ 거래 신호 저장 완료: {result.inserted_id}")
            return str(result.inserted_id)

        except Exception as e:
            print(f"❌ 거래 신호 저장 실패: {e}")
            raise

    async def save_trading_signal_with_details(
        self,
        exchange: str,
        market: str,
        timeframe: str,
        current_price: float,
        overall_signal: str,
        indicators: Dict[str, Any],
        rule_evaluation: Dict[str, Any],
        parameters: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        상세 정보와 함께 거래 신호 저장 (에이전트용)

        Args:
            exchange: 거래소
            market: 시장
            timeframe: 시간프레임
            current_price: 현재 가격
            overall_signal: 종합 신호
            indicators: 모든 기술적 지표
            rule_evaluation: 규칙 평가 결과
            parameters: 사용된 파라미터
            metadata: 추가 메타데이터

        Returns:
            저장된 문서의 ObjectId
        """
        try:
            # RSI 정보 추출
            rsi = indicators.get("rsi")
            rsi_period = parameters.get("rsi_period", 14)

            # MACD 정보 추출
            macd_cross = indicators.get("macd_cross")

            # 볼린저 밴드 정보 추출
            bollinger_bands = None
            if "bb_upper" in indicators and "bb_lower" in indicators:
                bollinger_bands = {
                    "upper": indicators.get("bb_upper"),
                    "lower": indicators.get("bb_lower"),
                    "middle": indicators.get("bb_middle"),
                    "pct_b": indicators.get("bb_pct_b")
                }

            # 신호 강도 계산
            signal_strength = self._calculate_signal_strength(indicators, rule_evaluation)

            # 개별 규칙 신호 추출
            rule_signals = {}
            for key, value in rule_evaluation.items():
                if key.startswith("rule") and key != "overall":
                    rule_signals[key] = value

            # 저장할 데이터 구성
            signal_doc = {
                "exchange": exchange,
                "market": market,
                "timeframe": timeframe,
                "timestamp": datetime.utcnow(),
                "current_price": current_price,
                "overall_signal": overall_signal,
                "rsi": rsi,
                "rsi_period": rsi_period,
                "macd_cross": macd_cross,
                "bollinger_bands": bollinger_bands,
                "signal_strength": signal_strength,
                "rule_signals": rule_signals,
                "parameters": parameters,
                "metadata": metadata or {},
                "created_at": datetime.utcnow()
            }

            # MongoDB에 저장
            collection = self.db.trading_signals
            result = await collection.insert_one(signal_doc)

            print(f"✅ 상세 거래 신호 저장 완료: {result.inserted_id}")
            return str(result.inserted_id)

        except Exception as e:
            print(f"❌ 상세 거래 신호 저장 실패: {e}")
            raise

    def _calculate_signal_strength(self, indicators: Dict[str, Any], rule_evaluation: Dict[str, Any]) -> float:
        """신호 강도 계산 (0-100)"""
        try:
            # RSI 기반 강도
            rsi_strength = 0
            if "rsi" in indicators:
                rsi = indicators["rsi"]
                if rsi <= 20 or rsi >= 80:
                    rsi_strength = 100
                elif rsi <= 30 or rsi >= 70:
                    rsi_strength = 80
                elif rsi <= 40 or rsi >= 60:
                    rsi_strength = 60
                else:
                    rsi_strength = 40

            # 볼린저 밴드 기반 강도
            bb_strength = 0
            if "bb_pct_b" in indicators:
                bb_pct_b = indicators["bb_pct_b"]
                if bb_pct_b <= 0.1 or bb_pct_b >= 0.9:
                    bb_strength = 100
                elif bb_pct_b <= 0.2 or bb_pct_b >= 0.8:
                    bb_strength = 80
                elif bb_pct_b <= 0.3 or bb_pct_b >= 0.7:
                    bb_strength = 60
                else:
                    bb_strength = 40

            # MACD 기반 강도
            macd_strength = 0
            if "macd_cross" in indicators:
                macd_cross = indicators["macd_cross"]
                if macd_cross in ["bullish", "bearish"]:
                    macd_strength = 80
                else:
                    macd_strength = 40

            # 종합 강도 계산
            total_strength = (rsi_strength + bb_strength + macd_strength) / 3
            return round(total_strength, 2)

        except Exception:
            return 50.0  # 기본값

    # ===== 거래 신호 조회 =====
    async def get_trading_signals(
        self,
        query: TradingSignalQuery
    ) -> List[TradingSignal]:
        """
        조건에 맞는 거래 신호 조회

        Args:
            query: 조회 조건

        Returns:
            거래 신호 리스트
        """
        try:
            collection = self.db.trading_signals

            # 쿼리 조건 구성
            filter_conditions = {}

            if query.exchange:
                filter_conditions["exchange"] = query.exchange

            if query.market:
                filter_conditions["market"] = query.market

            if query.timeframe:
                filter_conditions["timeframe"] = query.timeframe

            if query.signal:
                filter_conditions["overall_signal"] = query.signal

            # 날짜 범위 조건
            if query.start_date or query.end_date:
                date_filter = {}
                if query.start_date:
                    date_filter["$gte"] = query.start_date
                if query.end_date:
                    date_filter["$lte"] = query.end_date
                filter_conditions["timestamp"] = date_filter

            # MongoDB에서 조회
            cursor = collection.find(filter_conditions).sort("timestamp", DESCENDING)

            if query.skip > 0:
                cursor = cursor.skip(query.skip)

            if query.limit > 0:
                cursor = cursor.limit(query.limit)

            # 결과 변환
            signals = []
            async for doc in cursor:
                # ObjectId를 문자열로 변환
                doc["_id"] = str(doc["_id"])
                signals.append(TradingSignal(**doc))

            print(f"✅ 거래 신호 조회 완료: {len(signals)}개")
            return signals

        except Exception as e:
            print(f"❌ 거래 신호 조회 실패: {e}")
            raise

    async def get_trading_signal_by_id(self, signal_id: str) -> Optional[TradingSignal]:
        """ID로 특정 거래 신호 조회"""
        try:
            from bson import ObjectId

            collection = self.db.trading_signals
            doc = await collection.find_one({"_id": ObjectId(signal_id)})

            if doc:
                doc["_id"] = str(doc["_id"])
                return TradingSignal(**doc)

            return None

        except Exception as e:
            print(f"❌ 거래 신호 ID 조회 실패: {e}")
            return None

    async def get_latest_trading_signal(
        self,
        exchange: str,
        market: str,
        timeframe: Optional[str] = None
    ) -> Optional[TradingSignal]:
        """최신 거래 신호 조회"""
        try:
            collection = self.db.trading_signals

            filter_conditions = {
                "exchange": exchange,
                "market": market
            }

            if timeframe:
                filter_conditions["timeframe"] = timeframe

            doc = await collection.find_one(
                filter_conditions,
                sort=[("timestamp", DESCENDING)]
            )

            if doc:
                doc["_id"] = str(doc["_id"])
                return TradingSignal(**doc)

            return None

        except Exception as e:
            print(f"❌ 최신 거래 신호 조회 실패: {e}")
            return None

    # ===== 통계 정보 =====
    async def get_trading_signal_stats(
        self,
        exchange: Optional[str] = None,
        market: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> TradingSignalStats:
        """거래 신호 통계 정보 조회"""
        try:
            collection = self.db.trading_signals

            # 기본 필터 조건
            filter_conditions = {}

            if exchange:
                filter_conditions["exchange"] = exchange

            if market:
                filter_conditions["market"] = market

            if start_date or end_date:
                date_filter = {}
                if start_date:
                    date_filter["$gte"] = start_date
                if end_date:
                    date_filter["$lte"] = end_date
                filter_conditions["timestamp"] = date_filter

            # 총 신호 개수
            total_signals = await collection.count_documents(filter_conditions)

            # 신호별 분포
            signal_pipeline = [
                {"$match": filter_conditions},
                {"$group": {"_id": "$overall_signal", "count": {"$sum": 1}}}
            ]
            signal_distribution = {}
            async for doc in collection.aggregate(signal_pipeline):
                signal_distribution[doc["_id"]] = doc["count"]

            # 거래소별 분포
            exchange_pipeline = [
                {"$match": filter_conditions},
                {"$group": {"_id": "$exchange", "count": {"$sum": 1}}}
            ]
            exchange_distribution = {}
            async for doc in collection.aggregate(exchange_pipeline):
                exchange_distribution[doc["_id"]] = doc["count"]

            # 시장별 분포
            market_pipeline = [
                {"$match": filter_conditions},
                {"$group": {"_id": "$market", "count": {"$sum": 1}}}
            ]
            market_distribution = {}
            async for doc in collection.aggregate(market_pipeline):
                market_distribution[doc["_id"]] = doc["count"]

            # 시간프레임별 분포
            timeframe_pipeline = [
                {"$match": filter_conditions},
                {"$group": {"_id": "$timeframe", "count": {"$sum": 1}}}
            ]
            timeframe_distribution = {}
            async for doc in collection.aggregate(timeframe_pipeline):
                timeframe_distribution[doc["_id"]] = doc["count"]

            # 평균 신호 강도
            strength_pipeline = [
                {"$match": filter_conditions},
                {"$group": {"_id": None, "avg_strength": {"$avg": "$signal_strength"}}}
            ]
            avg_signal_strength = None
            async for doc in collection.aggregate(strength_pipeline):
                avg_signal_strength = round(doc["avg_strength"], 2)

            stats = TradingSignalStats(
                total_signals=total_signals,
                signal_distribution=signal_distribution,
                exchange_distribution=exchange_distribution,
                market_distribution=market_distribution,
                timeframe_distribution=timeframe_distribution,
                avg_signal_strength=avg_signal_strength,
                success_rate=None,
                hourly_distribution=None,
                daily_distribution=None
            )

            print(f"✅ 거래 신호 통계 조회 완료")
            return stats

        except Exception as e:
            print(f"❌ 거래 신호 통계 조회 실패: {e}")
            raise

    # ===== 데이터 정리 =====
    async def cleanup_old_signals(self, days_to_keep: int = 90):
        """오래된 거래 신호 정리"""
        try:
            collection = self.db.trading_signals

            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

            result = await collection.delete_many({
                "timestamp": {"$lt": cutoff_date}
            })

            print(f"✅ 오래된 거래 신호 정리 완료: {result.deleted_count}개 삭제")
            return result.deleted_count

        except Exception as e:
            print(f"❌ 오래된 거래 신호 정리 실패: {e}")
            raise


# 전역 MongoDB 서비스 인스턴스
mongodb_service = MongoDBService()


async def get_mongodb_service() -> MongoDBService:
    """MongoDB 서비스 인스턴스 반환"""
    if not mongodb_service.client:
        await mongodb_service.connect()
    return mongodb_service
