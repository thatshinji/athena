"""Longbridge 内容 Provider — 新闻与社区数据。

通过 ContentContext 获取个股相关新闻。
"""

import concurrent.futures
import logging
from threading import Lock
from typing import Any, Dict, List, Optional

from athena.config import settings

logger = logging.getLogger(__name__)

_content_lock = Lock()
_content_ctx = None
_content_available: Optional[bool] = None


def _init_content():
    global _content_ctx, _content_available
    if _content_available is not None:
        return
    with _content_lock:
        if _content_available is not None:
            return

        def _do_init():
            from longbridge.openapi import Config, ContentContext
            return ContentContext(Config.from_apikey_env())

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_do_init)
                _content_ctx = future.result(timeout=5)
                _content_available = True
                logger.info("Longbridge ContentContext 初始化成功")
        except Exception as e:
            _content_available = False
            logger.warning(f"ContentContext 不可用: {e}")


def fetch_news(symbol: str) -> Optional[List[Dict[str, Any]]]:
    """获取个股新闻列表。"""
    _init_content()
    if not _content_available:
        return None
    try:
        symbol_full = f"{symbol}.US"
        raw = _content_ctx.news(symbol_full)
        return [
            {
                "id": n.id,
                "title": n.title,
                "description": n.description,
                "published_at": n.published_at,
                "url": n.url,
            }
            for n in (raw or [])
        ]
    except Exception as e:
        logger.debug(f"新闻获取失败 {symbol}: {e}")
        return None
