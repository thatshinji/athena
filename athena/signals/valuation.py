"""估值信号模块。

从 Longbridge valuation 数据提取：
- VL-001 Trailing PE
- VL-002 Forward PE（从一致预期推导）
- PEG
"""

from typing import Any, Dict, Optional


def compute_valuation_signals(
    fund_data: Optional[Dict[str, Any]],
    latest_price: float,
) -> Dict:
    """从估值数据生成结构化信号。

    Args:
        fund_data: fetch_fundamentals() 的返回值
        latest_price: 当前股价

    Returns:
        {"signals": {...}, "research_inputs": {...}}
    """
    if not fund_data or "valuation" not in fund_data:
        return {
            "signals": {"available": False, "description": "估值数据不可用"},
            "research_inputs": {
                "VL-001": {"label": "Trailing PE", "claim": "无数据", "assessment": "N/A"},
                "VL-002": {"label": "Forward PE (Est.)", "claim": "无数据", "assessment": "N/A"},
            },
        }

    val = fund_data.get("valuation", {})
    consensus = fund_data.get("consensus", {})
    signals = {"available": True}
    research_inputs = {}

    # ---- VL-001 Trailing PE ----
    pe = val.get("pe", {})
    if pe:
        pe_current = pe.get("current")
        pe_high = pe.get("high")
        pe_low = pe.get("low")
        pe_desc = pe.get("desc", "")

        # 解析 percentile 信息（从 desc 文本提取）
        percentile = _parse_percentile(pe_desc)

        signals["trailing_pe"] = {
            "current": pe_current,
            "high": pe_high,
            "low": pe_low,
            "percentile": percentile,
        }

        # 判断估值位置
        if pe_current and pe_high:
            position = round(pe_current / pe_high * 100, 1)
            signals["pe_vs_range"] = position

        assessment = _assess_pe(pe_current, percentile)
        signals["pe_assessment"] = assessment

        research_inputs["VL-001"] = {
            "label": "Trailing PE",
            "claim": (
                f"PE={pe_current}, 处于历史 {percentile}% 分位"
                if percentile is not None
                else f"PE={pe_current}"
            ),
            "assessment": assessment["description_zh"],
        }

    # ---- VL-002 Forward PE (从 EPS consensus 推导) ----
    eps_consensus = consensus.get("normalized_eps", {}) or consensus.get("eps", {})
    if eps_consensus and latest_price:
        est_eps = eps_consensus.get("estimate")
        if est_eps and est_eps > 0:
            # 一致预期 EPS 为单季数据，年化（×4）后计算 Forward PE
            annual_eps = est_eps * 4
            fwd_pe = round(latest_price / annual_eps, 1)
            signals["forward_pe"] = {"value": fwd_pe}

            # PEG 需要盈利增长率，当前只有单期一致预期无法可靠计算
            # 用 revenue beat% 作为增长方向参考，但不输出精确 PEG 数值
            rev_consensus = consensus.get("revenue", {})
            rev_growth_hint = ""
            if rev_consensus:
                rev_actual = rev_consensus.get("actual", 0)
                rev_est = rev_consensus.get("estimate", 0)
                if rev_est > 0:
                    rev_beat_pct = round((rev_actual - rev_est) / rev_est * 100, 1)
                    if rev_beat_pct > 5:
                        rev_growth_hint = "，营收增长强劲"
                    elif rev_beat_pct > 0:
                        rev_growth_hint = "，营收小幅增长"
                    elif rev_beat_pct > -5:
                        rev_growth_hint = "，营收基本持平"
                    else:
                        rev_growth_hint = "，营收下滑"

            peg_desc = f"Forward PE≈{fwd_pe}{rev_growth_hint}（需多期数据计算 PEG）"

            research_inputs["VL-002"] = {
                "label": "Forward PE (Est.)",
                "claim": f"Forward PE≈{fwd_pe} (基于年化 EPS={annual_eps:.2f}){rev_growth_hint}",
                "assessment": (
                    "Undervalued" if fwd_pe < 15
                    else "Fair" if fwd_pe < 25
                    else "Expensive" if fwd_pe < 40
                    else "Very Expensive"
                ),
            }

    # ---- PS ----
    ps = val.get("ps", {})
    if ps and ps.get("current"):
        signals["ps"] = {
            "current": ps["current"],
            "high": ps.get("high"),
            "low": ps.get("low"),
        }

    # ---- 综合判断 ----
    if pe:
        pe_v = pe.get("current")
        if pe_v and pe_v < 15:
            signals["description"] = "估值偏低"
        elif pe_v and pe_v < 25:
            signals["description"] = "估值合理"
        elif pe_v and pe_v < 40:
            signals["description"] = "估值偏高"
        elif pe_v:
            signals["description"] = "估值很高"
    else:
        signals["description"] = "估值数据不足"

    return {
        "signals": signals,
        "research_inputs": research_inputs,
    }


def _parse_percentile(desc: str) -> Optional[float]:
    """从 PE desc 文本中提取百分位。例: 'cheaper than 42.15% of the time'"""
    import re
    if not desc:
        return None
    m = re.search(r"cheaper than\s+([\d.]+)%", desc)
    if m:
        return float(m.group(1))
    return None


def _assess_pe(pe_current: Optional[float], percentile: Optional[float]) -> Dict:
    if pe_current is None:
        return {"level": "unknown", "description_zh": "PE 数据不可用"}

    if pe_current < 0:
        return {"level": "negative", "description_zh": "PE 为负值，公司亏损"}

    if pe_current < 15:
        return {"level": "low", "description_zh": f"PE={pe_current}，处于较低水平"}
    elif pe_current < 25:
        return {"level": "moderate", "description_zh": f"PE={pe_current}，估值合理"}
    elif pe_current < 40:
        return {"level": "high", "description_zh": f"PE={pe_current}，估值偏高"}
    else:
        return {"level": "very_high", "description_zh": f"PE={pe_current}，估值极高"}
