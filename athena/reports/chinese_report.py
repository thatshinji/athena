"""中文研究报告生成模块。"""

import json, logging
from datetime import datetime
from pathlib import Path
from typing import Dict

from athena.config import settings
from athena.data.market_provider import LongbridgeMarketProvider
from athena.data.fundamental_provider import fetch_fundamentals
from athena.data.content_provider import fetch_news
from athena.data.market_flow_provider import fetch_broker_holdings
from athena.data.political_trades import fetch_political_trades, fetch_insider_trades
from athena.data.social import fetch_community_topics
from athena.signals.technical import compute_technical_signals
from athena.signals.fundamentals import compute_fundamental_signals
from athena.signals.valuation import compute_valuation_signals
from athena.signals.risk import compute_risk_signals
from athena.signals.catalysts import compute_catalyst_signals
from athena.signals.flow import compute_flow_signals
from athena.signals.sentiment import compute_sentiment_signals
from athena.signals.political import compute_political_signals
from athena.signals.macro import compute_macro_signals
from athena.evidence.models import Evidence, build_price_evidence
from athena.evidence.store import EvidenceStore

logger = logging.getLogger(__name__)
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"


def _fetch_industry_valuation(symbol: str):
    try:
        from athena.data.fundamental_provider import _init_fundamental, _fund_ctx
        _init_fundamental()
        if _fund_ctx:
            return list(_fund_ctx.industry_valuation(f"{symbol}.US").list)
    except Exception:
        pass
    return None


def generate_report(symbol: str, days: int = 250, use_llm: bool = False) -> Dict:
    symbol = symbol.upper()
    provider = LongbridgeMarketProvider()
    df = provider.fetch_history(symbol, days=days)
    spy_df = None
    qqq_df = None
    if symbol not in ("SPY", "QQQ"):
        try:
            spy_df = provider.fetch_history("SPY", days=days)
            qqq_df = provider.fetch_history("QQQ", days=days)
        except Exception:
            pass

    tech_result = compute_technical_signals(df, benchmark_df=spy_df)
    fund_data = fetch_fundamentals(symbol)
    fund_result = compute_fundamental_signals(fund_data, tech_result["latest"]["close"])
    val_result = compute_valuation_signals(fund_data, tech_result["latest"]["close"])

    news_list = fetch_news(symbol)
    community = fetch_community_topics(symbol)
    cat_result = compute_catalyst_signals(
        news_list, fund_data.get("consensus", {}) if fund_data else {},
        fund_data.get("corp_actions") if fund_data else None)
    sent_result = compute_sentiment_signals(news_list, community)

    broker_data = fetch_broker_holdings(symbol)
    flow_result = compute_flow_signals(broker_data, fund_data)

    pol_trades = fetch_political_trades(symbol)
    ins_trades = fetch_insider_trades(symbol)
    pol_result = compute_political_signals(pol_trades, ins_trades)

    macro_data = _fetch_industry_valuation(symbol)
    macro_result = compute_macro_signals(
        macro_data, val_result["signals"].get("trailing_pe", {}).get("current"))

    risk_result = compute_risk_signals(tech_result["signals"], fund_result["signals"], val_result["signals"])

    all_ri = {}
    for r in [tech_result, fund_result, val_result, risk_result, cat_result, flow_result, sent_result, pol_result, macro_result]:
        all_ri.update(r["research_inputs"])

    all_signals = {
        "technical": tech_result["signals"], "fundamental": fund_result["signals"],
        "valuation": val_result["signals"], "risk": risk_result["signals"],
        "catalyst": cat_result["signals"], "flow": flow_result["signals"],
        "sentiment": sent_result["signals"], "political": pol_result["signals"],
        "macro": macro_result["signals"],
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
    _add_evidence(pol_result["research_inputs"], "political", "political")
    _add_evidence(macro_result["research_inputs"], "macro", "macro")

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
                                "error": str(e), "report_markdown": f"# LLM 调用出错: {e}"}
    else:
        try:
            from athena.probability import estimate_probability
            from athena.probability.engine import _classify_status
            prob = estimate_probability(all_signals, tech_result["latest"]["close"])
            result["report"] = {"symbol": symbol, "status": _classify_status(prob, all_signals),
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
    fp = OUTPUT_DIR / f"{symbol}_report_{ts}.md"
    md = report.get("report_markdown", "") or _format_report_json(report)
    fp.write_text(md, encoding="utf-8")
    jp = OUTPUT_DIR / f"{symbol}_report_{ts}.json"
    jp.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return str(fp)


def _format_report_json(report: Dict) -> str:
    labels = {"Candidate": "⭐ Candidate", "Watch": "👀 Watch", "Reject": "❌ Reject", "Risk Alert": "⚠️ Risk Alert"}
    s = report.get("status", "Unknown")
    return f"""# {report.get('symbol', '')} 3–6 个月交易窗口研究
## 一、研究结论
{labels.get(s, s)}
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
