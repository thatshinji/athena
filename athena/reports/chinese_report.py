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
from athena.signals.supply_chain import compute_supply_chain_signals, SUPPLY_CHAIN_MAP
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



def _fetch_supplier_prices(symbol, provider):
    """获取供应商近期价格变化"""
    chain = SUPPLY_CHAIN_MAP.get(symbol.upper().replace(".US",""), {}).get("suppliers", [])
    if not chain:
        return None
    result = {}
    for ticker in chain[:5]:
        try:
            df = provider.fetch_history(ticker, days=30)
            if df is not None and len(df) >= 10:
                pct = round((df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100, 1)
                result[ticker] = pct
        except Exception:
            pass
    return result if result else None


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

    # 供应链
    supplier_prices = _fetch_supplier_prices(symbol, provider)
    sc_result = compute_supply_chain_signals(symbol, news_list, supplier_prices)

    all_ri = {}
    for r in [tech_result, fund_result, val_result, risk_result, cat_result, flow_result, sent_result, pol_result, macro_result, sc_result]:
        all_ri.update(r["research_inputs"])

    all_signals = {
        "technical": tech_result["signals"], "fundamental": fund_result["signals"],
        "valuation": val_result["signals"], "risk": risk_result["signals"],
        "catalyst": cat_result["signals"], "flow": flow_result["signals"],
        "sentiment": sent_result["signals"], "political": pol_result["signals"],
        "macro": macro_result["signals"],
        "supply_chain": sc_result["signals"],
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
    _add_evidence(sc_result["research_inputs"], "supply_chain", "supply_chain")

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
            # 规则引擎计算确定性概率
            from athena.probability import estimate_probability
            prob = estimate_probability(all_signals, tech_result["latest"]["close"])
            analyst = DeepSeekAnalyst()
            report = analyst.analyze(symbol, result["evidence"], result["signals"],
                                     prob["upside_probability_range"],
                                     prob["downside_probability_range"])
            analyst.close()
            # 规则引擎概率覆盖 LLM 输出（确保一致性）
            report["upside_probability_range"] = prob["upside_probability_range"]
            report["downside_probability_range"] = prob["downside_probability_range"]
            report["confidence"] = prob["confidence"]
            # 在 LLM 报告前插入引擎校准概率（LLM 可能在正文写不一致的数字）
            md = report.get("report_markdown", "")
            if md:
                up_str = f"{prob['upside_probability_range'][0]}%-{prob['upside_probability_range'][1]}%"
                down_str = f"{prob['downside_probability_range'][0]}%-{prob['downside_probability_range'][1]}%"
                cal_note = prob.get("calibration_note", "")
                preamble = f"> **引擎校准概率**: +20% 区间 **{up_str}**, -10% 区间 **{down_str}**{cal_note}\n\n---\n\n"
                report["report_markdown"] = preamble + md
            result["report"] = report
            result["report_path"] = _save_report(symbol, report, result)
        except Exception as e:
            logger.error(f"LLM 分析失败: {e}")
            result["report"] = {"status": "Not Ready", "confidence": "Not Ready",
                                "error": str(e), "report_markdown": f"# LLM 调用出错: {e}"}
            result["report_path"] = _save_report(symbol, result["report"], result)
    else:
        try:
            from athena.probability import estimate_probability
            from athena.probability.engine import _classify_status
            prob = estimate_probability(all_signals, tech_result["latest"]["close"])
            status = _classify_status(prob, all_signals)
            up_path, down_risks, key_ev, missing, watch = _build_rule_report(
                symbol, all_signals, tech_result["latest"], all_ri, status)
            result["report"] = {"symbol": symbol, "status": status,
                "upside_probability_range": prob["upside_probability_range"],
                "downside_probability_range": prob["downside_probability_range"],
                "confidence": prob["confidence"],
                "upside_path": up_path, "downside_risks": down_risks,
                "key_evidence": key_ev, "missing_evidence": missing,
                "watchlist": watch, "report_markdown": ""}
            result["report_path"] = _save_report(symbol, result["report"], result)
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


def _save_report(symbol: str, report: Dict, result: Dict = None) -> str:
    symbol_dir = OUTPUT_DIR / symbol
    symbol_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y_%m%d_%H%M")
    fp = symbol_dir / f"{ts}.md"
    md = report.get("report_markdown", "") or _format_report_json(report)
    # 后处理：修复 markdown 标题格式
    import re
    nums = "一二三四五六七八九十"
    sec_names = ["研究结论", "+20% 上行路径", "-10% 下行风险", "技术面判断",
                 "基本面判断", "估值与预期判断", "消息面与催化剂", "资金流与情绪",
                 "风险官反驳", "最终判断与观察清单"]
    for i in range(10):
        n, s = nums[i], sec_names[i]
        # 先剥离所有已有前缀，再统一添加 ##
        md = re.sub(rf'(\*\*|##\s*)?{n}、{s}(\*\*)?', f'## {n}、{s}', md)
    # 截断尾部不完整句子（LLM 超时截断）
    if md.rstrip().endswith(('；', '：', '，', ',')):
        md = md.rstrip().rstrip('；：，,') + '。'
    # 注入数据来源与方法章节（不覆盖 LLM 已有内容）
    if "## 数据来源" not in md and "数据来源与分析方法" not in md:
        cal = report.get("calibration_note", "")
        md += f"\n\n## 数据来源与分析方法\n"
        md += "- **行情**：Longbridge OpenAPI LV1 实时行情 + yfinance 备选\n"
        md += "- **财报**：Longbridge FundamentalContext（IS/BS/CF 三表）\n"
        md += "- **估值**：Trailing PE / Forward PE / P/S / EV/EBIT / FCF Yield / 行业对比\n"
        md += "- **技术面**：MA/RSI/ATR + Volume Profile（成交量分布）+ Market Structure（HH/HL 趋势结构）\n"
        md += "- **催化剂**：新闻关键词检测 + corp_actions 结构化事件 + 具体标题与日期\n"
        md += "- **资金流**：经纪商 + ETF 持仓 + 机构股东 + 大股东增减持\n"
        md += "- **情绪**：新闻文本分析 + LongPort 社区讨论\n"
        md += f"- **概率模型**：规则引擎打分 + 历史案例贝叶斯校准{('（' + cal + '）') if cal else ''}\n"
        md += f"- **置信度**：{report.get('confidence', 'N/A')}\n"
    # 追加 CLI 原始数据摘要（方便查阅）
    if result:
        md += _build_raw_data_appendix(result, report)
        md += _build_cli_summary(result, report)
    fp.write_text(md, encoding="utf-8")
    jp = symbol_dir / f"{ts}.json"
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
## 数据来源与分析方法
- 行情数据：Longbridge OpenAPI (LV1 实时行情) + yfinance 备选
- 基本面：Longbridge FundamentalContext (IS/BS/CF 三表 + 一致预期)
- 估值：Trailing PE / Forward PE / P/S / EV/EBIT / FCF Yield / 行业对比
- 技术面：MA/RSI/ATR + Volume Profile + Market Structure (HH/HL)
- 催化剂：新闻关键词检测 + 结构化公司事件 (corp_actions)
- 资金流：经纪商 + ETF 持仓 + 机构股东 + 大股东增减持
- 情绪：新闻文本分析 + LongPort 社区讨论
- 概率模型：规则引擎打分 + 历史案例贝叶斯校准 ({report.get('calibration_note', '')})
- 置信度：{report.get('confidence', 'N/A')}"""

def _build_raw_data_appendix(result: Dict, report: Dict) -> str:
    """构建原始数据摘要附录。"""
    latest = result.get("latest", {})
    ri = result.get("research_inputs", {})
    ev = result.get("evidence", [])
    cal = result.get("calibration", {})
    signals = result.get("signals", {})

    md = "\n\n---\n\n## 附录：原始数据摘要\n\n"
    md += f"- **数据源**: {result.get('source', 'N/A')}\n"
    if latest.get('close'):
        md += f"- **收盘价**: ${latest['close']:.2f}\n"
    md += f"- **MA20**: {latest.get('ma20', 'N/A')} | **MA50**: {latest.get('ma50', 'N/A')} | **MA200**: {latest.get('ma200', 'N/A')}\n"
    md += f"- **RSI14**: {latest.get('rsi14', 'N/A')} | **ATR%**: {latest.get('atr_pct', 'N/A')}%\n"
    md += f"- **52W High**: {latest.get('high_52w', 'N/A')} | **52W Low**: {latest.get('low_52w', 'N/A')}\n"
    md += f"- **判断**: {report.get('status', 'N/A')} (置信度: {report.get('confidence', 'N/A')})\n"
    up = report.get("upside_probability_range", [])
    down = report.get("downside_probability_range", [])
    if up and down:
        md += f"- **+20% 概率**: {up[0]}-{up[1]}% | **-10% 概率**: {down[0]}-{down[1]}%\n"
    rsk = signals.get("risk", {}).get("risk_score")
    if rsk is not None:
        md += f"- **风险评分**: {rsk}/10\n"
    if cal and cal.get("resolved_cases", 0) > 0:
        md += f"- **历史校准**: {cal['resolved_cases']} 已结案例, Candidate 胜率 {cal['candidate_success_rate']}%\n"
    md += "\n### Research Input 映射\n\n| ID | 标签 | 评估 |\n|----|------|------|\n"
    for k, v in ri.items():
        md += f"| {k} | {v.get('label', 'N/A')} | {v.get('assessment', 'N/A')} |\n"
    md += f"\n### Evidence ({len(ev)} 条)\n\n"
    for e in ev:
        md += f"- [{e.get('confidence', '?')}] {e.get('claim', '')[:100]}\n"
    return md


def _build_rule_report(symbol, signals, latest, ri, status):
    tech = signals.get("technical", {})
    fund = signals.get("fundamental", {})
    val = signals.get("valuation", {})
    risk = signals.get("risk", {})
    flow = signals.get("flow", {})
    cat = signals.get("catalyst", {})
    sent = signals.get("sentiment", {})

    up = []; down = []; key = []; missing = []; watch = []
    rev_yoy = fund.get("revenue_yoy", 0) or 0
    eps_beat = fund.get("eps", {}).get("beat_pct", 0) or 0
    atr = latest.get("atr_pct", 0) or 0
    pe = val.get("trailing_pe", {}).get("current")
    risk_score = risk.get("risk_score", 0) or 0

    # 上行
    if tech.get("price", {}).get("alignment", {}).get("type") in ("strong_bullish", "bullish"):
        up.append("技术面多头排列，价格站上关键均线")
    if rev_yoy > 10: up.append(f"营收同比增长 {rev_yoy}%，高增速支撑")
    if eps_beat > 3: up.append(f"EPS 超预期 {eps_beat:.0f}%，盈利改善")
    if pe and pe < 30: up.append(f"PE {pe}，估值合理有安全边际")
    if flow.get("institutional", {}).get("trend") == "accumulating": up.append("机构资金持续增持")
    if not up: up.append("暂无明显上行催化，需等待突破信号")

    # 下行
    if atr > 5: down.append(f"ATR {atr}% 偏高，止损易触发")
    if eps_beat < 0: down.append("EPS 低于预期")
    if val.get("forward_pe", {}).get("value", 0) or 0 > 40: down.append("Forward PE 偏高")
    if risk_score >= 5: down.append(f"风险评分 {risk_score}/10")
    if sent.get("news", {}).get("direction") == "negative": down.append("新闻情绪偏负面")
    if not down: down.append("未检测到显著下行风险因子")

    # 证据
    key.append(f"收盘价 ${latest.get('close','N/A')}，MA20 {latest.get('ma20','N/A')}，RSI {latest.get('rsi14','N/A')}，ATR {atr}%")
    if fund.get("available"): key.append(f"营收 YoY {rev_yoy}%，EPS beat {eps_beat}%")
    key.append(f"风险评分 {risk_score}/10")
    if cat.get("available"): key.append(f"{cat.get('catalyst_count',0)} 个潜在催化剂")

    # 缺失
    if not fund.get("available"): missing.append("基本面数据不可用")
    if not flow.get("available"): missing.append("资金流数据不足")
    if not missing: missing.append("各维度数据基本齐全")

    # 观察
    watch.append(f"股价能否站稳 MA20 ({latest.get('ma20','N/A')})")
    watch.append(f"ATR 是否收敛（当前 {atr}%）")
    watch.append("下一季度财报的营收/利润率变化")
    watch.append("机构持仓趋势变化")
    watch.append("行业宏观政策变化")

    return up, down, key, missing, watch


def _build_cli_summary(result: Dict, report: Dict) -> str:
    """生成 CLI 风格的控制台摘要文本（带 emoji）。"""
    latest = result.get("latest", {})
    signals = result.get("signals", {})
    ri = result.get("research_inputs", {})
    ev = result.get("evidence", [])
    cal = result.get("calibration", {})
    sym = result.get("symbol", "?")
    tech = signals.get("technical", signals)
    fund = signals.get("fundamental", {})
    val = signals.get("valuation", {})
    cat = signals.get("catalyst", {})
    fl = signals.get("flow", {})
    rsk = signals.get("risk", {})

    lines = []
    a = lines.append
    a(f"\n\n---\n\n## CLI 控制台摘要\n\n```")
    a(f"{'='*60}")
    a(f"  {sym} 研究报告")
    a(f"{'='*60}")
    a(f"  时间: {result.get('as_of', '')[:19]}")
    a(f"  数据源: {result.get('source', 'N/A')}")
    a(f"  收盘价: ${latest.get('close', 0):.2f}")
    a("")

    # 均线
    a("  📊 均线:")
    a(f"     MA20:  ${latest['ma20']:.2f}" if latest.get('ma20') else "     MA20:  N/A")
    a(f"     MA50:  ${latest['ma50']:.2f}" if latest.get('ma50') else "     MA50:  N/A")
    a(f"     MA200: ${latest['ma200']:.2f}" if latest.get('ma200') else "     MA200: N/A")
    a(f"     判断: {tech['price']['description']}")
    a("")

    # 动量
    a("  📈 动量:")
    a(f"     RSI14: {latest.get('rsi14',0):.1f}" if latest.get('rsi14') else "     RSI14: N/A")
    a(f"     判断: {tech['momentum']['description']}")
    a("")

    # 波动率
    a("  📉 波动率:")
    a(f"     ATR14: {latest.get('atr14',0):.2f}" if latest.get('atr14') else "     ATR14: N/A")
    a(f"     ATR%:  {latest.get('atr_pct',0):.1f}%" if latest.get('atr_pct') else "     ATR%:  N/A")
    a(f"     判断: {tech['volatility']['description']}")
    a("")

    # 基本面
    if fund.get("available"):
        eps = fund.get("eps", {})
        rev = fund.get("revenue", {})
        a("  💰 基本面:")
        if eps:
            a(f"     EPS: 实际=${eps.get('actual',0):.2f} vs 预期=${eps.get('estimate',0):.2f} ({eps.get('status','')})")
        if rev:
            a(f"     营收: ${rev.get('actual_billion',0)}B vs ${rev.get('estimate_billion',0)}B ({rev.get('status','')})")
        a(f"     判断: {fund.get('description', '')}")
        a("")
    else:
        a("  💰 基本面: 数据不可用")
        a("")

    # 估值
    if val.get("available"):
        pe = val.get("trailing_pe", {})
        fwd = val.get("forward_pe", {})
        a("  🏷️ 估值:")
        if pe:
            a(f"     PE: {pe.get('current', 'N/A')} (历史 {pe.get('percentile', '?')}分位)")
        if fwd:
            a(f"     Forward PE: {fwd.get('value', 'N/A')}")
        a(f"     判断: {val.get('description', '')}")
        a("")
    else:
        a("  🏷️ 估值: 数据不可用")
        a("")

    # 催化剂
    if cat.get("available"):
        a(f"  📰 催化剂: {cat.get('description', '')}")
        a("")

    # 资金流
    if fl.get("available"):
        a(f"  💵 资金流: {fl.get('description', '')}")
        a("")

    # 风险
    if rsk.get("available"):
        a(f"  ⚠️ 风险评级: {rsk.get('description', '')}")
        a("")

    # Research Input
    a("  📋 Research Input 映射:")
    for k, v in ri.items():
        a(f"     {k} ({v['label']}): {v['assessment']}")
    a("")

    # Evidence
    a(f"  📎 Evidence: {len(ev)} 条")
    for e in ev:
        a(f"     [{e.get('confidence', '?')}] {e.get('claim', '')[:80]}")
    a("")

    # 校准
    if cal and cal.get("resolved_cases", 0) > 0:
        a(f"  📊 历史校准 (已结 {cal['resolved_cases']} 案例):")
        a(f"     Candidate 胜率: {cal.get('candidate_success_rate',0)}% {'✅ 高于盈亏平衡' if cal.get('above_balance') else '❌ 低于 33.3%'}")
        a(f"     +20% 先达率: {cal.get('upside_first_rate',0)}%  -10% 先达率: {cal.get('stop_loss_first_rate',0)}%")
        if cal.get('total_cases', 0) > cal.get('resolved_cases', 0):
            a(f"     待结案例: {cal['total_cases'] - cal['resolved_cases']}")
        a("")

    # 判断
    status_emoji = {"Candidate": "⭐", "Watch": "👀", "Reject": "❌", "Risk Alert": "⚠️"}.get(report.get("status", ""), "🤖")
    a(f"  {status_emoji} 判断: {report.get('status', 'Unknown')} (置信度: {report.get('confidence', 'N/A')})")

    lines.append("```")
    return "\n".join(lines)
