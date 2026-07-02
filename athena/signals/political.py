"""政治交易信号模块。

从 Quiver 国会交易数据提取信号。
"""

from typing import Any, Dict, List, Optional


def compute_political_signals(
    political_trades: Optional[List[Dict[str, Any]]],
    insider_trades: Optional[List[Dict[str, Any]]] = None,
) -> Dict:
    pt = political_trades or []
    it = insider_trades or []

    signals = {"available": False}
    research_inputs = {}

    # ---- PL-001 Political Trading ----
    if pt:
        signals["available"] = True
        buys = sum(1 for t in pt if t.get("transaction", "").lower() in ("purchase", "buy"))
        sells = sum(1 for t in pt if t.get("transaction", "").lower() in ("sale", "sell"))
        total = len(pt)

        if buys > sells * 2:
            direction, desc = "net_buy", f"国会净买入 ({buys} 买 vs {sells} 卖, 共 {total} 笔)"
        elif sells > buys * 2:
            direction, desc = "net_sell", f"国会净卖出 ({sells} 卖 vs {buys} 买, 共 {total} 笔)"
        else:
            direction, desc = "mixed", f"国会交易 {total} 笔 (买 {buys} / 卖 {sells})"

        # 计算总金额
        amounts = []
        for t in pt:
            try:
                amounts.append(float(t.get("amount", 0)))
            except (ValueError, TypeError):
                pass
        total_amount = sum(amounts)

        signals["political"] = {
            "total": total, "buys": buys, "sells": sells,
            "direction": direction, "total_amount": total_amount,
        }

        research_inputs["PL-001"] = {
            "label": "Political Trades",
            "claim": desc + (f" (总额 ${total_amount:,.0f})" if total_amount > 0 else ""),
            "assessment": "Bullish" if direction == "net_buy" else "Bearish" if direction == "net_sell" else "Neutral",
        }

    # ---- FL-004 Insider Trading ----
    if it:
        signals["available"] = True
        buys = sum(1 for t in it if t.get("transaction", "").lower() in ("purchase", "buy"))
        sells = sum(1 for t in it if t.get("transaction", "").lower() in ("sale", "sell"))
        total = len(it)

        if buys > sells:
            direction, desc = "net_buy", f"内幕净买入 ({buys} 买 vs {sells} 卖)"
        elif sells > 0:
            direction, desc = "net_sell", f"内幕净卖出 ({sells} 卖 vs {buys} 买)"
        else:
            direction, desc = "none", "无近期内幕交易"

        signals["insider"] = {"total": total, "buys": buys, "sells": sells, "direction": direction}

        research_inputs["FL-004"] = {
            "label": "Insider Activity",
            "claim": desc,
            "assessment": "Bullish" if direction == "net_buy" else "Bearish" if direction == "net_sell" else "Neutral",
        }

    if not signals["available"]:
        signals["description"] = "政治/内幕数据不可用"
    else:
        parts = []
        if "political" in signals:
            parts.append(signals["political"]["direction"])
        if "insider" in signals:
            parts.append(f"insider_{signals['insider']['direction']}")
        signals["description"] = " / ".join(parts)

    return {"signals": signals, "research_inputs": research_inputs}
