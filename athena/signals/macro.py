"""宏观/行业信号模块。

从 Longbridge industry_valuation 获取同行对比。
"""

from typing import Any, Dict, List, Optional


def compute_macro_signals(
    industry_data: Optional[List[Dict[str, Any]]],
    symbol_pe: Optional[float] = None,
) -> Dict:
    """从行业估值数据生成信号。

    Args:
        industry_data: industry_valuation 返回的 list
        symbol_pe: 该股票的 PE

    Returns:
        {"signals": {...}, "research_inputs": {...}}
    """
    if not industry_data or not symbol_pe:
        return {
            "signals": {"available": False, "description": "行业数据不可用"},
            "research_inputs": {"MA-001": {"label": "Industry Comparison", "claim": "无数据", "assessment": "N/A"}},
        }

    peers = []
    for item in industry_data:
        pe = getattr(item, "pe", None)
        name = getattr(item, "name", "?")
        symbol = getattr(item, "symbol", "?").replace(".US", "")
        if pe and float(pe) > 0:
            peers.append({"name": name, "symbol": symbol, "pe": round(float(pe), 1)})

    if len(peers) < 2:
        return {
            "signals": {"available": False, "description": "同行数据不足"},
            "research_inputs": {"MA-001": {"label": "Industry Comparison", "claim": "同行数据不足", "assessment": "N/A"}},
        }

    avg_pe = round(sum(p["pe"] for p in peers) / len(peers), 1)
    median_pe = sorted(p["pe"] for p in peers)[len(peers) // 2]

    if symbol_pe < median_pe * 0.8:
        position = "undervalued"
        desc = f"相对行业折价 (PE {symbol_pe} vs 中位 {median_pe})"
    elif symbol_pe > median_pe * 1.2:
        position = "premium"
        desc = f"相对行业溢价 (PE {symbol_pe} vs 中位 {median_pe})"
    else:
        position = "fair"
        desc = f"估值与行业持平 (PE {symbol_pe} vs 中位 {median_pe})"

    signals = {
        "available": True,
        "peer_count": len(peers),
        "avg_pe": avg_pe,
        "median_pe": median_pe,
        "position": position,
        "description": desc,
    }

    research_inputs = {
        "MA-001": {
            "label": "Industry Comparison",
            "claim": f"{len(peers)} 家同行: 平均 PE={avg_pe}, 中位 PE={median_pe}. {desc}",
            "assessment": "Undervalued" if position == "undervalued" else "Premium" if position == "premium" else "Fair",
        },
    }

    return {"signals": signals, "research_inputs": research_inputs}
