"""Athena CLI — 命令行入口

用法:
    python -m athena run NVDA              # 技术面 + Evidence
    python -m athena run NVDA --report     # 技术面 + Evidence + LLM 中文报告
    python -m athena run AAPL --json       # JSON 输出
"""

import argparse
import json
import sys

from athena.reports.chinese_report import generate_report


def print_summary(result: dict):
    """打印中文摘要"""
    symbol = result["symbol"]
    latest = result["latest"]
    signals = result["signals"]
    tech = signals.get("technical", signals)
    fund = signals.get("fundamental", {})
    val = signals.get("valuation", {})
    ri = result["research_inputs"]

    print(f"\n{'='*60}")
    print(f"  {symbol} 研究报告")
    print(f"{'='*60}")
    print(f"  时间: {result['as_of'][:19]}")
    if result.get('source'):
        print(f"  数据源: {result['source']}")
    print(f"  收盘价: ${latest['close']:.2f}")
    print()

    print(f"  📊 均线:")
    print(f"     MA20:  ${latest['ma20']:.2f}" if latest.get('ma20') else "     MA20:  N/A")
    print(f"     MA50:  ${latest['ma50']:.2f}" if latest.get('ma50') else "     MA50:  N/A")
    print(f"     MA200: ${latest['ma200']:.2f}" if latest.get('ma200') else "     MA200: N/A")
    print(f"     判断: {tech['price']['description']}")
    print()

    print(f"  📈 动量:")
    print(f"     RSI14: {latest['rsi14']:.1f}" if latest.get('rsi14') else "     RSI14: N/A")
    print(f"     判断: {tech['momentum']['description']}")
    print()

    print(f"  📉 波动率:")
    print(f"     ATR14: {latest['atr14']:.2f}" if latest.get('atr14') else "     ATR14: N/A")
    print(f"     ATR%:  {latest['atr_pct']:.1f}%" if latest.get('atr_pct') else "     ATR%:  N/A")
    print(f"     判断: {tech['volatility']['description']}")
    print()

    # 基本面
    if fund.get("available"):
        eps = fund.get("eps", {})
        rev = fund.get("revenue", {})
        print(f"  💰 基本面:")
        if eps:
            print(f"     EPS: 实际=${eps.get('actual',0):.2f} vs 预期=${eps.get('estimate',0):.2f} ({eps.get('status','')})")
        if rev:
            print(f"     营收: ${rev.get('actual_billion',0)}B vs ${rev.get('estimate_billion',0)}B ({rev.get('status','')})")
        print(f"     判断: {fund.get('description', '')}")
        print()
    else:
        print(f"  💰 基本面: 数据不可用")
        print()

    # 估值
    if val.get("available"):
        pe = val.get("trailing_pe", {})
        fwd = val.get("forward_pe", {})
        print(f"  🏷️ 估值:")
        if pe:
            print(f"     PE: {pe.get('current', 'N/A')} (历史 {pe.get('percentile', '?')}分位)")
        if fwd:
            print(f"     Forward PE: {fwd.get('value', 'N/A')}")
        print(f"     判断: {val.get('description', '')}")
        print()
    else:
        print(f"  🏷️ 估值: 数据不可用")
        print()

    # 催化剂
    cat = signals.get("catalyst", {})
    if cat.get("available"):
        print(f"  📰 催化剂: {cat.get('description', '')}")
        print()

    # 资金流
    fl = signals.get("flow", {})
    if fl.get("available"):
        print(f"  💵 资金流: {fl.get('description', '')}")
        print()

    # 风险
    rsk = signals.get("risk", {})
    if rsk.get("available"):
        print(f"  ⚠️ 风险评级: {rsk.get('description', '')}")
        print()

    print(f"  📋 Research Input 映射:")
    for k, v in ri.items():
        print(f"     {k} ({v['label']}): {v['assessment']}")
    print()

    print(f"  📎 Evidence: {len(result['evidence'])} 条")
    for e in result["evidence"]:
        print(f"     [{e['confidence']}] {e['claim'][:80]}")
    print()

    # 校准指标
    cal = result.get("calibration")
    if cal and cal.get("status") != "insufficient_data":
        print(f"  📊 历史校准 (已结 {cal.get('resolved_cases', 0)} 案例):")
        print(f"     Candidate 胜率: {cal.get('candidate_success_rate', 0)}% "
              f"({'✅ 高于盈亏平衡' if cal.get('above_balance') else '❌ 低于 33.3%'} )")
        print(f"     +20% 先达率: {cal.get('upside_first_rate', 0)}%  "
              f"-10% 先达率: {cal.get('stop_loss_first_rate', 0)}%")
        if cal.get("total_cases", 0) > cal.get("resolved_cases", 0):
            print(f"     待结案例: {cal['total_cases'] - cal['resolved_cases']}")
        print()

    # 判断结论
    if result.get("report"):
        report_status = result["report"].get("status", "Unknown")
        status_emoji = {"Candidate": "⭐", "Watch": "👀", "Reject": "❌", "Risk Alert": "⚠️"}.get(report_status, "🤖")
        print(f"  {status_emoji} 判断: {report_status} (置信度: {result['report'].get('confidence', 'N/A')})")
        report_path = result.get("report_path")
        if report_path:
            print(f"  📄 报告已保存: {report_path}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Athena — AI 投资研究系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m athena run NVDA
  python -m athena run NVDA --report
  python -m athena run AAPL --json
        """,
    )
    sub = parser.add_subparsers(dest="command", help="子命令")

    run_parser = sub.add_parser("run", help="运行研究")
    run_parser.add_argument("symbol", help="股票代码（如 NVDA, AAPL）")
    run_parser.add_argument(
        "--days", type=int, default=250, help="交易日数（默认 250）"
    )
    run_parser.add_argument(
        "--report", action="store_true", help="生成 LLM 中文研究报告"
    )
    run_parser.add_argument(
        "--json", action="store_true", help="输出完整 JSON"
    )

    args = parser.parse_args()

    if args.command != "run":
        parser.print_help()
        sys.exit(1)

    try:
        result = generate_report(
            args.symbol, days=args.days, use_llm=args.report
        )
    except ValueError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        print_summary(result)


if __name__ == "__main__":
    main()
