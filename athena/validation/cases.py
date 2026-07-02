"""验证案例 — 按 09_VALIDATION_AND_BACKTEST.md 定义。

案例数据结构和存储。
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, Optional


@dataclass
class CaseRecord:
    """历史案例记录"""
    case_id: str
    symbol: str
    as_of_date: str
    as_of_price: float
    upside_target: float
    downside_stop: float
    status_at_time: str  # Candidate/Watch/Reject/Risk Alert
    evidence_summary: Dict = None

    # 后验
    upside_hit_date: Optional[str] = None
    downside_hit_date: Optional[str] = None
    window_end_date: Optional[str] = None
    final_price: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    notes: str = ""

    def __post_init__(self):
        if self.evidence_summary is None:
            self.evidence_summary = {}

    @classmethod
    def from_report(cls, symbol: str, report_result: Dict) -> "CaseRecord":
        price = report_result.get("latest", {}).get("close", 0)
        signals = report_result.get("signals", {})
        report = report_result.get("report", {})
        status = report.get("status", "Watch") if report else "Watch"
        ev_summary = {
            "source": report_result.get("source", "unknown"),
            "evidence_count": len(report_result.get("evidence", [])),
            "pe": signals.get("valuation", {}).get("trailing_pe", {}).get("current"),
            "fwd_pe": signals.get("valuation", {}).get("forward_pe", {}).get("value"),
            "eps_beat": signals.get("fundamental", {}).get("eps", {}).get("beat_pct"),
            "gross_margin": signals.get("fundamental", {}).get("gross_margin"),
            "risk_score": signals.get("risk", {}).get("risk_score"),
        }
        return cls(
            case_id=f"{symbol}_{datetime.now().strftime('%Y-%m-%d')}",
            symbol=symbol,
            as_of_date=datetime.now().strftime("%Y-%m-%d"),
            as_of_price=price,
            upside_target=round(price * 1.20, 2),
            downside_stop=round(price * 0.90, 2),
            status_at_time=status,
            evidence_summary=ev_summary,
            window_end_date=(datetime.now() + timedelta(days=180)).strftime("%Y-%m-%d"),
        )

    def to_dict(self) -> Dict:
        from athena.validation.outcomes import classify_outcome
        d = asdict(self)
        d["outcome"] = classify_outcome(self)
        d["is_correct"] = (self.status_at_time == "Candidate" and d["outcome"] == "UpsideFirst")
        return d
