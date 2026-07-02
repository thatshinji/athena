"""供应链信号模块。

监测产业链上下游：供应商股价联动 + 成本变化 + 行业瓶颈。
"""

from typing import Any, Dict, List, Optional

# 已知供应链映射（主要供应商/客户/同行）
SUPPLY_CHAIN_MAP = {
    "AAPL": {
        "suppliers": ["TSM", "QRVO", "SWKS", "AVGO", "STM", "CRUS", "LRCX", "AMAT"],
        "competitors": ["SMSN", "XIACF"],
        "description": "消费电子供应链：芯片代工/射频/存储/设备",
    },
    "NVDA": {
        "suppliers": ["TSM", "AMD", "INTC", "ASML", "LRCX", "AMAT"],
        "competitors": ["AMD", "INTC"],
        "description": "AI/GPU 供应链：晶圆代工/封装/光刻",
    },
    "TSLA": {
        "suppliers": ["CATL", "BYDDF", "LGCLF", "ALB", "SQM", "F", "GM"],
        "competitors": ["F", "GM", "RIVN", "LCID"],
        "description": "电动车供应链：电池/锂矿/制造",
    },
}

# 供应链/成本相关关键词
SUPPLY_KW = {
    "chip_shortage": ["芯片短缺", "chip shortage", "晶圆", "foundry", "产能不足"],
    "cost_pressure": ["涨价", "提价", "price increase", "成本上升", "cost rising", "margin pressure"],
    "cost_relief": ["降价", "price cut", "成本下降", "cost reduction", "毛利率改善"],
    "logistics": ["物流", "运费", "港口", "shipping", "freight", "supply chain disruption"],
    "tariff": ["关税", "tariff", "trade war", "制裁", "sanction", "export control"],
    "labor": ["人工成本", "劳动力", "罢工", "strike", "工资", "wage"],
}


def compute_supply_chain_signals(
    symbol: str,
    news_list: Optional[List[Dict[str, Any]]],
    supplier_prices: Optional[Dict[str, float]] = None,
) -> Dict:
    """生成供应链信号。

    Args:
        symbol: 股票代码
        news_list: 新闻列表
        supplier_prices: 供应商价格变化百分比 {ticker: pct_change}

    Returns:
        {"signals": {...}, "research_inputs": {...}}
    """
    chain_info = SUPPLY_CHAIN_MAP.get(symbol.upper(), {"suppliers": ["TSM"], "competitors": [], "description": "通用"})
    signals = {"available": False}
    research_inputs = {}

    # ---- SC-001 Supplier Index ----
    if supplier_prices:
        changes = list(supplier_prices.values())
        if changes:
            avg_change = round(sum(changes) / len(changes), 1)
            up = sum(1 for c in changes if c > 0)
            down = sum(1 for c in changes if c < 0)
            direction = "bullish" if avg_change > 1 else "bearish" if avg_change < -1 else "neutral"
            desc = f"{len(changes)}家供应商: 平均{'+' if avg_change>0 else ''}{avg_change}% ({up}涨{down}跌)"
            signals["available"] = True
            signals["supplier_index"] = {"avg_change": avg_change, "direction": direction, "count": len(changes)}
            research_inputs["SC-001"] = {
                "label": "Supplier Index",
                "claim": desc,
                "assessment": "Bullish" if direction == "bullish" else "Bearish" if direction == "bearish" else "Neutral",
            }

    # ---- SC-002 Supply Chain News ----
    if news_list:
        hits = {cat: 0 for cat in SUPPLY_KW}
        for article in news_list[:30]:
            text = (article.get("title", "") + " " + article.get("description", "")).lower()
            for cat, keywords in SUPPLY_KW.items():
                if any(kw.lower() in text for kw in keywords):
                    hits[cat] += 1

        total_hits = sum(hits.values())
        if total_hits > 0:
            signals["available"] = True
            top = sorted(hits.items(), key=lambda x: -x[1])[:3]
            top_str = ", ".join(f"{c}({n})" for c, n in top if n > 0)
            risk_level = "high" if total_hits > 10 else "medium" if total_hits > 5 else "low"
            signals["supply_news"] = {"hits": total_hits, "top_categories": top, "risk_level": risk_level}
            research_inputs["SC-002"] = {
                "label": "Supply Chain News",
                "claim": f"供应链相关新闻 {total_hits} 条: {top_str}",
                "assessment": "Risk" if risk_level == "high" else "Caution" if risk_level == "medium" else "Normal",
            }

    if not signals["available"]:
        signals["description"] = "供应链数据不可用"
    else:
        parts = []
        if "supplier_index" in signals:
            parts.append(f"供应商_{signals['supplier_index']['direction']}")
        if "supply_news" in signals:
            parts.append(f"新闻{signals['supply_news']['hits']}条")
        signals["description"] = " / ".join(parts)
        signals["chain_info"] = chain_info

    return {"signals": signals, "research_inputs": research_inputs}
