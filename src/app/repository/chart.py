# # src/app/repository/chart_repository.py
# from typing import Dict, Any, List, Optional
# from datetime import datetime, timedelta
# from pymongo import MongoClient
# from pymongo.collection import Collection
# import pandas as pd

# class ChartRepository:
#     def __init__(self, mongo_uri: str, db_name: str = "trading_ai"):
#         self.client = MongoClient(mongo_uri)
#         self.db = self.client[db_name]
#         self.charts = self.db.charts
#         self.history = self.db.indicator_history
#         self.ai_analysis = self.db.ai_analysis

#         # 인덱스 생성
#         self._create_indexes()

#     def _create_indexes(self):
#         """성능 최적화를 위한 인덱스 생성"""
#         # 차트 데이터: 마켓 + 시간 기반 조회
#         self.charts.create_index([
#             ("market", 1),
#             ("timestamp", -1)
#         ])

#         # 차트 데이터: 마켓 + 타임프레임 + 시간
#         self.charts.create_index([
#             ("market", 1),
#             ("timeframe", 1),
#             ("timestamp", -1)
#         ])

#         # 히스토리: 마켓 + 날짜
#         self.history.create_index([
#             ("market", 1),
#             ("date", -1)
#         ])

#     async def save_chart_data(
#         self,
#         market: str,
#         timeframe: str,
#         indicators: Dict[str, Any],
#         signals: Dict[str, Any],
#         candle_data: Dict[str, Any]
#     ) -> str:
#         """실시간 차트 데이터 저장"""
#         document = {
#             "market": market,
#             "timeframe": timeframe,
#             "timestamp": indicators.get("time", datetime.utcnow()),
#             "candle": candle_data,
#             "indicators": indicators,
#             "signals": signals,
#             "created_at": datetime.utcnow()
#         }

#         result = self.charts.insert_one(document)
#         return str(result.inserted_id)

#     async def get_chart_history(
#         self,
#         market: str,
#         timeframe: str,
#         start_time: datetime,
#         end_time: datetime,
#         limit: int = 1000
#     ) -> List[Dict[str, Any]]:
#         """특정 기간 차트 데이터 조회"""
#         cursor = self.charts.find(
#             {
#                 "market": market,
#                 "timeframe": timeframe,
#                 "timestamp": {
#                     "$gte": start_time,
#                     "$lte": end_time
#                 }
#             },
#             {"_id": 0}  # ObjectId 제외
#         ).sort("timestamp", -1).limit(limit)

#         return list(cursor)

#     async def get_latest_indicators(
#         self,
#         market: str,
#         timeframe: str,
#         limit: int = 100
#     ) -> List[Dict[str, Any]]:
#         """최신 지표 데이터 조회"""
#         cursor = self.charts.find(
#             {
#                 "market": market,
#                 "timeframe": timeframe
#             },
#             {
#                 "_id": 0,
#                 "timestamp": 1,
#                 "indicators": 1,
#                 "signals": 1
#             }
#         ).sort("timestamp", -1).limit(limit)

#         return list(cursor)

#     async def save_ai_analysis(
#         self,
#         market: str,
#         analysis: Dict[str, Any]
#     ) -> str:
#         """AI 분석 결과 저장"""
#         document = {
#             "market": market,
#             "timestamp": datetime.utcnow(),
#             "analysis": analysis,
#             "created_at": datetime.utcnow()
#         }

#         result = self.ai_analysis.insert_one(document)
#         return str(result.inserted_id)

#     async def aggregate_daily_history(
#         self,
#         market: str,
#         timeframe: str,
#         target_date: datetime
#     ) -> Dict[str, Any]:
#         """일별 지표 집계"""
#         start_time = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
#         end_time = start_time + timedelta(days=1)

#         pipeline = [
#             {
#                 "$match": {
#                     "market": market,
#                     "timeframe": timeframe,
#                     "timestamp": {"$gte": start_time, "$lt": end_time}
#                 }
#             },
#             {
#                 "$group": {
#                     "_id": {
#                         "hour": {"$hour": "$timestamp"}
#                     },
#                     "rsi_values": {"$push": "$indicators.rsi"},
#                     "bb_bandwidth_values": {"$push": "$indicators.bb_bandwidth"},
#                     "signals": {"$push": "$signals.overall"}
#                 }
#             },
#             {
#                 "$project": {
#                     "hour": "$_id.hour",
#                     "rsi": {
#                         "min": {"$min": "$rsi_values"},
#                         "max": {"$max": "$rsi_values"},
#                         "avg": {"$avg": "$rsi_values"}
#                     },
#                     "bb_bandwidth": {
#                         "min": {"$min": "$bb_bandwidth_values"},
#                         "max": {"$max": "$bb_bandwidth_values"},
#                         "avg": {"$avg": "$bb_bandwidth_values"}
#                     },
#                     "signals_count": {
#                         "buy": {"$size": {"$filter": {"input": "$signals", "cond": {"$eq": ["$$this", "BUY"]}}}},
#                         "sell": {"$size": {"$filter": {"input": "$signals", "cond": {"$eq": ["$$this", "SELL"]}}}},
#                         "hold": {"$size": {"$filter": {"input": "$signals", "cond": {"$eq": ["$$this", "HOLD"]}}}}
#                     }
#                 }
#             },
#             {"$sort": {"hour": 1}}
#         ]

#         result = list(self.charts.aggregate(pipeline))
#         return result