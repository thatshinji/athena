"""概率引擎 — 第一版：规则 + 信号驱动。

在 LLM 不可用时提供基于规则的概率估计。
通过 validation 历史案例库做统计校准，避免纯主观打分。
"""

from typing import Dict, List, Optional, Tuple


def _get_historical_baseline():
    """从 validation 历史案例库获取校准基准。"""
    try:
        from athena.validation import store
        m = store.calibration_metrics()
        if m.get("resolved_cases", 0) >= 5:
            return {
                "success_rate": m["candidate_success_rate"],
                "upside_first": m["upside_first_rate"],
                "stop_loss_first": m["stop_loss_first_rate"],
                "total_cases": m["resolved_cases"],
            }
    except Exception:
        pass
    return None


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

        # ---- 历史校准修正（贝叶斯风格回归） ----
        calibration = _get_historical_baseline()
        cal_note = ""
        if calibration and calibration["total_cases"] >= 5:
            hist_up = calibration["upside_first"]
            hist_down = calibration["stop_loss_first"]
            blend = min(0.3, calibration["total_cases"] / 100)
            up_mid = round(up_mid * (1 - blend) + hist_up * blend)
            down_mid = round(down_mid * (1 - blend) + hist_down * blend)
            cal_note = f" (基于 {calibration['total_cases']} 案例校准)"

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
        "calibration_note": cal_note if cal_note else "",
        "factors": {
            "bullish": reasons_up[:5],
            "bearish": reasons_down[:5],
        },
    }


def _classify_status(prob_result: Dict, signals: Dict = None) -> str:
    """根据概率 + 7 个 Candidate 条件判断（08_RISK §2）"""
    up_low = prob_result["upside_probability_range"][0]
    down_high = prob_result["downside_probability_range"][1]
    factors = prob_result.get("factors", {})

    # 基础概率条件
    candidate_prob = up_low > 33 and down_high < up_low
    risk_alert_prob = down_high > 50
    reject_prob = up_low < 20

    # 用信号数据检查剩余条件（如果提供）
    extra_checks_pass = True
    extra_checks_fail_reason = ""
    if signals:
        tech = signals.get("technical", {})
        fund = signals.get("fundamental", {})
        val = signals.get("valuation", {})
        risk = signals.get("risk", {})

        # 条件 4: 技术面不破坏止损
        stop_feasible = tech.get("volatility", {}).get("atr_stop_assessment", {}).get("stop_loss_feasible")
        if stop_feasible is False:
            extra_checks_pass = False
            extra_checks_fail_reason = "止损不可执行"

        # 条件 5: 基本面或预期至少一项改善
        eps_beat = fund.get("eps", {}).get("beat_pct", 0) or 0
        rev_yoy = fund.get("revenue_yoy", 0) or 0
        if eps_beat <= 0 and rev_yoy <= 0:
            extra_checks_pass = False
            extra_checks_fail_reason = "基本面无改善"

        # 条件 6: 估值未严重透支
        pe = val.get("trailing_pe", {}).get("current")
        fwd_pe = val.get("forward_pe", {}).get("value")
        if (pe and pe > 100) or (fwd_pe and fwd_pe > 80):
            extra_checks_pass = False
            extra_checks_fail_reason = "估值严重透支"

        # 条件 7: 无重大单点风险
        risk_score = risk.get("risk_score", 0) or 0
        if risk_score >= 7:
            extra_checks_pass = False
            extra_checks_fail_reason = f"风险评分过高 ({risk_score}/10)"

    # 综合判断
    if candidate_prob and extra_checks_pass:
        return "Candidate"
    elif risk_alert_prob or (candidate_prob and not extra_checks_pass):
        return "Risk Alert" if down_high > 40 else "Watch"
    elif reject_prob:
        return "Reject"
    else:
        return "Watch"
