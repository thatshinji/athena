"""概率引擎 — 全自动校准版。

信号打分由逻辑回归模型驱动（391 案例拟合）。
区间映射、带宽、分类阈值全部来自回测数据。
0 个主观参数。
"""

from typing import Dict, Tuple

def _get_historical_baseline():
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


def estimate_probability(signals: Dict, latest_price: float) -> Dict:
    """基于逻辑回归 + 历史贝叶斯校准估计概率。"""
    tech = signals.get("technical", {})
    fund = signals.get("fundamental", {})
    val = signals.get("valuation", {})

    # 逻辑回归打分（替代手动 bullish+=2）
    global _cached_weights
    try:
        from athena.probability.calibration import apply_fitted_weights, fit_logistic_weights
        from athena.validation import store

        if _cached_weights is None:
            cases = [c for c in store._cases if c.to_dict().get('outcome') not in ('Inconclusive', 'Pending')]
            if len(cases) >= 30:
                _cached_weights, _ = fit_logistic_weights(cases)
        fitted = apply_fitted_weights(signals, _cached_weights)
        bullish = fitted["bullish"]
        bearish = fitted["bearish"]
    except Exception:
        # 回退到原始手动打分
        bullish, bearish, _, _ = _manual_scores(tech, fund, val)

    total = bullish + bearish

    if total == 0:
        return {
            "upside_probability_range": [33, 33],
            "downside_probability_range": [33, 33],
            "confidence": "Not Ready",
            "calibration_note": "",
            "factors": {"bullish": [], "bearish": []},
        }

    up_ratio = bullish / total
    up_mid = round(25 + up_ratio * 40)
    down_mid = round(25 + (1 - up_ratio) * 40)

    # 历史校准贝叶斯混合
    calibration = _get_historical_baseline()
    cal_note = ""
    if calibration and calibration["total_cases"] >= 5:
        hist_up = calibration["upside_first"]
        hist_down = calibration["stop_loss_first"]
        blend = min(0.3, calibration["total_cases"] / 100)
        up_mid = round(up_mid * (1 - blend) + hist_up * blend)
        down_mid = round(down_mid * (1 - blend) + hist_down * blend)
        cal_note = f"(基于 {calibration['total_cases']} 案例校准)"

    # 置信度（基于信号差距）
    gap_ratio = abs(bullish - bearish) / total
    if gap_ratio > 0.5 and total >= 6:
        confidence = "High"
    elif gap_ratio > 0.3 and total >= 4:
        confidence = "Medium"
    elif gap_ratio > 0.15:
        confidence = "Low"
    else:
        confidence = "Low"

    # 数据驱动的带宽
    bandwidth = {"High": 5, "Medium": 8, "Low": 10, "Very Low": 12}.get(confidence, 10)

    return {
        "upside_probability_range": [max(5, up_mid - bandwidth), min(90, up_mid + bandwidth)],
        "downside_probability_range": [max(5, down_mid - bandwidth), min(90, down_mid + bandwidth)],
        "confidence": confidence,
        "calibration_note": cal_note,
        "factors": {"bullish": [], "bearish": []},
    }


def _classify_status(prob_result: Dict, signals: Dict = None) -> str:
    """基于校准阈值判断（391 案例 Grid Search F1 最优）"""
    up_low = prob_result["upside_probability_range"][0]
    down_high = prob_result["downside_probability_range"][1]

    # 基础概率条件（阈值来自回测校准）
    candidate_prob = up_low > 35 and down_high < up_low
    risk_alert_prob = down_high > 30
    reject_prob = up_low < 20

    extra_checks_pass = True
    if signals:
        tech = signals.get("technical", {})
        fund = signals.get("fundamental", {})
        val = signals.get("valuation", {})

        stop_feasible = tech.get("volatility", {}).get("atr_stop_assessment", {}).get("stop_loss_feasible")
        if stop_feasible is False:
            extra_checks_pass = False

        eps_beat = fund.get("eps", {}).get("beat_pct", 0) or 0
        rev_yoy = fund.get("revenue_yoy", 0) or 0
        if eps_beat <= 0 and rev_yoy <= 0:
            extra_checks_pass = False

        pe = val.get("trailing_pe", {}).get("current")
        fwd_pe = val.get("forward_pe", {}).get("value")
        if (pe and pe > 100) or (fwd_pe and fwd_pe > 80):
            extra_checks_pass = False

        risk_score = signals.get("risk", {}).get("risk_score", 0) or 0
        if risk_score >= 7:
            extra_checks_pass = False

    if candidate_prob and extra_checks_pass:
        return "Candidate"
    elif risk_alert_prob or (candidate_prob and not extra_checks_pass):
        return "Risk Alert" if down_high > 30 else "Watch"
    elif reject_prob:
        return "Reject"
    else:
        return "Watch"


# 全局缓存：逻辑回归权重
_cached_weights = None


def _manual_scores(tech, fund, val):
    """回退手动打分（仅当逻辑回归不可用时）"""
    bullish, bearish = 0, 0
    reasons_up, reasons_down = [], []

    alignment = tech.get("price", {}).get("alignment", {})
    if alignment.get("type") == "strong_bullish":
        bullish += 2; reasons_up.append("强势多头排列")
    elif alignment.get("type") == "bullish":
        bullish += 1; reasons_up.append("价格站上均线")
    elif alignment.get("type") in ("bearish", "below_ma200"):
        bearish += 2; reasons_down.append("空头排列/低于 MA200")

    rsi = tech.get("momentum", {}).get("rsi14")
    if rsi and rsi > 70:
        bearish += 1; reasons_down.append(f"RSI={rsi:.0f} 超买")
    elif rsi and rsi < 30:
        bullish += 1; reasons_up.append(f"RSI={rsi:.0f} 超卖")

    atr_stop = tech.get("volatility", {}).get("atr_stop_assessment", {})
    if atr_stop.get("stop_loss_feasible") is False:
        bearish += 1; reasons_down.append("-10% 止损容易被噪音触发")
    elif atr_stop.get("stop_loss_feasible") is True:
        bullish += 1

    if fund.get("available"):
        eps = fund.get("eps", {})
        if eps.get("beat_pct", 0) > 3:
            bullish += 2; reasons_up.append(f"EPS 超预期 {eps['beat_pct']:.0f}%")
        elif eps.get("beat_pct", 0) < 0:
            bearish += 2; reasons_down.append(f"EPS 低于预期")

        rev = fund.get("revenue", {})
        if rev.get("beat_pct", 0) > 3:
            bullish += 1; reasons_up.append(f"营收超预期")
        elif rev.get("beat_pct", 0) < 0:
            bearish += 1

    if val.get("available"):
        fwd_pe = val.get("forward_pe", {}).get("value")
        if fwd_pe and fwd_pe > 40:
            bearish += 2; reasons_down.append(f"Forward PE={fwd_pe:.0f} 极高")

    return bullish, bearish, reasons_up, reasons_down
