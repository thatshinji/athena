"""风险信号模块 — 跨技术面/基本面/估值聚合风险。

从现有信号中提取风险因子，给出结构化风险评估。
对应 Research Input: RK-001 Overall Risk Level。
"""

from typing import Any, Dict, List, Optional


def compute_risk_signals(
    tech_signals: Dict,
    fund_signals: Dict,
    val_signals: Dict,
) -> Dict:
    """从三类信号聚合风险。

    Args:
        tech_signals: compute_technical_signals() 返回的 signals["signals"]
        fund_signals: compute_fundamental_signals() 返回的 signals["signals"]
        val_signals: compute_valuation_signals() 返回的 signals["signals"]

    Returns:
        {"signals": {...}, "research_inputs": {...}}
    """
    risks: List[Dict] = []
    risk_score = 0  # 0-10, 越高风险越大

    # ---- 技术面风险 ----
    # ATR 过高
    atr_stop = tech_signals.get("volatility", {}).get("atr_stop_assessment", {})
    if atr_stop.get("stop_loss_feasible") is False:
        atr_pct = tech_signals.get("volatility", {}).get("atr_pct", 0)
        risk_score += 2
        risks.append({
            "source": "technical",
            "factor": "High Volatility",
            "severity": "high" if (atr_pct and atr_pct > 7) else "medium",
            "description": f"ATR%={atr_pct}%，-10% 止损容易被日常波动触发",
        })

    # 空头排列
    alignment = tech_signals.get("price", {}).get("alignment", {})
    if alignment.get("type") in ("bearish", "below_ma200"):
        risk_score += 2
        risks.append({
            "source": "technical",
            "factor": "Bearish Alignment",
            "severity": "high" if alignment.get("type") == "below_ma200" else "medium",
            "description": alignment.get("description_zh", "空头排列"),
        })

    # RSI 极端
    rsi = tech_signals.get("momentum", {}).get("rsi14")
    if rsi is not None and rsi > 70:
        risk_score += 1
        risks.append({
            "source": "technical", "factor": "RSI Overbought",
            "severity": "low", "description": f"RSI={rsi:.0f} 超买，回调风险",
        })

    # 接近 52 周高点
    support = tech_signals.get("support_resistance", {})
    pct_from_high = support.get("pct_from_high")
    if pct_from_high is not None and pct_from_high > -5:
        risk_score += 1
        risks.append({
            "source": "technical", "factor": "Near 52W High",
            "severity": "low", "description": "接近 52 周高点，上行空间有限",
        })

    # ---- 基本面风险 ----
    if fund_signals.get("available"):
        # 营收 miss
        rev = fund_signals.get("revenue", {})
        if rev.get("beat_pct", 0) < -3:
            risk_score += 2
            risks.append({
                "source": "fundamental", "factor": "Revenue Miss",
                "severity": "high", "description": f"营收低于预期 {abs(rev['beat_pct']):.0f}%",
            })
        elif rev.get("beat_pct", 0) < 0:
            risk_score += 1
            risks.append({
                "source": "fundamental", "factor": "Revenue Slight Miss",
                "severity": "medium", "description": f"营收略低于预期 {abs(rev['beat_pct']):.1f}%",
            })

        # EPS miss
        eps = fund_signals.get("eps", {})
        if eps.get("beat_pct", 0) < -5:
            risk_score += 2
            risks.append({
                "source": "fundamental", "factor": "EPS Miss",
                "severity": "high", "description": f"EPS 低于预期 {abs(eps['beat_pct']):.0f}%",
            })

    # ---- 估值风险 ----
    if val_signals.get("available"):
        fwd_pe = val_signals.get("forward_pe", {}).get("value")
        if fwd_pe and fwd_pe > 40:
            risk_score += 3
            risks.append({
                "source": "valuation", "factor": "Extreme Valuation",
                "severity": "high", "description": f"Forward PE={fwd_pe:.0f}，估值透支严重",
            })
        elif fwd_pe and fwd_pe > 25:
            risk_score += 1
            risks.append({
                "source": "valuation", "factor": "Elevated Valuation",
                "severity": "medium", "description": f"Forward PE={fwd_pe:.0f}，估值偏高",
            })

        # PE 负值
        pe = val_signals.get("trailing_pe", {}).get("current")
        if pe is not None and pe < 0:
            risk_score += 2
            risks.append({
                "source": "valuation", "factor": "Negative Earnings",
                "severity": "high", "description": "PE 为负，公司亏损",
            })

    # ---- 综合评估 ----
    risk_level, risk_desc = _classify_risk(risk_score)

    return {
        "signals": {
            "available": True,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "description": risk_desc,
            "factors": risks,
        },
        "research_inputs": {
            "RK-001": {
                "label": "Overall Risk Level",
                "claim": f"风险评分={risk_score}/10, 等级={risk_level}",
                "assessment": risk_desc,
            },
        },
    }


def _classify_risk(score: int):
    if score >= 7:
        return "Critical", f"风险评分 {score}/10，多重风险叠加，强烈建议规避"
    elif score >= 5:
        return "High", f"风险评分 {score}/10，存在多个显著风险因素"
    elif score >= 3:
        return "Medium", f"风险评分 {score}/10，存在一些值得关注的风险"
    else:
        return "Low", f"风险评分 {score}/10，当前未发现重大风险信号"
