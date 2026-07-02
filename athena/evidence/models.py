"""Evidence 数据模型 — 按 03_DATA_SOURCE_CONTRACT.md 规范定义"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Evidence:
    """统一证据结构"""

    symbol: str
    as_of: str  # ISO 8601 时间戳
    source: str  # e.g. "longbridge", "fixture"
    source_type: str  # e.g. "market_data", "fundamental"
    evidence_type: str  # e.g. "technical", "fundamental", "catalyst"
    claim: str  # 一句话证据声明
    metrics: Dict[str, Any] = field(default_factory=dict)
    url: Optional[str] = None
    confidence: str = "High"  # High | Medium | Low
    limitations: List[str] = field(default_factory=list)

    @property
    def evidence_id(self) -> str:
        """生成唯一 Evidence ID，格式: {SYMBOL}_{SOURCE}_{TYPE}_{YYYY-MM-DD}"""
        date_part = self.as_of[:10]
        source_abbr = {
            "longbridge": "LB", "yfinance": "YF", "fixture": "FX",
        }.get(self.source, self.source[:2].upper())
        type_abbr = self.evidence_type[:3].upper()
        return f"{self.symbol}_{source_abbr}_{type_abbr}_{date_part}"

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["evidence_id"] = self.evidence_id
        return d


def build_price_evidence(symbol: str, tech_result: Dict, source: str = "fixture") -> List[Evidence]:
    """从技术面计算结果构建 Evidence 列表。

    Args:
        symbol: 股票代码
        tech_result: compute_technical_signals 的输出
        source: 数据来源（longbridge / yfinance / fixture）

    Returns:
        Evidence 列表
    """
    latest = tech_result["latest"]
    signals = tech_result["signals"]
    ri = tech_result["research_inputs"]
    as_of = datetime.now().isoformat()
    # 真实数据源置信度更高
    evidence_confidence = "High" if source in ("longbridge", "yfinance") else "Low"

    evidence_list = []

    # TC-001 Price Trend
    e1 = Evidence(
        symbol=symbol,
        as_of=as_of,
        source=source,
        source_type="market_data",
        evidence_type="technical",
        claim=ri["TC-001"]["claim"],
        metrics={
            "close": latest["close"],
            "ma20": latest["ma20"],
            "ma50": latest["ma50"],
            "ma200": latest["ma200"],
        },
        confidence=evidence_confidence,
    )
    evidence_list.append(e1)

    # TC-002 Moving Average Alignment
    e2 = Evidence(
        symbol=symbol,
        as_of=as_of,
        source=e1.source,
        source_type="market_data",
        evidence_type="technical",
        claim=ri["TC-002"]["claim"],
        metrics={
            "alignment_type": signals["price"]["alignment"]["type"],
            "bullish": signals["price"]["alignment"]["bullish"],
        },
        confidence="High",
    )
    evidence_list.append(e2)

    # TC-005 Volatility / ATR
    e3 = Evidence(
        symbol=symbol,
        as_of=as_of,
        source=e1.source,
        source_type="market_data",
        evidence_type="technical",
        claim=ri["TC-005"]["claim"],
        metrics={
            "atr14": latest["atr14"],
            "atr_pct": latest["atr_pct"],
        },
        confidence="High",
    )
    evidence_list.append(e3)

    # RK-010 Drawdown / Stop-loss Risk
    e4 = Evidence(
        symbol=symbol,
        as_of=as_of,
        source=e1.source,
        source_type="market_data",
        evidence_type="technical",
        claim=ri["RK-010"]["claim"],
        metrics={
            "stop_loss_feasible": signals["volatility"]["atr_stop_assessment"].get(
                "stop_loss_feasible"
            ),
            "rsi14": latest["rsi14"],
        },
        confidence="Medium",
    )
    evidence_list.append(e4)

    # TC-006 Support / Resistance
    if "TC-006" in ri:
        evidence_list.append(Evidence(
            symbol=symbol,
            as_of=as_of,
            source=source,
            source_type="market_data",
            evidence_type="technical",
            claim=ri["TC-006"]["claim"],
            metrics={
                "high_52w": latest.get("high_52w"),
                "low_52w": latest.get("low_52w"),
                "pct_from_high": latest.get("pct_from_high"),
                "pct_from_low": latest.get("pct_from_low"),
            },
            confidence=evidence_confidence,
        ))

    # RS-001 Relative Strength vs SPY
    if "RS-001" in ri and signals.get("relative_strength"):
        evidence_list.append(Evidence(
            symbol=symbol,
            as_of=as_of,
            source=source,
            source_type="market_data",
            evidence_type="technical",
            claim=ri["RS-001"]["claim"],
            metrics={
                "stock_change_pct": signals["relative_strength"]["stock_change_pct"],
                "benchmark_change_pct": signals["relative_strength"]["benchmark_change_pct"],
                "relative": signals["relative_strength"]["relative"],
            },
            confidence=evidence_confidence,
        ))

    return evidence_list
