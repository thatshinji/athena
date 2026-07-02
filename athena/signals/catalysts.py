"""催化剂信号模块。

从新闻和一致预期中检测催化剂事件。
"""

import re
from typing import Any, Dict, List, Optional


# 催化剂关键词映射
CATALYST_KEYWORDS = {
    "earnings": ["财报", "earnings", "季度", "营收", "利润", "EPS", "指引", "guidance"],
    "product": ["发布", "launch", "推出", "新品", "iPhone", "chip", "芯片", "model"],
    "ai_data_center": ["AI", "人工智能", "数据中心", "data center", "GPU", "NVIDIA"],
    "regulation": ["监管", "调查", "罚款", "反垄断", "regulation", "antitrust"],
    "ma": ["收购", "并购", "合并", "acquisition", "merger", "buy"],
    "partnership": ["合作", "partnership", "协议", "deal", "contract"],
    "supply_chain": ["供应链", "supply chain", "短缺", "shortage"],
}


def compute_catalyst_signals(
    news_list: Optional[List[Dict[str, Any]]],
    consensus: Optional[Dict[str, Any]],
) -> Dict:
    """从新闻和财报数据检测催化剂。

    Returns:
        {"signals": {...}, "research_inputs": {...}}
    """
    catalysts: List[Dict] = []
    news_count = 0

    # 扫描新闻标题
    if news_list:
        news_count = len(news_list)
        for article in news_list[:20]:  # 最近 20 条
            title = (article.get("title", "") + " " + article.get("description", "")).lower()
            detected = []
            for category, keywords in CATALYST_KEYWORDS.items():
                for kw in keywords:
                    if kw.lower() in title:
                        detected.append(category)
                        break
            if detected:
                pub = article.get("published_at", "")
                date_str = pub if isinstance(pub, str) else str(pub)[:10]
                catalysts.append({
                    "date": date_str,
                    "title": article.get("title", ""),
                    "categories": detected,
                })

    # 财报事件
    if consensus:
        eps = consensus.get("normalized_eps", {}) or consensus.get("eps", {})
        rev = consensus.get("revenue", {})
        if eps or rev:
            events = []
            if eps.get("comp") == "beat_est":
                events.append("EPS 超预期")
            elif eps.get("comp") == "miss_est":
                events.append("EPS 低于预期")
            if rev.get("comp") == "beat_est":
                events.append("营收超预期")
            elif rev.get("comp") == "miss_est":
                events.append("营收低于预期")
            if events:
                catalysts.append({
                    "date": "latest_quarter",
                    "title": "最新财报: " + ", ".join(events),
                    "categories": ["earnings"],
                })

    # 分类汇总
    cat_counts = {}
    for c in catalysts:
        for cat in c["categories"]:
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

    has_catalyst = len(catalysts) > 0
    top_cats = sorted(cat_counts.items(), key=lambda x: -x[1])[:3]

    signals = {
        "available": True,
        "news_count": news_count,
        "catalyst_count": len(catalysts),
        "has_major_catalyst": any(
            cat in ("earnings", "product", "ai_data_center", "ma")
            for cat in cat_counts
        ),
        "top_categories": [c[0] for c in top_cats],
        "description": (
            f"检测到 {len(catalysts)} 个潜在催化剂 ({', '.join(c[0] for c in top_cats)})"
            if has_catalyst else "未检测到明显催化剂"
        ),
    }

    research_inputs = {
        "CA-001": {
            "label": "Catalyst Detection",
            "claim": signals["description"],
            "assessment": (
                "Strong" if has_catalyst and signals["has_major_catalyst"]
                else "Present" if has_catalyst else "None"
            ),
        },
    }

    return {"signals": signals, "research_inputs": research_inputs}
