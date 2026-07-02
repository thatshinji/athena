"""基本面信号模块。

从 Longbridge 数据提取：
- BQ-001 Revenue / BQ-001a Revenue YoY
- BQ-002 Gross Margin / BQ-003 Net Margin / BQ-004 ROE
- BQ-005 EPS YoY Growth
- GR-004 Estimate Revision (EPS 一致预期)
- GR-005 Analyst Consensus (分析师共识)
"""

from typing import Any, Dict, Optional


def compute_fundamental_signals(fund_data: Optional[Dict[str, Any]], latest_price: float = 0) -> Dict:
    if not fund_data:
        return {
            "signals": {"available": False, "description": "基本面数据不可用"},
            "research_inputs": {"BQ-001": {"label": "Revenue", "claim": "无数据", "assessment": "N/A"}},
        }

    consensus = fund_data.get("consensus", {})
    fin = fund_data.get("financial_report", {})

    signals = {"available": True}
    research_inputs = {}

    # ---- BQ-001 Revenue Consensus ----
    rev = consensus.get("revenue", {})
    if rev:
        actual_b, est_b = rev.get("actual", 0), (rev.get("estimate", 0) or 0)
        beat_pct = round((actual_b - est_b) / est_b * 100, 1) if est_b > 0 else 0
        signals["revenue"] = {"actual_billion": round(actual_b / 1e9, 1),
                              "estimate_billion": round(est_b / 1e9, 1), "beat_pct": beat_pct,
                              "status": rev.get("comp_desc", "N/A")}
        research_inputs["BQ-001"] = {
            "label": "Revenue", "claim": f"营收=${actual_b/1e9:.1f}B vs 预期=${est_b/1e9:.1f}B ({'+' if beat_pct>0 else ''}{beat_pct}%)",
            "assessment": "Beat" if beat_pct > 0 else "Miss" if beat_pct < 0 else "Inline",
        }

    # ---- Revenue YoY ----
    rev_fin = fin.get("revenue", {})
    if rev_fin.get("latest_yoy") is not None:
        signals["revenue_yoy"] = round(rev_fin["latest_yoy"], 1)
        research_inputs["BQ-001a"] = {
            "label": "Revenue YoY", "claim": f"营收同比增速 {rev_fin['latest_yoy']:.1f}% ({rev_fin.get('latest_period','')})",
            "assessment": "Strong" if rev_fin["latest_yoy"] > 15 else "Moderate" if rev_fin["latest_yoy"] > 5 else "Weak" if rev_fin["latest_yoy"] > 0 else "Declining",
        }

    # ---- Gross Margin ----
    gm = fin.get("gross_margin", {})
    if gm.get("latest_value") is not None:
        signals["gross_margin"] = round(gm["latest_value"], 2)
        gm_yoy = gm.get("latest_yoy")
        desc = f"毛利率 {gm['latest_value']:.1f}%"
        if gm_yoy is not None:
            desc += f", 同比 {'+'+str(gm_yoy)+'pp' if gm_yoy > 0 else str(gm_yoy)+'pp'}"
        research_inputs["BQ-002"] = {"label": "Gross Margin", "claim": desc,
            "assessment": "Expanding" if (gm_yoy and gm_yoy > 0.5) else "Stable" if (gm_yoy and gm_yoy > -0.5) else "Contracting"}

    # ---- Net Margin ----
    nm = fin.get("net_margin", {})
    if nm.get("latest_value") is not None:
        signals["net_margin"] = round(nm["latest_value"], 2)
        research_inputs["BQ-003"] = {"label": "Net Margin", "claim": f"净利率 {nm['latest_value']:.1f}%",
            "assessment": "Excellent" if nm["latest_value"] > 20 else "Good" if nm["latest_value"] > 10 else "Thin"}

    # ---- ROE ----
    roe = fin.get("roe", {})
    if roe.get("latest_value") is not None:
        signals["roe"] = round(roe["latest_value"], 2)
        research_inputs["BQ-004"] = {"label": "ROE", "claim": f"ROE {roe['latest_value']:.1f}%",
            "assessment": "Excellent" if roe["latest_value"] > 20 else "Good" if roe["latest_value"] > 10 else "Low"}

    # ---- EPS YoY ----
    eps_fin = fin.get("eps", {})
    if eps_fin.get("latest_yoy") is not None:
        signals["eps_yoy"] = round(eps_fin["latest_yoy"], 1)
        research_inputs["BQ-005"] = {"label": "EPS YoY Growth", "claim": f"EPS 同比增速 {eps_fin['latest_yoy']:.1f}%",
            "assessment": "Strong" if eps_fin["latest_yoy"] > 15 else "Moderate" if eps_fin["latest_yoy"] > 5 else "Weak"}

    # ---- GR-004 Estimate Revision ----
    eps = consensus.get("normalized_eps", {}) or consensus.get("eps", {})
    if eps:
        actual_eps, est_eps = eps.get("actual", 0), (eps.get("estimate", 0) or 0)
        eps_beat = round((actual_eps - est_eps) / abs(est_eps) * 100, 1) if est_eps != 0 else 0
        signals["eps"] = {"actual": actual_eps, "estimate": est_eps, "beat_pct": eps_beat, "status": eps.get("comp_desc", "N/A")}
        research_inputs["GR-004"] = {"label": "Estimate Revision",
            "claim": f"EPS 实际=${actual_eps:.2f} vs 预期=${est_eps:.2f} ({'+' if eps_beat>0 else ''}{eps_beat}%)",
            "assessment": "Upward Revision" if eps_beat > 3 else "Slight Beat" if eps_beat > 0 else "Miss"}

    # ---- GR-005 Analyst Consensus ----
    ratings = fund_data.get("ratings", [])
    if ratings:
        target_prices = [r["target_price"] for r in ratings if r.get("target_price")]
        if target_prices and latest_price > 0:
            avg_target = round(sum(target_prices) / len(target_prices), 2)
            upside = round((avg_target / latest_price - 1) * 100, 1)
            signals["analyst_target"] = avg_target
            signals["analyst_upside_pct"] = upside
            research_inputs["GR-005"] = {"label": "Analyst Consensus",
                "claim": f"{len(ratings)} 位分析师，平均目标价 ${avg_target:.1f} ({'+' if upside>0 else ''}{upside}%)",
                "assessment": "Bullish" if upside > 15 else "Neutral" if upside > 0 else "Bearish"}

    # ---- BQ-006 Free Cash Flow ----
    fcf = fin.get("free_cash_flow", {})
    if fcf.get("latest_value") is not None:
        signals["fcf_billion"] = round(fcf["latest_value"] / 1e9, 1)
        research_inputs["BQ-006"] = {"label": "Free Cash Flow",
            "claim": f"自由现金流 ${fcf['latest_value']/1e9:.1f}B",
            "assessment": "Strong" if fcf["latest_value"] > 1e9 else "Positive" if fcf["latest_value"] > 0 else "Negative"}

    # ---- BQ-007 Net Debt / Cash Position ----
    nd = fin.get("net_debt", {})
    if nd.get("latest_value") is not None:
        signals["net_debt_billion"] = round(nd["latest_value"] / 1e9, 1)
        if nd["latest_value"] < 0:
            desc = f"净现金 ${abs(nd['latest_value'])/1e9:.1f}B（财务健康）"
            assessment = "Net Cash"
        elif nd["latest_value"] < 1e10:
            desc = f"净债务 ${nd['latest_value']/1e9:.1f}B（可控）"
            assessment = "Manageable"
        else:
            desc = f"净债务 ${nd['latest_value']/1e9:.1f}B（偏高）"
            assessment = "High"
        research_inputs["BQ-007"] = {"label": "Debt Level", "claim": desc, "assessment": assessment}

    # ---- BQ-008 Operating Cash Flow ----
    ocf = fin.get("operating_cash_flow", {})
    if ocf.get("latest_value") is not None:
        signals["ocf_billion"] = round(ocf["latest_value"] / 1e9, 1)
        # FCF yield = FCF / Market Cap (approximate with price)
        if latest_price > 0 and fcf.get("latest_value"):
            shares_outstanding = fin.get("eps", {}).get("latest_value")
            # Estimate market cap from PE ratio
            pe = fin.get("roe", {})  # placeholder — use trailing PE from valuation instead
        research_inputs["BQ-008"] = {"label": "Op. Cash Flow",
            "claim": f"经营现金流 ${ocf['latest_value']/1e9:.1f}B",
            "assessment": "Strong" if ocf["latest_value"] > 5e9 else "Positive"}

    # 综合
    strengths = sum(1 for v in [signals.get("revenue_yoy", 0), signals.get("eps_yoy", 0)] if v and v > 5)
    margins_good = (gm.get("latest_value", 0) or 0) > (nm.get("latest_value", 0) or 0) > 10 if gm and nm else False
    if strengths >= 2 and margins_good:
        signals["description"] = "基本面强劲：营收/盈利双增长，利润率健康"
    elif strengths >= 1:
        signals["description"] = "基本面稳健"
    else:
        signals["description"] = "基本面一般或数据不足"

    return {"signals": signals, "research_inputs": research_inputs}
