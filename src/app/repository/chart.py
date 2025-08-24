from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import logging

from src.common.conf.mongodb import MongoDBConfig

logger = logging.getLogger(__name__)

# KST 시간대 설정 (UTC+9)
KST = timezone(timedelta(hours=9))

def get_kst_now() -> datetime:
    """현재 KST 시간 반환"""
    return datetime.now(KST)

def get_kst_datetime(dt: datetime) -> datetime:
    """datetime을 KST로 변환"""
    if dt.tzinfo is None:
        # naive datetime을 UTC로 가정하고 KST로 변환
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST)

def parse_kst_timestamp(timestamp_str: str) -> datetime:
    """문자열을 KST datetime으로 파싱"""
    try:
        # ISO 형식 문자열 파싱
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return get_kst_datetime(dt)
    except ValueError:
        # 다른 형식 시도
        try:
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            return dt.replace(tzinfo=KST)
        except ValueError:
            logger.warning(f"타임스탬프 파싱 실패: {timestamp_str}, 현재 KST 시간 사용")
            return get_kst_now()

class ChartRepository:
    def __init__(self, mongo_uri: str = "mongodb://localhost:27017", db_name: str = "trading_ai"):
        """
        MongoDB 연결 및 초기화

        Args:
            mongo_uri: MongoDB 연결 URI
            db_name: 데이터베이스 이름
        """
        try:
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            # 연결 테스트
            self.client.admin.command('ping')
            logger.info(f"MongoDB 연결 성공: {mongo_uri}")

            self.db = self.client[db_name]
            self.charts = self.db.charts
            self.history = self.db.indicator_history
            self.ai_analysis = self.db.ai_analysis
            self.market_stats = self.db.market_stats

            # 인덱스 생성
            self._create_indexes()
            logger.info("MongoDB 인덱스 생성 완료")

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"MongoDB 연결 실패: {e}")
            raise ConnectionError(f"MongoDB 연결할 수 없습니다: {e}")

    def _create_indexes(self):
        """성능 최적화를 위한 인덱스 생성"""
        try:
            # 차트 데이터: 마켓 + 시간 기반 조회
            self.charts.create_index([
                ("market", 1),
                ("timestamp", -1)
            ])

            # 차트 데이터: 마켓 + 타임프레임 + 시간
            self.charts.create_index([
                ("market", 1),
                ("timeframe", 1),
                ("timestamp", -1)
            ])

            # TTL 인덱스: 90일 후 자동 삭제 (선택사항)
            self.charts.create_index("created_at", expireAfterSeconds=90*24*60*60)

            # 히스토리: 마켓 + 날짜
            self.history.create_index([
                ("market", 1),
                ("date", -1)
            ])

            # AI 분석: 마켓 + 시간
            self.ai_analysis.create_index([
                ("market", 1),
                ("timestamp", -1)
            ])

            # 시장 통계: 마켓 + 날짜
            self.market_stats.create_index([
                ("market", 1),
                ("date", -1)
            ])

            logger.info("MongoDB 인덱스 생성 완료")

        except Exception as e:
            logger.error(f"인덱스 생성 실패: {e}")
            raise

    async def save_chart_data(
        self,
        market: str,
        timeframe: str,
        indicators: Dict[str, Any],
        signals: Dict[str, Any],
        candle_data: Dict[str, Any]
    ) -> str:
        """
        실시간 차트 데이터 저장

        Args:
            market: 마켓 코드 (예: KRW-BTC)
            timeframe: 시간프레임 (예: minutes:60)
            indicators: 계산된 지표들
            signals: 신호 평가 결과
            candle_data: 캔들 데이터

        Returns:
            저장된 문서의 ID
        """
        try:
            # timestamp 처리 - KST로 변환
            timestamp = indicators.get("time")
            if isinstance(timestamp, str):
                timestamp = parse_kst_timestamp(timestamp)
            elif timestamp is None:
                timestamp = get_kst_now()
            else:
                timestamp = get_kst_datetime(timestamp)

            # 현재 KST 시간
            kst_now = get_kst_now()

            document = {
                "market": market,
                "timeframe": timeframe,
                "timestamp": timestamp,
                "candle": candle_data,
                "indicators": indicators,
                "signals": signals,
                "created_at": kst_now
            }

            # 중복 데이터 체크 (같은 마켓, 타임프레임, 시간)
            existing = self.charts.find_one({
                "market": market,
                "timeframe": timeframe,
                "timestamp": timestamp
            })

            if existing:
                # 기존 데이터 업데이트
                result = self.charts.update_one(
                    {"_id": existing["_id"]},
                    {"$set": document}
                )
                logger.info(f"차트 데이터 업데이트: {market} {timeframe} {timestamp}")
                return str(existing["_id"])
            else:
                # 새 데이터 삽입
                result = self.charts.insert_one(document)
                logger.info(f"차트 데이터 저장: {market} {timeframe} {timestamp}")
                return str(result.inserted_id)

        except Exception as e:
            logger.error(f"차트 데이터 저장 실패: {e}")
            raise

    async def debug_save_and_retrieve(
        self,
        market: str,
        timeframe: str,
        indicators: Dict[str, Any],
        signals: Dict[str, Any],
        candle_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        디버깅용: 저장 후 즉시 조회 테스트
        """
        try:
            # 1. 저장 전 데이터 개수 확인
            before_count = self.charts.count_documents({})
            logger.info(f"저장 전 전체 데이터 개수: {before_count}")

            # 2. 데이터 저장
            db_id = await self.save_chart_data(market, timeframe, indicators, signals, candle_data)
            logger.info(f"데이터 저장 완료, DB ID: {db_id}")

            # 3. 저장 후 데이터 개수 확인
            after_count = self.charts.count_documents({})
            logger.info(f"저장 후 전체 데이터 개수: {after_count}")

            # 4. 저장된 데이터 직접 조회
            saved_data = self.charts.find_one({"_id": db_id})
            logger.info(f"저장된 데이터 조회: {saved_data is not None}")

            if saved_data:
                logger.info(f"저장된 데이터 구조:")
                logger.info(f"  - market: {saved_data.get('market')}")
                logger.info(f"  - timeframe: {saved_data.get('timeframe')}")
                logger.info(f"  - timestamp: {saved_data.get('timestamp')}")
                logger.info(f"  - created_at: {saved_data.get('created_at')}")

            # 5. 동일한 조건으로 데이터 조회
            query = {
                "market": market,
                "timeframe": timeframe
            }

            # timestamp 범위로 조회 (최근 1시간)
            end_time = get_kst_now()
            start_time = end_time - timedelta(hours=1)

            query["timestamp"] = {
                "$gte": start_time,
                "$lte": end_time
            }

            recent_data = list(self.charts.find(query).sort("timestamp", -1).limit(5))
            logger.info(f"최근 1시간 데이터 조회 결과: {len(recent_data)}개")

            for i, data in enumerate(recent_data):
                logger.info(f"  데이터 {i+1}: {data.get('timestamp')} - {data.get('indicators', {}).get('close')}")

            return {
                "success": True,
                "db_id": db_id,
                "before_count": before_count,
                "after_count": after_count,
                "data_increased": after_count > before_count,
                "saved_data_exists": saved_data is not None,
                "recent_data_count": len(recent_data),
                "query_used": str(query)
            }

        except Exception as e:
            logger.error(f"디버깅 저장/조회 실패: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_raw_data_sample(
        self,
        market: str = None,
        timeframe: str = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        디버깅용: 원시 데이터 샘플 조회
        """
        try:
            query = {}
            if market:
                query["market"] = market
            if timeframe:
                query["timeframe"] = timeframe

            cursor = self.charts.find(query).sort("timestamp", -1).limit(limit)
            data = list(cursor)

            logger.info(f"원시 데이터 샘플 조회: {len(data)}개")
            for i, item in enumerate(data):
                logger.info(f"  샘플 {i+1}:")
                logger.info(f"    _id: {item.get('_id')}")
                logger.info(f"    market: {item.get('market')}")
                logger.info(f"    timeframe: {item.get('timeframe')}")
                logger.info(f"    timestamp: {item.get('timestamp')}")
                logger.info(f"    created_at: {item.get('created_at')}")
                logger.info(f"    indicators keys: {list(item.get('indicators', {}).keys())}")
                logger.info(f"    signals keys: {list(item.get('signals', {}).keys())}")

            return data

        except Exception as e:
            logger.error(f"원시 데이터 샘플 조회 실패: {e}")
            return []

    async def get_chart_history(
        self,
        market: str,
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        특정 기간 차트 데이터 조회

        Args:
            market: 마켓 코드
            timeframe: 시간프레임
            start_time: 시작 시간
            end_time: 종료 시간
            limit: 최대 조회 개수

        Returns:
            차트 데이터 리스트
        """
        try:
            logger.info(f"히스토리 조회 시작: {market} {timeframe}")
            logger.info(f"조회 기간: {start_time} ~ {end_time}")

            # 1. 먼저 전체 데이터 개수 확인
            total_count = self.charts.count_documents({})
            market_count = self.charts.count_documents({"market": market})
            timeframe_count = self.charts.count_documents({"timeframe": timeframe})

            logger.info(f"전체 데이터: {total_count}개, 마켓별: {market_count}개, 타임프레임별: {timeframe_count}개")

            # 2. 단순 조건으로 먼저 조회해보기
            simple_query = {"market": market}
            simple_count = self.charts.count_documents(simple_query)
            logger.info(f"마켓만으로 조회: {simple_count}개")

            if simple_count == 0:
                logger.warning(f"마켓 {market}에 대한 데이터가 없습니다")
                return []

            # 3. 타임프레임 조건 추가
            timeframe_query = {"market": market, "timeframe": timeframe}
            tf_count = self.charts.count_documents(timeframe_query)
            logger.info(f"마켓+타임프레임으로 조회: {tf_count}개")

            if tf_count == 0:
                logger.warning(f"타임프레임 {timeframe}에 대한 데이터가 없습니다")
                # 다른 타임프레임이 있는지 확인
                other_timeframes = self.charts.distinct("timeframe", {"market": market})
                logger.info(f"사용 가능한 타임프레임: {other_timeframes}")
                return []

            # 4. 시간 범위 조건 추가
            time_query = {
                "market": market,
                "timeframe": timeframe,
                "timestamp": {
                    "$gte": start_time,
                    "$lte": end_time
                }
            }

            time_count = self.charts.count_documents(time_query)
            logger.info(f"시간 범위로 조회: {time_count}개")

            if time_count == 0:
                logger.warning(f"시간 범위 {start_time} ~ {end_time}에 데이터가 없습니다")

                # 실제 저장된 데이터의 시간 범위 확인
                first_data = self.charts.find_one(timeframe_query, sort=[("timestamp", 1)])
                last_data = self.charts.find_one(timeframe_query, sort=[("timestamp", -1)])

                if first_data and last_data:
                    actual_start = first_data.get("timestamp")
                    actual_end = last_data.get("timestamp")
                    logger.info(f"실제 데이터 시간 범위: {actual_start} ~ {actual_end}")

                # 시간 범위 없이 조회해보기
                logger.info("시간 범위 없이 조회 시도...")
                cursor = self.charts.find(timeframe_query, {"_id": 0}).sort("timestamp", -1).limit(limit)
                result = list(cursor)
                logger.info(f"시간 범위 없이 조회 결과: {len(result)}개")
                return result

            # 5. 정상적인 시간 범위 조회
            cursor = self.charts.find(time_query, {"_id": 0}).sort("timestamp", -1).limit(limit)
            result = list(cursor)

            logger.info(f"최종 조회 결과: {len(result)}개")
            if result:
                logger.info(f"첫 번째 데이터: {result[0].get('timestamp')}")
                logger.info(f"마지막 데이터: {result[-1].get('timestamp')}")

            return result

        except Exception as e:
            logger.error(f"차트 히스토리 조회 실패: {e}")
            raise

    async def get_latest_indicators(
        self,
        market: str,
        timeframe: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        최신 지표 데이터 조회

        Args:
            market: 마켓 코드
            timeframe: 시간프레임
            limit: 최대 조회 개수

        Returns:
            최신 지표 데이터 리스트
        """
        try:
            cursor = self.charts.find(
                {
                    "market": market,
                    "timeframe": timeframe
                },
                {
                    "_id": 0,
                    "timestamp": 1,
                    "indicators": 1,
                    "signals": 1
                }
            ).sort("timestamp", -1).limit(limit)

            result = list(cursor)
            logger.info(f"최신 지표 조회: {market} {timeframe} {len(result)}개")
            return result

        except Exception as e:
            logger.error(f"최신 지표 조회 실패: {e}")
            raise

    async def save_ai_analysis(
        self,
        market: str,
        analysis: Dict[str, Any]
    ) -> str:
        """
        AI 분석 결과 저장

        Args:
            market: 마켓 코드
            analysis: AI 분석 결과

        Returns:
            저장된 문서의 ID
        """
        try:
            document = {
                "market": market,
                "timestamp": get_kst_now(),
                "analysis": analysis,
                "created_at": get_kst_now()
            }

            result = self.ai_analysis.insert_one(document)
            logger.info(f"AI 분석 결과 저장: {market}")
            return str(result.inserted_id)

        except Exception as e:
            logger.error(f"AI 분석 결과 저장 실패: {e}")
            raise

    async def get_ai_analysis_history(
        self,
        market: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        AI 분석 히스토리 조회

        Args:
            market: 마켓 코드
            start_time: 시작 시간
            end_time: 종료 시간
            limit: 최대 조회 개수

        Returns:
            AI 분석 결과 리스트
        """
        try:
            cursor = self.ai_analysis.find(
                {
                    "market": market,
                    "timestamp": {
                        "$gte": start_time,
                        "$lte": end_time
                    }
                },
                {"_id": 0}
            ).sort("timestamp", -1).limit(limit)

            result = list(cursor)
            logger.info(f"AI 분석 히스토리 조회: {market} {len(result)}개")
            return result

        except Exception as e:
            logger.error(f"AI 분석 히스토리 조회 실패: {e}")
            raise

    async def aggregate_daily_history(
        self,
        market: str,
        timeframe: str,
        target_date: datetime
    ) -> Dict[str, Any]:
        """
        일별 지표 집계

        Args:
            market: 마켓 코드
            timeframe: 시간프레임
            target_date: 대상 날짜

        Returns:
            일별 집계 결과
        """
        try:
            start_time = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = start_time + timedelta(days=1)

            pipeline = [
                {
                    "$match": {
                        "market": market,
                        "timeframe": timeframe,
                        "timestamp": {"$gte": start_time, "$lt": end_time}
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "hour": {"$hour": "$timestamp"}
                        },
                        "rsi_values": {"$push": "$indicators.rsi"},
                        "bb_bandwidth_values": {"$push": "$indicators.bb_bandwidth"},
                        "volume_values": {"$push": "$indicators.volume_z"},
                        "signals": {"$push": "$signals.overall"},
                        "close_prices": {"$push": "$indicators.close"}
                    }
                },
                {
                    "$project": {
                        "hour": "$_id.hour",
                        "rsi": {
                            "min": {"$min": "$rsi_values"},
                            "max": {"$max": "$rsi_values"},
                            "avg": {"$avg": "$rsi_values"},
                            "std": {"$stdDevPop": "$rsi_values"}
                        },
                        "bb_bandwidth": {
                            "min": {"$min": "$bb_bandwidth_values"},
                            "max": {"$max": "$bb_bandwidth_values"},
                            "avg": {"$avg": "$bb_bandwidth_values"}
                        },
                        "volume": {
                            "min": {"$min": "$volume_values"},
                            "max": {"$max": "$volume_values"},
                            "avg": {"$avg": "$volume_values"}
                        },
                        "price": {
                            "min": {"$min": "$close_prices"},
                            "max": {"$max": "$close_prices"},
                            "avg": {"$avg": "$close_prices"}
                        },
                        "signals_count": {
                            "buy": {"$size": {"$filter": {"input": "$signals", "cond": {"$eq": ["$$this", "BUY"]}}}},
                            "sell": {"$size": {"$filter": {"input": "$signals", "cond": {"$eq": ["$$this", "SELL"]}}}},
                            "hold": {"$size": {"$filter": {"input": "$signals", "cond": {"$eq": ["$$this", "HOLD"]}}}}
                        }
                    }
                },
                {"$sort": {"hour": 1}}
            ]

            result = list(self.charts.aggregate(pipeline))
            logger.info(f"일별 집계 완료: {market} {target_date.date()} {len(result)}시간")
            return result

        except Exception as e:
            logger.error(f"일별 집계 실패: {e}")
            raise

    async def get_market_statistics(
        self,
        market: str,
        timeframe: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        마켓 통계 정보 조회 (MongoDB 집계)
        """
        try:
            end_time = get_kst_now()
            start_time = end_time - timedelta(days=days)

            logger.info(f"마켓 통계 조회 시작: {market} {timeframe} {days}일")
            logger.info(f"조회 기간: {start_time} ~ {end_time}")

            # 먼저 데이터 존재 여부 확인
            count_check = self.charts.count_documents({
                "market": market,
                "timeframe": timeframe,
                "timestamp": {"$gte": start_time, "$lte": end_time}
            })

            logger.info(f"조회 조건에 맞는 데이터 개수: {count_check}")

            if count_check == 0:
                return {
                    "market": market,
                    "timeframe": timeframe,
                    "period_days": days,
                    "total_records": 0,
                    "start_date": start_time,
                    "end_date": end_time,
                    "message": "해당 기간에 데이터가 없습니다"
                }

            # 기본 통계 - 집계 파이프라인 수정
            pipeline = [
                {
                    "$match": {
                        "market": market,
                        "timeframe": timeframe,
                        "timestamp": {"$gte": start_time, "$lte": end_time}
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "total_records": {"$sum": 1},
                        "avg_rsi": {"$avg": "$indicators.rsi"},
                        "avg_volume_z": {"$avg": "$indicators.volume_z"},
                        "avg_bb_bandwidth": {"$avg": "$indicators.bb_bandwidth"},
                        "buy_signals": {"$sum": {"$cond": [{"$eq": ["$signals.overall", "BUY"]}, 1, 0]}},
                        "sell_signals": {"$sum": {"$cond": [{"$eq": ["$signals.overall", "SELL"]}, 1, 0]}},
                        "hold_signals": {"$sum": {"$cond": [{"$eq": ["$signals.overall", "HOLD"]}, 1, 0]}},
                        "min_price": {"$min": "$indicators.close"},
                        "max_price": {"$max": "$indicators.close"}
                    }
                }
            ]

            result = list(self.charts.aggregate(pipeline))

            if result:
                stats = result[0]
                stats["market"] = market
                stats["timeframe"] = timeframe
                stats["period_days"] = days
                stats["start_date"] = start_time
                stats["end_date"] = end_time
                stats["_id"] = None  # ObjectId 제거

                # 신호 요약 정리
                stats["signals_summary"] = {
                    "buy": stats.pop("buy_signals", 0),
                    "sell": stats.pop("sell_signals", 0),
                    "hold": stats.pop("hold_signals", 0)
                }

                # 가격 범위 정리
                stats["price_range"] = {
                    "min": stats.pop("min_price"),
                    "max": stats.pop("max_price")
                }

                logger.info(f"마켓 통계 조회 완료: {market} {timeframe} {days}일")
                return stats
            else:
                return {
                    "market": market,
                    "timeframe": timeframe,
                    "period_days": days,
                    "total_records": 0,
                    "start_date": start_time,
                    "end_date": end_time,
                    "message": "집계 결과가 없습니다"
                }

        except Exception as e:
            logger.error(f"마켓 통계 조회 실패: {e}")
            raise

    async def cleanup_old_data(self, days: int = 90) -> Dict[str, Any]:
        """
        오래된 데이터 정리

        Args:
            days: 보관할 일수

        Returns:
            정리 결과
        """
        try:
            cutoff_date = get_kst_now() - timedelta(days=days)

            # 오래된 차트 데이터 삭제
            charts_deleted = self.charts.delete_many({
                "created_at": {"$lt": cutoff_date}
            })

            # 오래된 AI 분석 데이터 삭제
            ai_deleted = self.ai_analysis.delete_many({
                "created_at": {"$lt": cutoff_date}
            })

            result = {
                "charts_deleted": charts_deleted.deleted_count,
                "ai_analysis_deleted": ai_deleted.deleted_count,
                "cutoff_date": cutoff_date,
                "cleanup_time": get_kst_now()
            }

            logger.info(f"데이터 정리 완료: 차트 {result['charts_deleted']}개, AI분석 {result['ai_analysis_deleted']}개")
            return result

        except Exception as e:
            logger.error(f"데이터 정리 실패: {e}")
            raise

    def close_connection(self):
        """MongoDB 연결 종료"""
        try:
            if hasattr(self, 'client'):
                self.client.close()
                logger.info("MongoDB 연결 종료")
        except Exception as e:
            logger.error(f"MongoDB 연결 종료 실패: {e}")

    def __del__(self):
        """소멸자에서 연결 종료"""
        self.close_connection()