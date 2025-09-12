"""
분석 보고서 관련 모델
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class AnalysisReportRequest(BaseModel):
    """분석 보고서 저장 요청 모델"""
    user_idx: int
    market_regime: Optional[str] = None  # 'TREND' or 'RANGE'
    used_regime_weights: Optional[Dict[str, Any]] = None
    quant_report: Optional[Dict[str, Any]] = None
    social_report: Optional[Dict[str, Any]] = None
    risk_report: Optional[Dict[str, Any]] = None
    analyst_summary: Optional[Dict[str, Any]] = None


class AnalysisReportResponse(BaseModel):
    """분석 보고서 저장 응답 모델"""
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None


class AnalysisReportData(BaseModel):
    """분석 보고서 데이터 모델"""
    idx: int
    user_idx: int
    timestamp: datetime
    market_regime: Optional[str] = None
    used_regime_weights: Optional[Dict[str, Any]] = None
    quant_report: Optional[Dict[str, Any]] = None
    social_report: Optional[Dict[str, Any]] = None
    risk_report: Optional[Dict[str, Any]] = None
    analyst_summary: Optional[Dict[str, Any]] = None
