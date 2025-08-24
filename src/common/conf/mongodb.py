"""
MongoDB 설정 관리
"""
import os
from typing import Optional
from datetime import timezone, timedelta

# KST 시간대 설정 (UTC+9)
KST = timezone(timedelta(hours=9))

class MongoDBConfig:
    """MongoDB 연결 설정"""

    # 기본 연결 정보
    DEFAULT_URI = "mongodb://localhost:27017"
    DEFAULT_DB = "trading_ai"

    # 환경 변수에서 설정 가져오기
    MONGO_URI = os.getenv("MONGO_URI", DEFAULT_URI)
    MONGO_DB = os.getenv("MONGO_DB", DEFAULT_DB)

    # 연결 옵션
    CONNECTION_TIMEOUT_MS = int(os.getenv("MONGO_CONNECTION_TIMEOUT_MS", "5000"))
    SERVER_SELECTION_TIMEOUT_MS = int(os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "5000"))
    MAX_POOL_SIZE = int(os.getenv("MONGO_MAX_POOL_SIZE", "100"))
    MIN_POOL_SIZE = int(os.getenv("MONGO_MIN_POOL_SIZE", "0"))

    # 인덱스 설정
    TTL_DAYS = int(os.getenv("MONGO_TTL_DAYS", "90"))

    # 백업 설정
    BACKUP_ENABLED = os.getenv("MONGO_BACKUP_ENABLED", "false").lower() == "true"
    BACKUP_INTERVAL_HOURS = int(os.getenv("MONGO_BACKUP_INTERVAL_HOURS", "24"))

    # 시간대 설정
    TIMEZONE = os.getenv("TIMEZONE", "KST")  # KST 또는 UTC
    USE_KST = TIMEZONE.upper() == "KST"

    @classmethod
    def get_connection_string(cls) -> str:
        """연결 문자열 반환"""
        return cls.MONGO_URI

    @classmethod
    def get_database_name(cls) -> str:
        """데이터베이스 이름 반환"""
        return cls.MONGO_DB

    @classmethod
    def get_connection_options(cls) -> dict:
        """연결 옵션 반환"""
        return {
            "serverSelectionTimeoutMS": cls.SERVER_SELECTION_TIMEOUT_MS,
            "connectTimeoutMS": cls.CONNECTION_TIMEOUT_MS,
            "maxPoolSize": cls.MAX_POOL_SIZE,
            "minPoolSize": cls.MIN_POOL_SIZE,
            "retryWrites": True,
            "w": "majority"
        }

    @classmethod
    def is_production(cls) -> bool:
        """프로덕션 환경 여부 확인"""
        return os.getenv("ENVIRONMENT", "development").lower() == "production"

    @classmethod
    def use_kst_timezone(cls) -> bool:
        """KST 시간대 사용 여부"""
        return cls.USE_KST

    @classmethod
    def get_kst_timezone(cls):
        """KST 시간대 객체 반환"""
        return KST if cls.USE_KST else timezone.utc

    @classmethod
    def get_collection_names(cls) -> dict:
        """컬렉션 이름 매핑"""
        return {
            "charts": "charts",
            "indicator_history": "indicator_history",
            "ai_analysis": "ai_analysis",
            "market_stats": "market_stats",
            "backtest_results": "backtest_results",
            "trading_signals": "trading_signals"
        }

    @classmethod
    def get_index_configs(cls) -> list:
        """인덱스 설정 목록"""
        return [
            # 차트 데이터 인덱스
            {
                "collection": "charts",
                "indexes": [
                    [("market", 1), ("timestamp", -1)],
                    [("market", 1), ("timeframe", 1), ("timestamp", -1)],
                    [("created_at", 1), {"expireAfterSeconds": cls.TTL_DAYS * 24 * 60 * 60}]
                ]
            },
            # 히스토리 인덱스
            {
                "collection": "indicator_history",
                "indexes": [
                    [("market", 1), ("date", -1)],
                    [("market", 1), ("timeframe", 1), ("date", -1)]
                ]
            },
            # AI 분석 인덱스
            {
                "collection": "ai_analysis",
                "indexes": [
                    [("market", 1), ("timestamp", -1)],
                    [("analysis.recommendation", 1), ("timestamp", -1)]
                ]
            },
            # 시장 통계 인덱스
            {
                "collection": "market_stats",
                "indexes": [
                    [("market", 1), ("date", -1)],
                    [("market", 1), ("timeframe", 1), ("date", -1)]
                ]
            }
        ]
