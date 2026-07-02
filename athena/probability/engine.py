"""概率引擎 — 第一版：规则 + 信号驱动。

在 LLM 不可用时提供基于规则的概率估计，作为兜底。
后续通过 historical cases 校准。
"""

from typing import Dict, List, Optional, Tuple


def estimate_probability(
    signals: Dict,
    latest_price: float,
) -> Dict:
    """基于多类信号估计 +20% 上行 / -10% 下行概率。

    Args:
        signals: 包含 technical / fundamental / valuation 的信号字典
        latest_price: 当前价格

    Returns:
        {
            "upside_probability_range": [lower, upper],
            "downside_probability_range": [lower, upper],
            "confidence": str,
            "factors": {"bullish": [...], "bearish": [...]},
        }
    """
    tech = signals.get("technical", {})
    fund = signals.get("fundamental", {})
    val = signals.get("valuation", {})

    bullish = 0
    bearish = 0
    reasons_up = []
    reasons_down = []

    # ---- 技术面 ----
    # 均线排列
    alignment = tech.get("price", {}).get("alignment", {})
    if alignment.get("type") == "strong_bullish":
        bullish += 2
        reasons_up.append("强势多头排列")
    elif alignment.get("type") == "bullish":
        bullish += 1
        reasons_up.append("价格站上均线")
    elif alignment.get("type") in ("bearish", "below_ma200"):
        bearish += 2
        reasons_down.append("空头排列/低于 MA200")

    # RSI
    rsi = tech.get("momentum", {}).get("rsi14")
    if rsi is not None:
        if 40 < rsi < 60:
            pass  # 中性
        elif rsi > 70:
            bearish += 1
            reasons_down.append(f"RSI={rsi:.0f} 超买")
        elif rsi < 30:
            bullish += 1
            reasons_up.append(f"RSI={rsi:.0f} 超卖")

    # ATR 止损可行性
    atr_stop = tech.get("volatility", {}).get("atr_stop_assessment", {})
    if atr_stop.get("stop_loss_feasible") is False:
        bearish += 1
        reasons_down.append("-10% 止损容易被噪音触发")
    elif atr_stop.get("stop_loss_feasible") is True:
        bullish += 1

    # 52 周位置
    support = tech.get("support_resistance", {})
    pct_from_high = support.get("pct_from_high")
    pct_from_low = support.get("pct_from_low")
    if pct_from_high is not None and pct_from_high > -5:
        bearish += 1
        reasons_down.append("接近 52 周高点，上行空间有限")
    if pct_from_low is not None and pct_from_low < 10:
        bullish += 1
        reasons_up.append("接近 52 周低点，可能见底")

    # ---- 基本面 ----
    if fund.get("available"):
        # EPS
        eps = fund.get("eps", {})
        if eps.get("beat_pct", 0) > 3:
            bullish += 2
            reasons_up.append(f"EPS 超预期 {eps['beat_pct']:.0f}%")
        elif eps.get("beat_pct", 0) < 0:
            bearish += 2
            reasons_down.append(f"EPS 低于预期 {abs(eps['beat_pct']):.0f}%")

        # 营收
        rev = fund.get("revenue", {})
        if rev.get("beat_pct", 0) > 3:
            bullish += 1
            reasons_up.append(f"营收超预期 {rev['beat_pct']:.0f}%")
        elif rev.get("beat_pct", 0) < 0:
            bearish += 1
            reasons_down.append(f"营收低于预期 {abs(rev['beat_pct']):.0f}%")

    # ---- 估值 ----
    if val.get("available"):
        fwd_pe = val.get("forward_pe", {}).get("value")
        trailing_pe = val.get("trailing_pe", {}).get("current")

        if fwd_pe and fwd_pe > 40:
            bearish += 2
            reasons_down.append(f"Forward PE={fwd_pe:.0f} 极高")
        elif fwd_pe and fwd_pe < 15:
            bullish += 2
            reasons_up.append(f"Forward PE={fwd_pe:.0f} 偏低")
        elif trailing_pe and trailing_pe > 40:
            bearish += 1
            reasons_down.append(f"PE={trailing_pe:.0f} 偏高")

    # ---- 综合计算 ----
    total = bullish + bearish
    if total == 0:
        confidence = "Not Ready"
        up_mid = 33
        down_mid = 33
    else:
        up_ratio = bullish / total
        up_mid = round(15 + up_ratio * 55)
        down_mid = round(15 + (1 - up_ratio) * 55)

        # 5 档置信度（08_RISK §6）
        if bullish >= 5 and bullish > bearish * 2.0:
            confidence = "High"
        elif bearish >= 5 and bearish > bullish * 2.0:
            confidence = "Very Low"
        elif bullish > bearish * 1.5:
            confidence = "Medium"
        elif bearish > bullish * 1.5:
            confidence = "Low"
        elif total >= 3:
            confidence = "Medium"
        else:
            confidence = "Not Ready"

    return {
        "upside_probability_range": [max(5, up_mid - 10), min(90, up_mid + 10)],
        "downside_probability_range": [max(5, down_mid - 10), min(90, down_mid + 10)],
        "confidence": confidence,
        "factors": {
            "bullish": reasons_up[:5],
            "bearish": reasons_down[:5],
        },
    }


def _classify_status(prob_result: Dict) -> str:
    """根据概率结果判断 Candidate/Watch/Reject/Risk Alert"""
    up_low = prob_result["upside_probability_range"][0]
    down_high = prob_result["downside_probability_range"][1]

    if up_low > 33 and down_high < up_low:
        return "Candidate"
    elif down_high > 50:
        return "Risk Alert"
    elif up_low < 20:
        return "Reject"
    else:
        return "Watch"
