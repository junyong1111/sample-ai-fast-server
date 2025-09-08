"""
포트폴리오 유틸리티 함수
손절/익절 판단 및 리스크 관리 계산
"""

from typing import Optional, Dict, Any
from src.common.utils.logger import set_logger

logger = set_logger("portfolio_utils")


def calculate_pnl_percentage(current_price: float, avg_entry_price: Optional[float]) -> Optional[float]:
    """손익률 계산 (백분율)"""
    if not avg_entry_price or avg_entry_price <= 0:
        return None

    pnl_percentage = ((current_price - avg_entry_price) / avg_entry_price) * 100
    return round(pnl_percentage, 2)


def calculate_stop_loss_price(avg_entry_price: float, stop_loss_percentage: float = 5.0) -> float:
    """손절가격 계산"""
    stop_loss_price = avg_entry_price * (1 - stop_loss_percentage / 100)
    return round(stop_loss_price, 2)


def calculate_take_profit_price(avg_entry_price: float, take_profit_percentage: float = 10.0) -> float:
    """목표가격 계산"""
    take_profit_price = avg_entry_price * (1 + take_profit_percentage / 100)
    return round(take_profit_price, 2)


def determine_trade_signal(current_price: float, avg_entry_price: Optional[float],
                          stop_loss_percentage: float = 5.0,
                          take_profit_percentage: float = 10.0) -> Dict[str, Any]:
    """거래 신호 판단"""
    if not avg_entry_price or avg_entry_price <= 0:
        return {
            "signal": "HOLD",
            "reason": "평균 매수가격 정보 없음",
            "pnl_percentage": None,
            "stop_loss_price": None,
            "take_profit_price": None,
            "is_stop_loss": False,
            "is_take_profit": False
        }

    # 손익률 계산
    pnl_percentage = calculate_pnl_percentage(current_price, avg_entry_price)

    # 손절/목표가격 계산
    stop_loss_price = calculate_stop_loss_price(avg_entry_price, stop_loss_percentage)
    take_profit_price = calculate_take_profit_price(avg_entry_price, take_profit_percentage)

    # 신호 판단
    is_stop_loss = current_price <= stop_loss_price
    is_take_profit = current_price >= take_profit_price

    if is_stop_loss:
        signal = "SELL"
        reason = f"손절 신호: 현재가({current_price}) <= 손절가({stop_loss_price})"
    elif is_take_profit:
        signal = "SELL"
        reason = f"익절 신호: 현재가({current_price}) >= 목표가({take_profit_price})"
    else:
        signal = "HOLD"
        reason = f"보유 유지: 손익률 {pnl_percentage}%"

    return {
        "signal": signal,
        "reason": reason,
        "pnl_percentage": pnl_percentage,
        "stop_loss_price": stop_loss_price,
        "take_profit_price": take_profit_price,
        "is_stop_loss": is_stop_loss,
        "is_take_profit": is_take_profit
    }


def calculate_risk_reward_ratio(avg_entry_price: float, stop_loss_percentage: float = 5.0,
                               take_profit_percentage: float = 10.0) -> float:
    """리스크-리워드 비율 계산"""
    risk_amount = avg_entry_price * (stop_loss_percentage / 100)
    reward_amount = avg_entry_price * (take_profit_percentage / 100)

    if risk_amount > 0:
        return round(reward_amount / risk_amount, 2)
    return 0.0


def analyze_portfolio_risk(btc_balance: float, btc_price: float, avg_entry_price: Optional[float],
                          total_value: float, btc_percentage: float) -> Dict[str, Any]:
    """포트폴리오 리스크 분석"""
    analysis = {
        "btc_value": btc_balance * btc_price,
        "btc_percentage": btc_percentage,
        "avg_entry_price": avg_entry_price,
        "current_price": btc_price,
        "pnl_percentage": None,
        "risk_level": "UNKNOWN",
        "recommendations": []
    }

    # 손익률 계산
    if avg_entry_price and avg_entry_price > 0:
        analysis["pnl_percentage"] = calculate_pnl_percentage(btc_price, avg_entry_price)

        # 리스크 레벨 판단
        if analysis["pnl_percentage"] >= 20:
            analysis["risk_level"] = "HIGH_PROFIT"
            analysis["recommendations"].append("고수익 상태: 일부 익절 고려")
        elif analysis["pnl_percentage"] >= 10:
            analysis["risk_level"] = "MEDIUM_PROFIT"
            analysis["recommendations"].append("수익 상태: 목표가 설정 고려")
        elif analysis["pnl_percentage"] >= -5:
            analysis["risk_level"] = "NORMAL"
            analysis["recommendations"].append("정상 범위: 현재 전략 유지")
        elif analysis["pnl_percentage"] >= -10:
            analysis["risk_level"] = "MEDIUM_LOSS"
            analysis["recommendations"].append("손실 상태: 손절가 확인 필요")
        else:
            analysis["risk_level"] = "HIGH_LOSS"
            analysis["recommendations"].append("큰 손실: 손절 검토 필요")

    # BTC 비중 분석
    if btc_percentage > 80:
        analysis["risk_level"] = "CONCENTRATED"
        analysis["recommendations"].append("BTC 집중도 높음: 분산투자 고려")
    elif btc_percentage < 10:
        analysis["risk_level"] = "UNDERWEIGHT"
        analysis["recommendations"].append("BTC 비중 낮음: 추가 매수 고려")

    return analysis
