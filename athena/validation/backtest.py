"""历史回测引擎。

按 09_VALIDATION_AND_BACKTEST.md 规范：
对指定股票在历史时间窗口内逐月运行规则引擎，
180 天后验证 +20%/-10% 结果，生成真实 CaseRecord。
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

from athena.data.market_provider import LongbridgeMarketProvider
from athena.data.fundamental_provider import fetch_fundamentals
from athena.signals.technical import compute_technical_signals
from athena.signals.fundamentals import compute_fundamental_signals
from athena.signals.valuation import compute_valuation_signals
from athena.signals.risk import compute_risk_signals
from athena.probability import estimate_probability
from athena.probability.engine import _classify_status
from athena.validation import CaseRecord

logger = logging.getLogger(__name__)


def run_backtest(
    symbol: str,
    start_date: str = "2023-01-01",
    end_date: str = "2025-06-01",
    interval_months: int = 2,
    lookback_days: int = 250,
    forward_days: int = 180,
) -> List[CaseRecord]:
    """对单个股票在指定时间窗口内逐次回测。

    Args:
        symbol: 股票代码
        start_date: 回测起始日期
        end_date: 回测结束日期
        interval_months: 回测间隔（月）
        lookback_days: 每次回测使用的回看天数
        forward_days: 结果验证窗口（天）

    Returns:
        生成的 CaseRecord 列表
    """
    provider = LongbridgeMarketProvider()
    symbol = symbol.upper()

    # 获取完整历史数据
    full_df = provider.fetch_history(symbol, days=1200)  # ~5 年
    if full_df is None or len(full_df) < 60:
        logger.warning(f"{symbol}: 历史数据不足")
        return []

    # 生成测试日期列表
    dates = pd.date_range(start=start_date, end=end_date, freq=f"{interval_months}MS")
    cases: List[CaseRecord] = []

    for as_of in dates:
        as_of_str = as_of.strftime("%Y-%m-%d")
        # 截取 as_of 之前的数据
        mask = full_df["date"] <= as_of
        df_slice = full_df[mask].tail(lookback_days).reset_index(drop=True)

        if len(df_slice) < 30:
            continue

        price = float(df_slice["close"].iloc[-1])

        # 运行信号计算（规则引擎，不调 LLM）
        tech = compute_technical_signals(df_slice)
        fund_data = fetch_fundamentals(symbol)
        fund = compute_fundamental_signals(fund_data, price)
        val = compute_valuation_signals(fund_data, price)
        risk = compute_risk_signals(tech["signals"], fund["signals"], val["signals"])

        all_signals = {
            "technical": tech["signals"],
            "fundamental": fund["signals"],
            "valuation": val["signals"],
            "risk": risk["signals"],
        }

        prob = estimate_probability(all_signals, price)
        status = _classify_status(prob, all_signals)

        # 验证 180 天后结果
        future_mask = full_df["date"] >= as_of
        future = full_df[future_mask].head(forward_days)
        if len(future) < 20:
            continue  # 数据不足，跳过

        upside_target = round(price * 1.20, 2)
        downside_stop = round(price * 0.90, 2)

        upside_hit = None
        downside_hit = None
        max_price = price
        min_price = price

        for _, row in future.iterrows():
            high = float(row["high"])
            low = float(row["low"])
            max_price = max(max_price, high)
            min_price = min(min_price, low)
            if high >= upside_target and upside_hit is None:
                upside_hit = row["date"].strftime("%Y-%m-%d")
            if low <= downside_stop and downside_hit is None:
                downside_hit = row["date"].strftime("%Y-%m-%d")
            if upside_hit and downside_hit:
                break

        window_end = (as_of + timedelta(days=forward_days)).strftime("%Y-%m-%d")
        final_price = float(future["close"].iloc[-1]) if len(future) > 0 else price

        case = CaseRecord(
            case_id=f"{symbol}_BT_{as_of_str}",
            symbol=symbol,
            as_of_date=as_of_str,
            as_of_price=price,
            upside_target=upside_target,
            downside_stop=downside_stop,
            status_at_time=status,
            upside_hit_date=upside_hit,
            downside_hit_date=downside_hit,
            window_end_date=window_end,
            final_price=final_price,
            max_drawdown_pct=round((min_price / price - 1) * 100, 1),
            evidence_summary={
                "source": "backtest",
                "pe": val["signals"].get("trailing_pe", {}).get("current"),
                "risk_score": risk["signals"].get("risk_score"),
            },
            notes=f"auto-backtest {start_date} to {end_date}",
        )
        cases.append(case)
        logger.info(f"{symbol} {as_of_str}: price={price}, status={status}, "
                     f"upside_hit={upside_hit}, downside_hit={downside_hit}")

    return cases


def run_multi_backtest(
    symbols: List[str],
    start_date: str = "2023-01-01",
    end_date: str = "2025-06-01",
) -> List[CaseRecord]:
    """批量回测多个股票。"""
    all_cases = []
    for sym in symbols:
        cases = run_backtest(sym, start_date, end_date)
        all_cases.extend(cases)
        logger.info(f"{sym}: {len(cases)} cases generated")
    return all_cases
