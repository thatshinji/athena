"""情绪信号模块。

结合新闻标题 + LongPort 社区讨论计算情绪。
"""

from typing import Any, Dict, List, Optional

POSITIVE_KW = [
    "beat", "超预期", "上调", "upgrade", "增长", "创新高", "突破",
    "launch", "推出", "合作", "partnership", "订单", "contract",
    "buyback", "回购", "dividend", "分红", "expansion", "扩张",
    "approval", "获批", "award", "获奖", "领先", "bullish",
]
NEGATIVE_KW = [
    "miss", "低于预期", "下调", "downgrade", "下滑", "下跌", "暴跌",
    "lawsuit", "诉讼", "罚款", "fine", "调查", "investigation",
    "delay", "延迟", "推迟", "召回", "recall", "裁员", "layoff",
    "shortage", "短缺", "warning", "警告", "risk", "风险",
    "crash", "崩盘", "collapse", "破产", "bearish",
]


def _analyze_texts(items: List[Dict], text_fields: List[str]) -> Dict:
    """通用文本情绪分析。"""
    positive = 0
    negative = 0
    total = 0
    for item in items[:30]:
        text = " ".join(item.get(f, "") for f in text_fields).lower()
        if not text.strip():
            continue
        total += 1
        pos_hit = any(kw in text for kw in POSITIVE_KW)
        neg_hit = any(kw in text for kw in NEGATIVE_KW)
        if pos_hit and not neg_hit:
            positive += 1
        elif neg_hit and not pos_hit:
            negative += 1
    if total == 0:
        return {"available": False, "total": 0}
    pos_ratio = round(positive / total * 100, 1)
    neg_ratio = round(negative / total * 100, 1)
    if pos_ratio > neg_ratio * 1.5:
        direction = "positive"
    elif neg_ratio > pos_ratio * 1.5:
        direction = "negative"
    else:
        direction = "neutral"
    return {"available": True, "total": total, "positive_pct": pos_ratio,
            "negative_pct": neg_ratio, "direction": direction}


def compute_sentiment_signals(
    news_list: Optional[List[Dict[str, Any]]],
    community_topics: Optional[List[Dict[str, Any]]] = None,
) -> Dict:
    signals = {"available": False}
    research_inputs = {}

    # ---- SE-001 News Sentiment ----
    if news_list:
        ns = _analyze_texts(news_list, ["title", "description"])
        if ns["available"]:
            signals["available"] = True
            signals["news"] = ns
            desc = f"新闻情绪{'偏正面' if ns['direction']=='positive' else '偏负面' if ns['direction']=='negative' else '中性'}"
            desc += f" (正面 {ns['positive_pct']}% vs 负面 {ns['negative_pct']}%)"
            research_inputs["SE-001"] = {"label": "News Sentiment", "claim": desc,
                "assessment": "Bullish" if ns["direction"] == "positive" else "Bearish" if ns["direction"] == "negative" else "Neutral"}

    # ---- SE-002 Community Sentiment (LongPort) ----
    if community_topics:
        cs = _analyze_texts(community_topics, ["title", "description"])
        if cs["available"]:
            signals["available"] = True
            # 计算互动指标
            total_likes = sum(t.get("likes", 0) or 0 for t in community_topics)
            total_comments = sum(t.get("comments", 0) or 0 for t in community_topics)
            engagement = "high" if total_likes + total_comments > 100 else "moderate" if total_likes + total_comments > 10 else "low"

            desc = f"社区讨论 {cs['total']} 条 (👍{total_likes} 💬{total_comments}), "
            desc += f"情绪{'偏正面' if cs['direction']=='positive' else '偏负面' if cs['direction']=='negative' else '中性'}"
            signals["community"] = {"topic_count": cs["total"], "likes": total_likes,
                                     "comments": total_comments, "engagement": engagement,
                                     "direction": cs["direction"]}
            research_inputs["SE-002"] = {"label": "Community Sentiment", "claim": desc,
                "assessment": "Bullish" if cs["direction"] == "positive" else "Bearish" if cs["direction"] == "negative" else "Neutral"}

    if not signals["available"]:
        signals["description"] = "情绪数据不可用"
    else:
        parts = []
        if "news" in signals:
            parts.append(f"news_{signals['news']['direction']}")
        if "community" in signals:
            parts.append(f"community_{signals['community']['direction']}")
        signals["description"] = " / ".join(parts)

    return {"signals": signals, "research_inputs": research_inputs}
