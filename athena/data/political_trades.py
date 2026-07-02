"""政治人物交易 Provider — Quiver Quantitative API。

免费 tier 支持国会交易 + 内幕交易数据。
"""

import logging
from typing import Any, Dict, List, Optional

from athena.config import settings

logger = logging.getLogger(__name__)
_quiver = None


def _get_quiver():
    global _quiver
    if _quiver is not None:
        return _quiver
    if not settings.quiver_configured:
        return None
    try:
        import quiverquant
        _quiver = quiverquant.quiver(settings.quiver_api_key)
        logger.info("Quiver API 初始化成功")
    except Exception as e:
        logger.warning(f"Quiver API 不可用: {e}")
        _quiver = False
    return _quiver if _quiver else None


def fetch_political_trades(symbol: str) -> Optional[List[Dict[str, Any]]]:
    """获取国会成员交易记录。"""
    q = _get_quiver()
    if not q:
        return None
    try:
        df = q.congress_trading(symbol)
        if df is None or df.empty:
            return None
        return [
            {"representative": r.get("Representative", ""),
             "transaction": r.get("Transaction", ""),
             "date": str(r.get("TransactionDate", "")),
             "amount": r.get("Amount", "0"),
             "party": r.get("Party", ""),
             "house": r.get("House", "")}
            for _, r in df.iterrows()
        ]
    except Exception as e:
        logger.debug(f"政治交易获取失败 {symbol}: {e}")
        return None


def fetch_insider_trades(symbol: str) -> Optional[List[Dict[str, Any]]]:
    """获取内幕交易记录。"""
    q = _get_quiver()
    if not q:
        return None
    try:
        df = q.insiders(symbol)
        if df is None or df.empty:
            return None
        return [
            {"name": r.get("Name", r.get("Insider", "")),
             "transaction": r.get("Transaction", ""),
             "shares": r.get("Shares", 0),
             "date": str(r.get("Date", r.get("FilingDate", ""))),
             "price": r.get("Price", 0)}
            for _, r in df.iterrows()
        ]
    except Exception as e:
        logger.debug(f"内幕交易获取失败 {symbol}: {e}")
        return None
