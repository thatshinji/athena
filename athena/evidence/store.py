"""Evidence Store — 收集、序列化 Evidence 列表"""

import json
from typing import Dict, List

from athena.evidence.models import Evidence


class EvidenceStore:
    """证据存储器"""

    def __init__(self):
        self._items: List[Evidence] = []

    def add(self, evidence: Evidence):
        self._items.append(evidence)

    def add_all(self, evidence_list: List[Evidence]):
        for e in evidence_list:
            self._items.append(e)

    def to_list(self) -> List[Dict]:
        return [e.to_dict() for e in self._items]

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_list(), ensure_ascii=False, indent=indent)

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self._items)
