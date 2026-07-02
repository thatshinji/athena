"""LLM 输出 JSON Schema — 按 07_LLM_RESEARCH_PROTOCOL.md §7 规范定义。

用于验证 LLM 返回的结构化数据。
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ResearchReport:
    """LLM 研究报告结构"""
    symbol: str
    status: str  # Candidate | Watch | Reject | Risk Alert
    upside_probability_range: List[float]  # [lower, upper] e.g. [0.35, 0.55]
    downside_probability_range: List[float]  # [lower, upper]
    confidence: str  # High | Medium | Low | Not Ready
    upside_path: List[str] = field(default_factory=list)
    downside_risks: List[str] = field(default_factory=list)
    key_evidence: List[str] = field(default_factory=list)
    missing_evidence: List[str] = field(default_factory=list)
    watchlist: List[str] = field(default_factory=list)
    report_markdown: str = ""

    def is_valid_status(self) -> bool:
        return self.status in ("Candidate", "Watch", "Reject", "Risk Alert")

    def is_valid_confidence(self) -> bool:
        return self.confidence in ("High", "Medium", "Low", "Not Ready")

    def has_valid_ranges(self) -> bool:
        """概率区间是否在 0-100 范围内"""
        for r in (self.upside_probability_range, self.downside_probability_range):
            if len(r) != 2:
                return False
            if not (0 <= r[0] <= r[1] <= 100):
                return False
        return True


# 允许的状态和置信度值供外部校验使用
VALID_STATUSES = ("Candidate", "Watch", "Reject", "Risk Alert")
VALID_CONFIDENCES = ("High", "Medium", "Low", "Not Ready")
