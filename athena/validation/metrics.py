"""校准指标 — 按 09_VALIDATION_AND_BACKTEST.md §4-5 规范。

计算 TP/FP/TN/FN、Candidate Success Rate、UpsideFirst/StopLossFirst 率。
"""

from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from athena.validation.cases import CaseRecord
    from athena.validation.outcomes import classify_outcome


def compute_calibration(cases: List["CaseRecord"]) -> Dict:
    """计算全部校准指标。"""
    resolved = [c for c in cases if c.to_dict()["outcome"] != "Inconclusive"]
    if not resolved:
        return {"status": "insufficient_data", "message": "无已结案例"}

    cands = [c for c in resolved if c.status_at_time == "Candidate"]
    tp = sum(1 for c in cands if c.to_dict()["is_correct"])
    fp = len(cands) - tp

    non_cands = [c for c in resolved if c.status_at_time != "Candidate"]
    fn = sum(1 for c in non_cands if c.to_dict()["outcome"] == "UpsideFirst")
    tn = len(non_cands) - fn

    total = len(resolved)
    success_rate = round(tp / len(cands) * 100, 1) if cands else 0

    upside_first = sum(1 for c in resolved if c.to_dict()["outcome"] == "UpsideFirst")
    stop_first = sum(1 for c in resolved if c.to_dict()["outcome"] == "StopLossFirst")
    neither = total - upside_first - stop_first

    return {
        "total_cases": len(cases),
        "resolved_cases": total,
        "pending_cases": len(cases) - total,
        "candidates": len(cands),
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "candidate_success_rate": success_rate,
        "balance_required_rate": 33.3,
        "above_balance": success_rate > 33.3,
        "upside_first_rate": round(upside_first / total * 100, 1) if total else 0,
        "stop_loss_first_rate": round(stop_first / total * 100, 1) if total else 0,
        "neither_rate": round(neither / total * 100, 1) if total else 0,
    }
