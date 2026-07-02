"""中文研究报告生成模块。"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict

from athena.config import settings
from athena.data.market_provider import LongbridgeMarketProvider
from athena.data.fundamental_provider import fetch_fundamentals
from athena.data.content_provider import fetch_news
from athena.data.market_flow_provider import fetch_broker_holdings
from athena.signals.technical import compute_technical_signals
from athena.signals.fundamentals import compute_fundamental_signals
from athena.signals.valuation import compute_valuation_signals
from athena.signals.risk import compute_risk_signals
from athena.signals.catalysts import compute_catalyst_signals
from athena.signals.flow import compute_flow_signals
from athena.signals.sentiment import compute_sentiment_signals
from athena.evidence.models import Evidence, build_price_evidence
from athena.evidence.store import EvidenceStore

logger = logging.getLogger(__name__)
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"


def generate_report(symbol: str, days: int = 250, use_llm: bool = False) -> Dict:
    symbol = symbol.upper()
    provider = LongbridgeMarketProvider()

    df = provider.fetch_history(symbol, days=days)
    spy_df = None
    if symbol not in ("SPY", "QQQ"):
        try:
            spy_df = provider.fetch_history("SPY", days=days)
        except Exception:
            pass

    tech_result = compute_technical_signals(df, benchmark_df=spy_df)

    fund_data = fetch_fundamentals(symbol)
    fund_result = compute_fundamental_signals(fund_data, tech_result["latest"]["close"])
    val_result = compute_valuation_signals(fund_data, tech_result["latest"]["close"])

    news_list = fetch_news(symbol)
    cat_result = compute_catalyst_signals(news_list, fund_data.get("consensus", {}) if fund_data else {})
    sent_result = compute_sentiment_signals(news_list)

    broker_data = fetch_broker_holdings(symbol)
    flow_result = compute_flow_signals(broker_data)

    risk_result = compute_risk_signals(tech_result["signals"], fund_result["signals"], val_result["signals"])

    all_ri = {}
    for r in [tech_result, fund_result, val_result, risk_result, cat_result, flow_result, sent_result]:
        all_ri.update(r["research_inputs"])

    all_signals = {
        "technical": tech_result["signals"],
        "fundamental": fund_result["signals"],
        "valuation": val_result["signals"],
        "risk": risk_result["signals"],
        "catalyst": cat_result["signals"],
        "flow": flow_result["signals"],
        "sentiment": sent_result["signals"],
    }

    source = provider.data_source
    evidence_list = build_price_evidence(symbol, tech_result, source=source)
    as_of = datetime.now().isoformat()
    ev_confidence = "High" if source == "longbridge" else "Low"

    def _add_evidence(ri_dict, src_type, ev_type):
        for ri_val in ri_dict.values():
            if ri_val.get("assessment") not in ("N/A", None):
                evidence_list.append(Evidence(symbol=symbol, as_of=as_of, source=source,
                    source_type=src_type, evidence_type=ev_type, claim=ri_val["claim"],
                    confidence=ev_confidence))

    _add_evidence(fund_result["research_inputs"], "fundamental", "fundamental")
    _add_evidence(val_result["research_inputs"], "fundamental", "valuation")
    _add_evidence(risk_result["research_inputs"], "risk", "risk")
    _add_evidence(cat_result["research_inputs"], "catalyst", "catalyst")
    _add_evidence(flow_result["research_inputs"], "flow", "flow")
    _add_evidence(sent_result["research_inputs"], "sentiment", "sentiment")

    store = EvidenceStore()
    store.add_all(evidence_list)

    result = {
        "symbol": symbol, "as_of": as_of, "source": source,
        "latest": tech_result["latest"], "signals": all_signals,
        "research_inputs": all_ri, "evidence": store.to_list(),
        "report": None, "report_path": None,
    }

    if use_llm and settings.deepseek_configured:
        try:
            from athena.llm.analyst import DeepSeekAnalyst
            analyst = DeepSeekAnalyst()
            report = analyst.analyze(symbol, result["evidence"], result["signals"])
            analyst.close()
            result["report"] = report
            result["report_path"] = _save_report(symbol, report)
        except Exception as e:
            logger.error(f"LLM 分析失败: {e}")
            result["report"] = {"status": "Not Ready", "confidence": "Not Ready",
                                "error": str(e), "report_markdown": f"# 报告生成失败\n\nLLM 调用出错: {e}"}
    else:
        try:
            from athena.probability import estimate_probability
            from athena.probability.engine import _classify_status
            prob = estimate_probability(all_signals, tech_result["latest"]["close"])
            status = _classify_status(prob)
            result["report"] = {"symbol": symbol, "status": status,
                "upside_probability_range": prob["upside_probability_range"],
                "downside_probability_range": prob["downside_probability_range"],
                "confidence": prob["confidence"],
                "key_evidence": prob["factors"]["bullish"][:3] + prob["factors"]["bearish"][:3],
                "missing_evidence": [], "watchlist": [], "report_markdown": ""}
        except Exception as e:
            logger.debug(f"规则引擎失败: {e}")

    if result.get("report"):
        try:
            from athena.validation import store as case_store, CaseRecord
            case_store.add(CaseRecord.from_report(symbol, result))
            result["calibration"] = case_store.calibration_metrics()
        except Exception as e:
            logger.debug(f"案例保存失败: {e}")

    return result


def _save_report(symbol: str, report: Dict) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = OUTPUT_DIR / f"{symbol}_report_{ts}.md"
    markdown = report.get("report_markdown", "") or _format_report_json(report)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown)
    json_path = OUTPUT_DIR / f"{symbol}_report_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    return str(filepath)


def _format_report_json(report: Dict) -> str:
    labels = {"Candidate": "⭐ Candidate", "Watch": "👀 Watch", "Reject": "❌ Reject", "Risk Alert": "⚠️ Risk Alert"}
    status = report.get("status", "Unknown")
    return f"""# {report.get('symbol', '')} 3–6 个月交易窗口研究
## 一、研究结论
{labels.get(status, status)}
置信度: {report.get('confidence', 'N/A')}
## 上行路径
{chr(10).join('- ' + p for p in report.get('upside_path', [])) or '无'}
## 下行风险
{chr(10).join('- ' + r for r in report.get('downside_risks', [])) or '无'}
## 关键证据
{chr(10).join('- ' + e for e in report.get('key_evidence', [])) or '无'}
## 缺失证据
{chr(10).join('- ' + e for e in report.get('missing_evidence', [])) or '无'}
## 观察清单
{chr(10).join('- ' + w for w in report.get('watchlist', [])) or '无'}
"""
