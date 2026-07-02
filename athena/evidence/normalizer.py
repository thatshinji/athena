"""Evidence 标准化器。

将不同数据源的原始数据统一转换为 Evidence 格式。
"""

from datetime import datetime
from typing import Any, Dict, List

from athena.evidence.models import Evidence


def normalize_tech_to_evidence(
    symbol: str, tech_result: Dict, source: str
) -> List[Evidence]:
    """技术面指标 → Evidence 列表。

    从 compute_technical_signals() 输出的 research_inputs 构建 Evidence。
    """
    ri = tech_result.get("research_inputs", {})
    latest = tech_result.get("latest", {})
    signals = tech_result.get("signals", {})
    as_of = datetime.now().isoformat()
    ev_conf = "High" if source in ("longbridge", "yfinance") else "Low"

    items = []

    for key, ri_val in ri.items():
        if ri_val.get("assessment") == "N/A":
            continue
        items.append(Evidence(
            symbol=symbol, as_of=as_of,
            source=source, source_type="market_data",
            evidence_type="technical",
            claim=ri_val["claim"],
            confidence=ev_conf,
        ))

    return items


def normalize_fundamental_to_evidence(
    symbol: str, fund_result: Dict, source: str
) -> List[Evidence]:
    """基本面信号 → Evidence 列表。"""
    ri = fund_result.get("research_inputs", {})
    as_of = datetime.now().isoformat()
    ev_conf = "High" if source == "longbridge" else "Low"

    items = []
    for key, ri_val in ri.items():
        if ri_val.get("assessment") == "N/A":
            continue
        items.append(Evidence(
            symbol=symbol, as_of=as_of,
            source=source, source_type="fundamental",
            evidence_type="fundamental",
            claim=ri_val["claim"],
            confidence=ev_conf,
        ))
    return items


def normalize_valuation_to_evidence(
    symbol: str, val_result: Dict, source: str
) -> List[Evidence]:
    """估值信号 → Evidence 列表。"""
    ri = val_result.get("research_inputs", {})
    as_of = datetime.now().isoformat()
    ev_conf = "High" if source == "longbridge" else "Low"

    items = []
    for key, ri_val in ri.items():
        if ri_val.get("assessment") == "N/A":
            continue
        items.append(Evidence(
            symbol=symbol, as_of=as_of,
            source=source, source_type="fundamental",
            evidence_type="valuation",
            claim=ri_val["claim"],
            confidence=ev_conf,
        ))
    return items
