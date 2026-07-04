"""技术面信号计算模块。

基于 OHLCV DataFrame 计算所有技术指标：
- adjusted_close
- MA20 / MA50 / MA200
- RSI14
- ATR14
- 20 日成交量均值
- 52 周高低点
- 相对基准指数强弱（SPY / QQQ）

输出映射到 Research Input 标签：
- TC-001 Price Trend
- TC-002 Moving Average Alignment
- TC-005 Volatility / ATR
- TC-006 Support / Resistance (52 周高低点)
- RK-010 Drawdown / Stop-loss Risk
"""

from typing import Dict, List, Optional

import numpy as np
import pandas as pd


def compute_ma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def compute_relative_strength(
    stock_close: pd.Series, benchmark_close: pd.Series, period: int = 60
) -> Optional[Dict]:
    """计算股票相对基准指数的强弱。

    Args:
        stock_close: 股票收盘价序列
        benchmark_close: 基准指数收盘价序列
        period: 比较窗口（交易日）

    Returns:
        {"pct_change_stock": float, "pct_change_benchmark": float,
         "relative": float, "description_zh": str} 或 None
    """
    min_len = min(len(stock_close), len(benchmark_close))
    days = min(period, min_len - 1)
    if days < 5:
        return None

    stock_ret = (stock_close.iloc[-1] / stock_close.iloc[-days] - 1) * 100
    bench_ret = (benchmark_close.iloc[-1] / benchmark_close.iloc[-days] - 1) * 100
    relative = round(stock_ret - bench_ret, 1)

    if relative > 10:
        zh = f"显著跑赢基准 (相对+{relative}%)，个股强势独立于大盘"
    elif relative > 3:
        zh = f"跑赢基准 (相对+{relative}%)，个股强于大盘"
    elif relative > -3:
        zh = f"与基准同步 (相对{relative:+}%)，无独立走势"
    elif relative > -10:
        zh = f"跑输基准 (相对{relative}%)，个股弱于大盘"
    else:
        zh = f"显著跑输基准 (相对{relative}%)，个股显著弱势"

    return {
        "stock_change_pct": round(stock_ret, 1),
        "benchmark_change_pct": round(bench_ret, 1),
        "relative": relative,
        "description_zh": zh,
    }


