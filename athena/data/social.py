"""社交媒体数据 Provider — Longbridge 社区话题。

通过 ContentContext.topics 获取 LongPort 社区讨论。
"""

import concurrent.futures
import logging
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_social_lock = Lock()
_social_ctx = None
_social_available: Optional[bool] = None


def _init_social():
    global _social_ctx, _social_available
    if _social_available is not None:
        return
    with _social_lock:
        if _social_available is not None:
            return

        def _do_init():
            from longbridge.openapi import Config, ContentContext
            return ContentContext(Config.from_apikey_env())

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_do_init)
                _social_ctx = future.result(timeout=5)
                _social_available = True
                logger.info("ContentContext (社区) 初始化成功")
        except Exception as e:
            _social_available = False
            logger.warning(f"ContentContext 不可用: {e}")


def fetch_community_topics(symbol: str) -> Optional[List[Dict[str, Any]]]:
    """获取 LongPort 社区讨论话题。"""
    _init_social()
    if not _social_available:
        return None
    try:
        raw = _social_ctx.topics(f"{symbol}.US")
        return [
            {"id": t.id, "title": t.title or t.description,
             "description": t.description, "comments": t.comments_count,
             "likes": t.likes_count, "shares": t.shares_count,
             "published_at": t.published_at, "url": t.url}
            for t in (raw or [])
        ]
    except Exception as e:
        logger.debug(f"社区话题获取失败 {symbol}: {e}")
        return None
