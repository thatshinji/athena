"""资金流信号模块。

从经纪商持仓数据提取资金流信号。
"""

from typing import Any, Dict, Optional


def compute_flow_signals(
    broker_holdings: Optional[Dict[str, Any]],
) -> Dict:
    """从经纪商持仓生成资金流信号。

    Returns:
        {"signals": {...}, "research_inputs": {...}}
    """
    if not broker_holdings:
        return {
            "signals": {"available": False, "description": "资金流数据不可用"},
            "research_inputs": {
                "FL-001": {"label": "Broker Flow", "claim": "无数据", "assessment": "N/A"},
            },
        }

    total = broker_holdings.get("total_brokers", 0) or 0
    buy = broker_holdings.get("buy_count", 0) or 0
    sell = broker_holdings.get("sell_count", 0) or 0
    net_flow = broker_holdings.get("net_flow")

    buy_ratio = round(buy / total * 100, 1) if total > 0 else 0
    sell_ratio = round(sell / total * 100, 1) if total > 0 else 0

    if buy_ratio > sell_ratio * 1.5:
        direction = "net_inflow"
        desc = f"经纪商净流入 (买入 {buy_ratio}% vs 卖出 {sell_ratio}%)"
    elif sell_ratio > buy_ratio * 1.5:
        direction = "net_outflow"
        desc = f"经纪商净流出 (卖出 {sell_ratio}% vs 买入 {buy_ratio}%)"
    else:
        direction = "balanced"
        desc = f"经纪商买卖均衡 (买{buy_ratio}% 卖{sell_ratio}%)"

    signals = {
        "available": True,
        "total_brokers": total,
        "buy_ratio": buy_ratio,
        "sell_ratio": sell_ratio,
        "direction": direction,
        "description": desc,
    }

    research_inputs = {
        "FL-001": {
            "label": "Broker Flow",
            "claim": desc,
            "assessment": (
                "Inflow" if direction == "net_inflow"
                else "Outflow" if direction == "net_outflow"
                else "Neutral"
            ),
        },
    }

    return {"signals": signals, "research_inputs": research_inputs}