def compute_technical_signals(df: pd.DataFrame, benchmark_df: pd.DataFrame = None) -> Dict:
    """计算全部技术指标并返回结构化信号。

    Args:
        df: 含 date, open, high, low, close, adj_close, volume 的 DataFrame
        benchmark_df: 可选，基准指数 OHLCV（用于计算相对强弱）

    Returns:
        {"latest": {...}, "indicators": DataFrame, "signals": {...}, "research_inputs": {...}}
    """
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    ma20 = compute_ma(close, 20)
    ma50 = compute_ma(close, 50)
    ma200 = compute_ma(close, 200)
    rsi14 = compute_rsi(close, 14)
    atr14 = compute_atr(high, low, close, 14)
    vol_avg_20d = compute_ma(volume, 20)

    latest_close = float(close.iloc[-1])
    latest_ma20 = float(ma20.iloc[-1]) if not pd.isna(ma20.iloc[-1]) else None
    latest_ma50 = float(ma50.iloc[-1]) if not pd.isna(ma50.iloc[-1]) else None
    latest_ma200 = float(ma200.iloc[-1]) if not pd.isna(ma200.iloc[-1]) else None
    latest_rsi = float(rsi14.iloc[-1]) if not pd.isna(rsi14.iloc[-1]) else None
    latest_atr = float(atr14.iloc[-1]) if not pd.isna(atr14.iloc[-1]) else None
    latest_vol_avg = float(vol_avg_20d.iloc[-1]) if not pd.isna(vol_avg_20d.iloc[-1]) else None

    atr_pct = (latest_atr / latest_close * 100) if latest_atr and latest_close else None

    # 52 周高低点
    high_52w = float(high.tail(252).max()) if len(high) >= 5 else None
    low_52w = float(low.tail(252).min()) if len(low) >= 5 else None
    pct_from_high = round((latest_close - high_52w) / high_52w * 100, 1) if high_52w and latest_close else None
    pct_from_low = round((latest_close - low_52w) / low_52w * 100, 1) if low_52w and latest_close else None

    # 相对强弱（vs SPY）
    rel_spy = None
    if benchmark_df is not None and len(benchmark_df) >= 20:
        rel_spy = compute_relative_strength(close, benchmark_df["close"])

    # Volume Profile（成交量分布：近 60 日支撑/阻力）
    vol_profile = _compute_volume_profile(df.tail(60))
    # Market Structure（趋势结构：HH/HL/LH/LL）
    mkt_structure = _analyze_market_structure(high, low, close)

    # 分类判断
    alignment = _classify_alignment(latest_close, latest_ma20, latest_ma50, latest_ma200)
    trend = _classify_trend(close, ma20, ma50)
    rsi_status = _classify_rsi(latest_rsi)
    atr_stop_assessment = _assess_atr_stop(atr_pct)
    support_resistance = _classify_support_resistance(latest_close, high_52w, low_52w)

    latest = {
        "close": latest_close,
        "ma20": latest_ma20,
        "ma50": latest_ma50,
        "ma200": latest_ma200,
        "rsi14": latest_rsi,
        "atr14": latest_atr,
        "atr_pct": round(atr_pct, 2) if atr_pct else None,
        "volume_avg_20d": latest_vol_avg,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "pct_from_high": pct_from_high,
        "pct_from_low": pct_from_low,
    }

    signals = {
        "price": {
            "close": latest_close, "ma20": latest_ma20, "ma50": latest_ma50, "ma200": latest_ma200,
            "high_52w": high_52w, "low_52w": low_52w,
            "alignment": alignment, "description": alignment["description_zh"],
        },
        "momentum": {"rsi14": latest_rsi, "status": rsi_status, "description": rsi_status["description_zh"]},
        "volatility": {"atr14": latest_atr, "atr_pct": round(atr_pct, 2) if atr_pct else None,
            "atr_stop_assessment": atr_stop_assessment, "description": atr_stop_assessment["description_zh"]},
        "volume": {"latest": int(volume.iloc[-1]), "avg_20d": int(latest_vol_avg) if latest_vol_avg else None,
            "volume_ratio": (round(float(volume.iloc[-1]) / latest_vol_avg, 2) if latest_vol_avg and latest_vol_avg > 0 else None)},
        "support_resistance": {"high_52w": high_52w, "low_52w": low_52w,
            "pct_from_high": pct_from_high, "pct_from_low": pct_from_low,
            "status": support_resistance["status"], "description": support_resistance["description_zh"]},
        "relative_strength": rel_spy,
    }



    research_inputs = {
        "TC-001": {
            "label": "Price Trend",
            "claim": f"Close {latest_close} vs MA20={latest_ma20}, MA50={latest_ma50}, MA200={latest_ma200}",
            "assessment": trend["description_zh"],
        },
        "TC-002": {
            "label": "Moving Average Alignment",
            "claim": alignment["description_zh"],
            "assessment": "Bullish" if alignment["bullish"] else "Bearish",
        },
        "TC-005": {
            "label": "Volatility / ATR",
            "claim": f"ATR14={latest_atr}, ATR%={atr_pct}%",
            "assessment": atr_stop_assessment["description_zh"],
        },
        "TC-006": {
            "label": "Support / Resistance",
            "claim": f"52W High={high_52w}, 52W Low={low_52w}, "
                     f"距高点{pct_from_high}%, 距低点{pct_from_low}%",
            "assessment": support_resistance["description_zh"],
        },
        "TC-007": {
            "label": "Volume Profile",
            "claim": vol_profile["description_zh"] if vol_profile else "数据不足",
            "assessment": (
                "Distribution (顶部放量)" if (vol_profile and vol_profile.get("zone") == "distribution")
                else "Accumulation (底部放量)" if (vol_profile and vol_profile.get("zone") == "accumulation")
                else "Neutral" if vol_profile else "N/A"
            ),
        },
        "TC-008": {
            "label": "Market Structure",
            "claim": mkt_structure["description_zh"] if mkt_structure else "数据不足",
            "assessment": (
                "Uptrend" if (mkt_structure and mkt_structure.get("trend") == "uptrend")
                else "Downtrend" if (mkt_structure and mkt_structure.get("trend") == "downtrend")
                else "Sideways" if mkt_structure else "N/A"
            ),
        },
        "RS-001": {
            "label": "Relative Strength vs SPY",
            "claim": rel_spy["description_zh"] if rel_spy else "基准数据不足",
            "assessment": (
                "Outperform" if (rel_spy and rel_spy["relative"] > 0)
                else "Underperform" if rel_spy else "N/A"
            ),
        },
        "RK-010": {
            "label": "Drawdown / Stop-loss Risk",
            "claim": f"ATR%={atr_pct}%, -10% stop: "
                     f"{'feasible' if atr_stop_assessment.get('stop_loss_feasible') else 'at risk'}",
            "assessment": atr_stop_assessment["description_zh"],
        },
    }

    indicators = pd.DataFrame({
        "date": df["date"],
        "close": close,
        "ma20": ma20,
        "ma50": ma50,
        "ma200": ma200,
        "rsi14": rsi14,
        "atr14": atr14,
        "vol_avg_20d": vol_avg_20d,
    })

    return {
        "latest": latest,
        "indicators": indicators,
        "signals": signals,
        "research_inputs": research_inputs,
    }


