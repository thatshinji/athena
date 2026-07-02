"""行情 Provider — 多数据源自动降级。

优先级：Longbridge SDK → yfinance → fixture
不调用交易接口。
"""

import concurrent.futures
import logging
import os
from dataclasses import dataclass
from datetime import date, timedelta
from threading import Lock
from typing import Optional

import numpy as np
import pandas as pd

from athena.config import settings

logger = logging.getLogger(__name__)

# ---- 禁用系统代理（macOS 系统代理未运行时会阻断所有 requests 流量） ----
os.environ.setdefault("no_proxy", "*")
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)

# ---- Longbridge SDK 单例缓存 ----

_sdk_lock = Lock()
_sdk_ctx = None
_sdk_available: Optional[bool] = None


def _init_sdk_once():
    """初始化 Longbridge SDK（带 5 秒超时保护），结果进程级缓存。"""
    global _sdk_ctx, _sdk_available

    if _sdk_available is not None:
        return

    with _sdk_lock:
        if _sdk_available is not None:
            return

        def _do_init():
            from longbridge.openapi import Config, QuoteContext
            config = Config.from_apikey_env()
            ctx = QuoteContext(config)
            ctx.trading_session()
            return ctx

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_do_init)
                _sdk_ctx = future.result(timeout=5)
                _sdk_available = True
                logger.info("Longbridge SDK 初始化成功")
        except concurrent.futures.TimeoutError:
            logger.warning(
                f"Longbridge SDK 连接超时 ({settings.longbridge_http_url})"
            )
            _sdk_ctx = None
            _sdk_available = False
        except Exception as e:
            err_msg = str(e)
            if "Connect" in err_msg or "timeout" in err_msg.lower():
                logger.warning(
                    f"Longbridge SDK 网络不可达 ({settings.longbridge_http_url}): {err_msg[:100]}"
                )
            elif any(k in err_msg for k in ("Unauthorized", "Auth", "auth")):
                logger.warning(f"Longbridge SDK 认证失败: {err_msg[:100]}")
            else:
                logger.warning(f"Longbridge SDK 不可用: {e}")
            _sdk_ctx = None
            _sdk_available = False


# ---- yfinance 可用性缓存 ----

_yf_lock = Lock()
_yf_available: Optional[bool] = None


def _check_yfinance():
    """检测 yfinance 是否可用（结果进程级缓存）。"""
    global _yf_available
    if _yf_available is not None:
        return _yf_available

    with _yf_lock:
        if _yf_available is not None:
            return _yf_available
        try:
            import yfinance as yf

            # 快速连接测试
            ticker = yf.Ticker("AAPL")
            hist = ticker.history(period="5d")
            if hist is not None and len(hist) > 0:
                _yf_available = True
                logger.info("yfinance 可用，将作为行情数据源")
            else:
                _yf_available = False
                logger.warning("yfinance 返回空数据，不可用")
        except Exception as e:
            _yf_available = False
            logger.warning(f"yfinance 不可用: {e}")
        return _yf_available


@dataclass
class OHLCV:
    """OHLCV 数据结构"""
    symbol: str
    as_of: date
    open: float
    high: float
    low: float
    close: float
    adj_close: float
    volume: int


