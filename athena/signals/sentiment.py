"""情绪信号模块。

从新闻标题关键词判断市场情绪方向。
在没有专用社交数据源的情况下，用新闻作为情绪 proxy。
"""

from typing import Any, Dict, List, Optional

# 正/负面情绪关键词
POSITIVE_KW = [
    "beat", "超预期", "上调", "upgrade", "增长", "创新高", "突破",
    "launch", "推出", "合作", "partnership", "订单", "contract",
    "buyback", "回购", "dividend", "分红", "expansion", "扩张",
    "approval", "获批", "award", "获奖", "领先",
]
NEGATIVE_KW = [
    "miss", "低于预期", "下调", "downgrade", "下滑", "下跌", "暴跌",
    "lawsuit", "诉讼", "罚款", "fine", "调查", "investigation",
    "delay", "延迟", "推迟", "召回", "recall", "裁员", "layoff",
    "shortage", "短缺", "warning", "警告", "risk", "风险",
    "crash", "崩盘", "collapse", "破产",
]


def compute_sentiment_signals(
    news_list: Optional[List[Dict[str, Any]]],
) -> Dict:
    """从新闻标题分析情绪。

    Returns:
        {"signals": {...}, "research_inputs": {...}}
    """
    if not news_list:
        return {
            "signals": {"available": False, "description": "情绪数据不可用"},
            "research_inputs": {"SE-001": {"label": "News Sentiment", "claim": "无数据", "assessment": "N/A"}},
        }

    positive = 0
    negative = 0
    total = 0

    for article in news_list[:20]:
        title = (article.get("title", "") + " " + article.get("description", "")).lower()
        total += 1
        pos_hit = any(kw.lower() in title for kw in POSITIVE_KW)
        neg_hit = any(kw.lower() in title for kw in NEGATIVE_KW)

        if pos_hit and not neg_hit:
            positive += 1
        elif neg_hit and not pos_hit:
            negative += 1
        # both or neither = neutral

    if total == 0:
        return {
            "signals": {"available": False, "description": "无新闻数据"},
            "research_inputs": {"SE-001": {"label": "News Sentiment", "claim": "无数据", "assessment": "N/A"}},
        }

    pos_ratio = round(positive / total * 100, 1)
    neg_ratio = round(negative / total * 100, 1)
    neutral_ratio = round(100 - pos_ratio - neg_ratio, 1)

    if pos_ratio > neg_ratio * 1.5:
        direction = "positive"
        desc = f"情绪偏正面 (正面 {pos_ratio}% vs 负面 {neg_ratio}%)"
    elif neg_ratio > pos_ratio * 1.5:
        direction = "negative"
        desc = f"情绪偏负面 (负面 {neg_ratio}% vs 正面 {pos_ratio}%)"
    else:
        direction = "neutral"
        desc = f"情绪中性 (正面 {pos_ratio}%, 负面 {neg_ratio}%)"

    signals = {
        "available": True,
        "total_articles": total,
        "positive_pct": pos_ratio,
        "negative_pct": neg_ratio,
        "neutral_pct": neutral_ratio,
        "direction": direction,
        "description": desc,
    }

    research_inputs = {
        "SE-001": {
            "label": "News Sentiment",
            "claim": desc,
            "assessment": "Bullish" if direction == "positive" else "Bearish" if direction == "negative" else "Neutral",
        },
    }

    return {"signals": signals, "research_inputs": research_inputs}