# ---- 分类辅助函数 ----

def _classify_alignment(close, ma20, ma50, ma200) -> Dict:
    if any(v is None for v in [close, ma20, ma50, ma200]):
        return {"bullish": False, "type": "insufficient_data", "description_zh": "均线数据不足"}

    above_all = close > ma20 and close > ma50 and close > ma200
    golden = ma20 > ma50 > ma200
    death = ma20 < ma50 < ma200

    if above_all and golden:
        return {"bullish": True, "type": "strong_bullish",
                "description_zh": f"强势多头排列：价格站上所有均线，MA20({ma20:.1f}) > MA50({ma50:.1f}) > MA200({ma200:.1f})"}
    elif above_all:
        return {"bullish": True, "type": "bullish", "description_zh": "价格站上所有均线，但均线尚未完全多头排列"}
    elif death:
        return {"bullish": False, "type": "bearish",
                "description_zh": f"空头排列：MA20({ma20:.1f}) < MA50({ma50:.1f}) < MA200({ma200:.1f})"}
    elif close < ma200:
        return {"bullish": False, "type": "below_ma200",
                "description_zh": f"价格低于 MA200({ma200:.1f})，长期趋势偏弱"}
    else:
        return {"bullish": None, "type": "mixed", "description_zh": "均线交错，趋势不明确"}


def _classify_trend(close, ma20, ma50) -> Dict:
    if len(close) < 20:
        return {"direction": "unknown", "description_zh": "数据不足"}

    pct_5d = (close.iloc[-1] / close.iloc[-5] - 1) * 100 if len(close) >= 5 else 0
    pct_20d = (close.iloc[-1] / close.iloc[-20] - 1) * 100
    above_ma20 = close.iloc[-1] > ma20.iloc[-1] if not pd.isna(ma20.iloc[-1]) else False
    above_ma50 = close.iloc[-1] > ma50.iloc[-1] if not pd.isna(ma50.iloc[-1]) else False

    if pct_5d > 3 and above_ma20:
        return {"direction": "strong_up", "description_zh": f"近期强势上涨 (5日 +{pct_5d:.1f}%)，站上 MA20"}
    elif pct_20d > 0 and above_ma20:
        return {"direction": "up", "description_zh": f"趋势向上 (20日 +{pct_20d:.1f}%)"}
    elif pct_20d < -5:
        return {"direction": "down", "description_zh": f"趋势走弱 (20日 {pct_20d:.1f}%)"}
    elif not above_ma50:
        return {"direction": "weak", "description_zh": "价格低于 MA50，趋势偏弱"}
    else:
        return {"direction": "sideways", "description_zh": "横盘整理，无明显方向"}


def _classify_rsi(rsi) -> Dict:
    if rsi is None:
        return {"status": "unknown", "description_zh": "RSI 数据不足"}
    if rsi > 70:
        return {"status": "overbought", "description_zh": f"RSI={rsi:.1f}，超买区域，短期回调风险"}
    elif rsi > 60:
        return {"status": "strong", "description_zh": f"RSI={rsi:.1f}，偏强，仍有上行空间"}
    elif rsi > 40:
        return {"status": "neutral", "description_zh": f"RSI={rsi:.1f}，中性区域"}
    elif rsi > 30:
        return {"status": "weak", "description_zh": f"RSI={rsi:.1f}，偏弱，关注是否企稳"}
    else:
        return {"status": "oversold", "description_zh": f"RSI={rsi:.1f}，超卖区域，可能出现反弹"}


