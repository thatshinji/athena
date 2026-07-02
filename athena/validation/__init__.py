"""验证与回测 — 历史案例管理系统。"""

import json
import logging
from pathlib import Path
from typing import List

from athena.validation.cases import CaseRecord
from athena.validation.outcomes import classify_outcome
from athena.validation.metrics import compute_calibration

logger = logging.getLogger(__name__)
CASES_DIR = Path(__file__).resolve().parent / "case_data"
CASES_DIR.mkdir(exist_ok=True)


class CaseStore:
    """历史案例存储器（JSON 文件持久化）"""

    def __init__(self, filepath: str = None):
        self._path = Path(filepath) if filepath else CASES_DIR / "cases.json"
        self._cases: List[CaseRecord] = []
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                with open(self._path) as f:
                    data = json.load(f)
                self._cases = [
                    CaseRecord(**{k: v for k, v in d.items()
                                  if k not in ("outcome", "is_correct", "evidence_summary")})
                    for d in data
                ]
                # 恢复 evidence_summary
                for i, d in enumerate(data):
                    if d.get("evidence_summary"):
                        self._cases[i].evidence_summary = d["evidence_summary"]
            except Exception as e:
                logger.warning(f"加载历史案例失败: {e}")

    def _save(self):
        with open(self._path, "w") as f:
            json.dump([c.to_dict() for c in self._cases], f, ensure_ascii=False, indent=2, default=str)

    def add(self, case: CaseRecord):
        for i, existing in enumerate(self._cases):
            if existing.case_id == case.case_id:
                self._cases[i] = case
                self._save()
                return
        self._cases.append(case)
        self._save()

    @property
    def candidates(self) -> List[CaseRecord]:
        return [c for c in self._cases if c.status_at_time == "Candidate"]

    @property
    def total_count(self) -> int:
        return len(self._cases)

    def calibration_metrics(self) -> dict:
        return compute_calibration(self._cases)

    def to_dataframe(self):
        import pandas as pd
        return pd.DataFrame([c.to_dict() for c in self._cases])


# 全局实例
store = CaseStore()
