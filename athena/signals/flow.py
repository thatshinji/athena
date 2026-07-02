"""资金流信号模块。

从基金持仓、大股东、经纪商数据提取资金流信号。
"""

from typing import Any, Dict, List, Optional


def compute_flow_signals(
    broker_holdings: Optional[Dict[str, Any]],
    fund_data: Optional[Dict[str, Any]] = None,
) -> Dict:
    broker = broker_holdings or {}
    fund_holders = (fund_data or {}).get("fund_holders", [])
    shareholders = (fund_data or {}).get("shareholders", [])

    signals = {"available": False}
    research_inputs = {}

    # ---- FL-001 Broker Flow ----
    total = broker.get("total_brokers", 0) or 0
    buy = broker.get("buy_count", 0) or 0
    sell = broker.get("sell_count", 0) or 0

    if total > 0:
        signals["available"] = True
        buy_ratio = round(buy / total * 100, 1)
        sell_ratio = round(sell / total * 100, 1)
        if buy_ratio > sell_ratio * 1.5:
            direction, desc = "net_inflow", f"经纪商净流入 (买{buy_ratio}% 卖{sell_ratio}%)"
        elif sell_ratio > buy_ratio * 1.5:
            direction, desc = "net_outflow", f"经纪商净流出 (卖{sell_ratio}% 买{buy_ratio}%)"
        else:
            direction, desc = "balanced", f"经纪商均衡 (买{buy_ratio}% 卖{sell_ratio}%)"
        signals["broker"] = {"buy_ratio": buy_ratio, "sell_ratio": sell_ratio, "direction": direction}
        research_inputs["FL-001"] = {"label": "Broker Flow", "claim": desc,
            "assessment": "Inflow" if direction == "net_inflow" else "Outflow" if direction == "net_outflow" else "Neutral"}

    # ---- FL-002 ETF/Fund Holdings ----
    if fund_holders:
        signals["available"] = True
        # 计算平均持仓比例和近期变化
        ratios = [h["position_ratio"] for h in fund_holders if h.get("position_ratio")]
        avg_ratio = round(sum(ratios) / len(ratios), 1) if ratios else 0
        top5 = sorted(fund_holders, key=lambda x: x.get("position_ratio", 0), reverse=True)[:5]
        top_names = ", ".join(h["name"][:15] for h in top5[:3])

        signals["etf_funds"] = {"count": len(fund_holders), "avg_position_ratio": avg_ratio, "top_holders": top_names}
        research_inputs["FL-002"] = {"label": "ETF/Fund Holdings",
            "claim": f"{len(fund_holders)} 只基金持仓，平均权重 {avg_ratio}%，前三大: {top_names}",
            "assessment": "High" if avg_ratio > 5 else "Moderate" if avg_ratio > 1 else "Low"}

    # ---- FL-003 Institutional Activity ----
    if shareholders:
        signals["available"] = True
        total_pct = round(sum(h["pct"] for h in shareholders), 1)
        # 近期增减持趋势
        changers = [h for h in shareholders if h.get("changed") != 0]
        if changers:
            buyers = sum(1 for h in changers if h["changed"] > 0)
            sellers = sum(1 for h in changers if h["changed"] < 0)
            net_shares = sum(h["changed"] for h in changers)
            if net_shares > 1e6:
                trend = "accumulating"
                desc = f"机构净增持 ({buyers} 增持 vs {sellers} 减持)"
            elif net_shares < -1e6:
                trend = "distributing"
                desc = f"机构净减持 ({sellers} 减持 vs {buyers} 增持)"
            else:
                trend = "neutral"
                desc = f"机构持仓稳定 ({buyers} 增持 {sellers} 减持)"
        else:
            trend, desc = "stable", "机构持仓无变化"

        signals["institutional"] = {"total_pct": total_pct, "trend": trend}
        research_inputs["FL-003"] = {"label": "Institutional Activity",
            "claim": f"机构持股 {total_pct}%，{desc}",
            "assessment": "Bullish" if trend == "accumulating" else "Bearish" if trend == "distributing" else "Neutral"}

    if not signals["available"]:
        signals["description"] = "资金流数据不可用"
    else:
        parts = []
        if "broker" in signals:
            parts.append(signals["broker"]["direction"])
        if "institutional" in signals:
            parts.append(signals["institutional"]["trend"])
        signals["description"] = " / ".join(parts) if parts else "资金流数据不足"

    return {"signals": signals, "research_inputs": research_inputs}
