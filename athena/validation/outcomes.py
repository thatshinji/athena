"""结果分类 — 按 09_VALIDATION_AND_BACKTEST.md §3 规范。

分类标准：
- UpsideFirst: 先触及 +20% 目标价
- StopLossFirst: 先触及 -10% 止损价
- Neither: 窗口期内均未触及
- Inconclusive: 数据不足无法判断
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from athena.validation.cases import CaseRecord


def classify_outcome(case: "CaseRecord") -> str:
    """分类案例结果。

    Returns: UpsideFirst | StopLossFirst | Neither | Inconclusive
    """
    # 双方都未触发且窗口未结束 → 待定
    if not case.upside_hit_date and not case.downside_hit_date:
        if case.window_end_date:
            from datetime import datetime
            if datetime.now().strftime("%Y-%m-%d") < case.window_end_date:
                return "Inconclusive"
        return "Neither"

    # 单方触发
    if case.upside_hit_date and not case.downside_hit_date:
        return "UpsideFirst"
    if case.downside_hit_date and not case.upside_hit_date:
        return "StopLossFirst"

    # 双方触发 → 比较时间
    if case.upside_hit_date < case.downside_hit_date:
        return "UpsideFirst"
    return "StopLossFirst"
