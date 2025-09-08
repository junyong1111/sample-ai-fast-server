"""
포트폴리오 유틸리티 함수 V2
수수료를 포함한 정확한 손익 계산 및 포트폴리오 분석
"""

from typing import Optional, Dict, Any, List
from src.common.utils.logger import set_logger

logger = set_logger("portfolio_utils")


def calculate_trading_fees(amount_usdt: float, fee_rate: float = 0.001) -> float:
    """거래 수수료 계산 (기본 0.1%)"""
    return round(amount_usdt * fee_rate, 8)


def calculate_net_profit(gross_profit_usdt: float, buy_fee: float, sell_fee: float) -> float:
    """수수료를 포함한 순수익 계산"""
    return round(gross_profit_usdt - buy_fee - sell_fee, 8)


def calculate_break_even_price(avg_entry_price: float, fee_rate: float = 0.001) -> float:
    """수수료를 고려한 손익분기점 계산"""
    # 매수 수수료를 포함한 실제 매수가격
    effective_buy_price = avg_entry_price * (1 + fee_rate)
    # 매도 수수료를 고려한 손익분기점
    break_even_price = effective_buy_price / (1 - fee_rate)
    return round(break_even_price, 2)


def calculate_effective_sell_price(current_price: float, fee_rate: float = 0.001) -> float:
    """수수료를 고려한 실제 매도가격 계산"""
    return round(current_price * (1 - fee_rate), 2)


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


def analyze_asset_with_fees(
    asset: str,
    balance: float,
    current_price: float,
    avg_entry_price: Optional[float],
    fee_rate: float = 0.001
) -> Dict[str, Any]:
    """자산별 수수료 포함 분석"""

    # 기본 정보
    current_value = balance * current_price

    # 수수료 계산
    buy_fee = 0.0
    sell_fee = calculate_trading_fees(current_value, fee_rate)

    if avg_entry_price and avg_entry_price > 0:
        # 매수 시 수수료 (원래 매수 금액 기준)
        original_buy_value = balance * avg_entry_price
        buy_fee = calculate_trading_fees(original_buy_value, fee_rate)

        # 손익 계산
        gross_profit = current_value - original_buy_value
        net_profit = calculate_net_profit(gross_profit, buy_fee, sell_fee)

        # 수익률 계산
        gross_profit_percentage = (gross_profit / original_buy_value) * 100
        net_profit_percentage = (net_profit / original_buy_value) * 100

        # 손익분기점
        break_even_price = calculate_break_even_price(avg_entry_price, fee_rate)

        # 실제 매도가격
        effective_sell_price = calculate_effective_sell_price(current_price, fee_rate)
        net_sell_value = balance * effective_sell_price

        # 수익성 판단
        is_profitable = net_profit > 0
        is_above_break_even = current_price >= break_even_price

    else:
        # 평균 매수가격이 없는 경우
        gross_profit = 0.0
        net_profit = 0.0
        gross_profit_percentage = 0.0
        net_profit_percentage = 0.0
        break_even_price = None
        effective_sell_price = calculate_effective_sell_price(current_price, fee_rate)
        net_sell_value = balance * effective_sell_price
        is_profitable = False
        is_above_break_even = False

    return {
        "asset": asset,
        "balance": balance,
        "current_price": current_price,
        "current_value": current_value,
        "avg_entry_price": avg_entry_price,

        # 수수료 정보
        "trading_fees": {
            "fee_rate": fee_rate,
            "estimated_buy_fee": buy_fee,
            "estimated_sell_fee": sell_fee,
            "total_fees": buy_fee + sell_fee
        },

        # 손익 분석
        "profit_loss": {
            "gross_profit_usdt": gross_profit,
            "net_profit_usdt": net_profit,
            "gross_profit_percentage": round(gross_profit_percentage, 2),
            "net_profit_percentage": round(net_profit_percentage, 2),
            "fee_impact_usdt": round((buy_fee + sell_fee), 8),
            "break_even_price": break_even_price
        },

        # 매도 분석
        "sell_analysis": {
            "gross_sell_value": current_value,
            "net_sell_value": net_sell_value,
            "effective_sell_price": effective_sell_price,
            "is_profitable": is_profitable,
            "is_above_break_even": is_above_break_even,
            "profit_after_fees": net_profit
        }
    }


def analyze_portfolio_with_fees(
    balances: List[Dict[str, Any]],
    current_prices: Dict[str, float],
    fee_rate: float = 0.001
) -> Dict[str, Any]:
    """포트폴리오 전체 수수료 포함 분석"""

    total_value = 0.0
    total_net_profit = 0.0
    total_fees = 0.0
    analyzed_assets = []

    for balance in balances:
        asset = balance.get("asset")
        balance_amount = balance.get("total", 0)
        avg_entry_price = balance.get("avg_entry_price")
        current_price = current_prices.get(asset, 0)

        if balance_amount > 0 and current_price > 0:
            asset_analysis = analyze_asset_with_fees(
                asset, balance_amount, current_price, avg_entry_price, fee_rate
            )
            analyzed_assets.append(asset_analysis)

            total_value += asset_analysis["current_value"]
            total_net_profit += asset_analysis["profit_loss"]["net_profit_usdt"]
            total_fees += asset_analysis["trading_fees"]["total_fees"]

    # 전체 포트폴리오 분석
    total_net_profit_percentage = (total_net_profit / total_value * 100) if total_value > 0 else 0

    return {
        "portfolio_summary": {
            "total_value": total_value,
            "total_net_profit": total_net_profit,
            "total_net_profit_percentage": round(total_net_profit_percentage, 2),
            "total_fees": total_fees,
            "fee_impact_percentage": round((total_fees / total_value * 100), 2) if total_value > 0 else 0
        },
        "assets": analyzed_assets
    }


def should_rebalance_with_fees(
    current_percentage: float,
    target_percentage: float,
    threshold: float,
    is_profitable: bool,
    net_profit_percentage: float
) -> Dict[str, Any]:
    """수수료를 고려한 리밸런싱 판단"""

    percentage_diff = abs(current_percentage - target_percentage)
    minimum_profit_threshold = 0.5
    should_rebalance = percentage_diff > threshold

    if should_rebalance:
        if not is_profitable and net_profit_percentage < -minimum_profit_threshold:
            return {
                "should_rebalance": False,
                "current_diff": percentage_diff,
                "threshold": threshold,
                "net_profit_percentage": net_profit_percentage
            }
        else:
            return {
                "should_rebalance": True,
                "current_diff": percentage_diff,
                "threshold": threshold,
                "net_profit_percentage": net_profit_percentage
            }
    else:
        return {
            "should_rebalance": False,
            "current_diff": percentage_diff,
            "threshold": threshold,
            "net_profit_percentage": net_profit_percentage
        }
