"""Longbridge 资金流 Provider — 经纪商持仓数据。

通过 MarketContext 获取 broker holdings 等资金流信息。
"""

import concurrent.futures
import logging
from threading import Lock
from typing import Any, Dict, List, Optional

from athena.config import settings

logger = logging.getLogger(__name__)

_flow_lock = Lock()
_flow_ctx = None
_flow_available: Optional[bool] = None


def _init_flow():
    global _flow_ctx, _flow_available
    if _flow_available is not None:
        return
    with _flow_lock:
        if _flow_available is not None:
            return

        def _do_init():
            from longbridge.openapi import Config, MarketContext
            return MarketContext(Config.from_apikey_env())

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_do_init)
                _flow_ctx = future.result(timeout=5)
                _flow_available = True
                logger.info("Longbridge MarketContext 初始化成功")
        except Exception as e:
            _flow_available = False
            logger.warning(f"MarketContext 不可用: {e}")


def fetch_broker_holdings(symbol: str) -> Optional[Dict[str, Any]]:
    """获取经纪商持仓概览。"""
    _init_flow()
    if not _flow_available:
        return None
    try:
        symbol_full = f"{symbol}.US"
        h = _flow_ctx.broker_holding(symbol_full)
        if not h:
            return None
        return {
            "total_brokers": getattr(h, "total_brokers", None),
            "buy_count": getattr(h, "buy_count", None),
            "sell_count": getattr(h, "sell_count", None),
            "net_flow": getattr(h, "net_flow", None),
        }
    except Exception as e:
        logger.debug(f"经纪商持仓获取失败 {symbol}: {e}")
        return None