class LongbridgeMarketProvider:
    """多数据源行情提供者。

    降级策略：
    1. Longbridge SDK（真实行情）
    2. yfinance（Yahoo Finance，免费无需 key）
    3. fixture（合成数据兜底）

    SDK 和 yfinance 检测结果进程级缓存。
    """

    def __init__(self):
        _init_sdk_once()

    @property
    def data_source(self) -> str:
        """当前使用的数据源名称"""
        if _sdk_available:
            return "longbridge"
        if _check_yfinance():
            return "yfinance"
        return "fixture"

    def fetch_history(self, symbol: str, days: int = 250) -> pd.DataFrame:
        """拉取日线 OHLCV 历史数据。

        依次尝试 Longbridge → yfinance → fixture。
        """
        symbol = symbol.upper()

        # 1. Longbridge SDK
        if _sdk_available:
            try:
                df = self._fetch_from_longbridge(symbol, days)
                logger.info(f"{symbol}: 数据来源 = longbridge (真实行情)")
                return df
            except Exception as e:
                logger.warning(f"Longbridge 拉取 {symbol} 失败: {e}")

        # 2. yfinance
        if _check_yfinance():
            try:
                df = self._fetch_from_yfinance(symbol, days)
                if df is not None and len(df) > 0:
                    logger.info(f"{symbol}: 数据来源 = yfinance (真实行情)")
                    return df
            except Exception as e:
                logger.warning(f"yfinance 拉取 {symbol} 失败: {e}")

        # 3. fixture 兜底
        logger.info(f"{symbol}: 数据来源 = fixture (合成数据)")
        return self._fetch_from_fixture(symbol, days)

    # ---- Longbridge ----

    def _fetch_from_longbridge(self, symbol: str, days: int) -> pd.DataFrame:
        from datetime import date as dt_date
        from longbridge.openapi import Period, AdjustType

        symbol_full = f"{symbol}.US"
        end_date = dt_date.today()
        start_date = end_date - timedelta(days=days * 2)

        candles = _sdk_ctx.history_candlesticks_by_date(
            symbol_full, Period.Day, AdjustType.ForwardAdjust, start_date, end_date
        )

        records = [
            {
                "date": pd.Timestamp(c.timestamp).date(),
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "adj_close": float(c.close),
                "volume": int(c.volume),
            }
            for c in candles
        ]
        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").tail(days).reset_index(drop=True)

    # ---- yfinance ----

    def _fetch_from_yfinance(self, symbol: str, days: int) -> Optional[pd.DataFrame]:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        # yfinance period 不支持任意天数，取略大于 days 的周期
        if days <= 60:
            period = "3mo"
        elif days <= 120:
            period = "6mo"
        elif days <= 250:
            period = "1y"
        else:
            period = "2y"

        hist = ticker.history(period=period)
        if hist is None or hist.empty:
            return None

        # 标准化为统一列名
        hist = hist.reset_index()
        hist = hist.rename(columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        })
        # yfinance 的 Close 已是 adjusted
        hist["adj_close"] = hist["close"]
        hist = hist[["date", "open", "high", "low", "close", "adj_close", "volume"]]
        hist["date"] = pd.to_datetime(hist["date"]).dt.tz_localize(None)

        return hist.sort_values("date").tail(days).reset_index(drop=True)

    # ---- fixture ----

    def _fetch_from_fixture(self, symbol: str, days: int) -> pd.DataFrame:
        symbol = symbol.upper()

        if symbol in _FIXTURE_SEEDS:
            seed = _FIXTURE_SEEDS[symbol]
        else:
            seed = _derive_seed(symbol)
            logger.info(
                f"Fixture 使用推导参数 ({symbol}): "
                f"base_price={seed['base_price']:.0f}, "
                f"volatility={seed['volatility']:.3f}"
            )

        return _generate_fixture(symbol, days, **seed)


# ---- Fixture 生成器 ----

_FIXTURE_SEEDS = {
    "NVDA": {
        "base_price": 78.0,
        "trend": 0.0012,
        "volatility": 0.028,
        "volume_avg": 45_000_000,
        "rng_seed": 42001,
    },
    "AAPL": {
        "base_price": 190.0,
        "trend": 0.0006,
        "volatility": 0.015,
        "volume_avg": 58_000_000,
        "rng_seed": 42002,
    },
}


def _derive_seed(symbol: str) -> dict:
    """通过符号名 hash 确定性推导 fixture 种子参数。"""
    import hashlib

    h = hashlib.sha256(symbol.encode()).digest()
    parts = [int.from_bytes(h[i : i + 4], "big") for i in range(0, 32, 4)]

    def _unorm(p: int, lo: float, hi: float) -> float:
        return lo + (p / 0xFFFFFFFF) * (hi - lo)

    return {
        "base_price": round(_unorm(parts[0], 10.0, 500.0), 2),
        "trend": round(_unorm(parts[1], -0.0005, 0.0015), 4),
        "volatility": round(_unorm(parts[2], 0.012, 0.040), 3),
        "volume_avg": int(_unorm(parts[3], 500_000, 80_000_000)),
        "rng_seed": parts[4] % (2**31),
    }


def _generate_fixture(
    symbol: str,
    days: int,
    base_price: float,
    trend: float,
    volatility: float,
    volume_avg: int,
    rng_seed: int = 42,
) -> pd.DataFrame:
    """生成符合美股统计特征的合成日线数据。"""
    rng = np.random.RandomState(rng_seed)

    returns = rng.normal(trend, volatility, days)
    event_days = rng.choice(days, size=max(1, days // 60), replace=False)
    returns[event_days] += rng.choice([-1, 1], len(event_days)) * rng.uniform(
        0.03, 0.08, len(event_days)
    )

    prices = base_price * np.exp(np.cumsum(returns))
    end_date = date.today()
    records = []
    business_days = 0
    current = end_date - timedelta(days=days * 2)

    while business_days < days:
        current += timedelta(days=1)
        if current.weekday() >= 5:
            continue
        if current > end_date:
            break

        i = business_days
        close = round(prices[i], 2)
        daily_range = close * rng.uniform(0.008, 0.025)
        open_price = round(close * (1 + rng.uniform(-0.005, 0.005)), 2)
        high = round(max(open_price, close) + daily_range * rng.uniform(0.3, 0.7), 2)
        low = round(min(open_price, close) - daily_range * rng.uniform(0.3, 0.7), 2)
        low = max(low, 1.0)
        volume = int(volume_avg * rng.uniform(0.5, 2.0))

        records.append({
            "date": current,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "adj_close": close,
            "volume": volume,
        })
        business_days += 1

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)