def _assess_atr_stop(atr_pct) -> Dict:
    if atr_pct is None:
        return {"stop_loss_feasible": None, "description_zh": "ATR 数据不足"}
    if atr_pct < 2.0:
        return {"stop_loss_feasible": True, "description_zh": f"ATR%={atr_pct:.1f}%，波动率低，-10% 止损不容易被噪音触发"}
    elif atr_pct < 3.5:
        return {"stop_loss_feasible": True, "description_zh": f"ATR%={atr_pct:.1f}%，波动率适中，-10% 止损有一定缓冲空间"}
    elif atr_pct < 5.0:
        return {"stop_loss_feasible": False, "description_zh": f"ATR%={atr_pct:.1f}%，波动率偏高，-10% 止损可能被日常波动触发"}
    else:
        return {"stop_loss_feasible": False, "description_zh": f"ATR%={atr_pct:.1f}%，波动率很高，-10% 止损极易被触发"}


def _classify_support_resistance(close, high_52w, low_52w) -> Dict:
    if close is None or high_52w is None or low_52w is None:
        return {"status": "unknown", "description_zh": "52 周数据不足"}

    pct_from_high = (close - high_52w) / high_52w * 100
    pct_from_low = (close - low_52w) / low_52w * 100

    if pct_from_high > -3:
        return {"status": "near_high", "description_zh": f"股价接近 52 周高点 (${high_52w:.1f})，距离仅 {pct_from_high:.1f}%"}
    elif pct_from_low < 10:
        return {"status": "near_low", "description_zh": f"股价接近 52 周低点 (${low_52w:.1f})，仅高出 {pct_from_low:.1f}%"}
    elif pct_from_high < -15:
        return {"status": "far_from_high", "description_zh": f"股价距 52 周高点较远 ({pct_from_high:.1f}%)，上方阻力需关注"}
    else:
        return {"status": "mid_range",
                "description_zh": f"股价位于 52 周区间的中间位置，距高点 {pct_from_high:.1f}%，距低点 +{pct_from_low:.1f}%"}


# ---- Volume Profile ----

def _compute_volume_profile(df_tail):
    """计算近 60 日成交量分布，判断支撑/阻力区域。"""
    if len(df_tail) < 10:
        return None
    close = df_tail["close"]
    volume = df_tail["volume"]
    current = float(close.iloc[-1])
    # 分 5 个价格区间
    price_bins = pd.cut(close, bins=5)
    vol_per_bin = volume.groupby(price_bins, observed=False).sum()
    # 找到最大成交量区间
    max_bin = vol_per_bin.idxmax()
    max_vol_pct = float(vol_per_bin.max() / vol_per_bin.sum() * 100)
    # 判断当前价格相对于量能区的位罝
    bin_mid = (max_bin.left + max_bin.right) / 2
    if current > bin_mid:
        zone = "distribution"  # 当前价高于高量区 → 可能套牢盘
    elif current < bin_mid:
        zone = "accumulation"  # 当前价低于高量区 → 可能支撑
    else:
        zone = "neutral"
    if zone == "distribution":
        desc = f"价格位于成交量密集区上方 (高量占比 {max_vol_pct:.0f}%)，存在套牢盘压力"
    elif zone == "accumulation":
        desc = f"价格位于成交量密集区下方 (高量占比 {max_vol_pct:.0f}%)，存在支撑"
    else:
        desc = f"价格位于成交量密集区内 (高量占比 {max_vol_pct:.0f}%)"
    return {"zone": zone, "max_vol_pct": round(max_vol_pct, 1), "description_zh": desc}


# ---- Market Structure ----

def _analyze_market_structure(high, low, close):
    """分析最近 20 根 K 线的趋势结构（HH/HL/LH/LL）。"""
    if len(close) < 20:
        return None
    h = list(high.iloc[-20:])
    l = list(low.iloc[-20:])
    # 找局部极值（每 5 根一个 swing point）
    swing_highs = []
    swing_lows = []
    for i in range(2, 18):
        if h[i] > h[i-1] and h[i] > h[i-2] and h[i] > h[i+1] and h[i] > h[i+2]:
            swing_highs.append(h[i])
        if l[i] < l[i-1] and l[i] < l[i-2] and l[i] < l[i+1] and l[i] < l[i+2]:
            swing_lows.append(l[i])
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return None
    # 判断 HH/HL 和 LH/LL
    hh = swing_highs[-1] > swing_highs[-2]
    hl = swing_lows[-1] > swing_lows[-2]
    if hh and hl:
        trend, desc = "uptrend", "上升趋势 (Higher High + Higher Low)"
    elif not hh and not hl:
        trend, desc = "downtrend", "下降趋势 (Lower High + Lower Low)"
    else:
        trend, desc = "sideways", "震荡格局 (无明确 HH/HL 或 LH/LL)"
    return {"trend": trend, "description_zh": desc}
