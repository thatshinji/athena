"""测试技术指标计算"""

import numpy as np
import pandas as pd
import pytest
from athena.data.market_provider import LongbridgeMarketProvider
from athena.signals.technical import (
    compute_technical_signals,
    compute_ma,
    compute_rsi,
    compute_atr,
)


class TestTechnicalIndicators:
    @pytest.fixture
    def df(self):
        p = LongbridgeMarketProvider()
        return p.fetch_history("NVDA", 250)

    @pytest.fixture
    def result(self, df):
        return compute_technical_signals(df)

    def test_ma_computation(self, df):
        ma20 = compute_ma(df["close"], 20)
        assert not pd.isna(ma20.iloc[-1])
        assert ma20.iloc[-1] > 0

    def test_rsi_computation(self, df):
        rsi = compute_rsi(df["close"], 14)
        assert not pd.isna(rsi.iloc[-1])
        assert 0 <= rsi.iloc[-1] <= 100

    def test_atr_computation(self, df):
        atr = compute_atr(df["high"], df["low"], df["close"], 14)
        assert not pd.isna(atr.iloc[-1])
        assert atr.iloc[-1] > 0

    def test_result_latest_fields(self, result):
        latest = result["latest"]
        assert latest["close"] > 0
        assert latest["ma20"] > 0
        assert latest["ma50"] > 0
        assert latest["ma200"] > 0
        assert 0 <= latest["rsi14"] <= 100
        assert latest["atr14"] > 0
        assert latest["atr_pct"] is not None

    def test_research_inputs_present(self, result):
        ri = result["research_inputs"]
        assert "TC-001" in ri
        assert "TC-002" in ri
        assert "TC-005" in ri
        assert "TC-006" in ri
        assert "RK-010" in ri
        for k, v in ri.items():
            assert "claim" in v
            assert "assessment" in v

    def test_signals_structure(self, result):
        signals = result["signals"]
        assert "price" in signals
        assert "momentum" in signals
        assert "volatility" in signals
        assert "volume" in signals

    def test_indicators_dataframe(self, result):
        df = result["indicators"]
        assert "ma20" in df.columns
        assert "ma50" in df.columns
        assert "ma200" in df.columns
        assert "rsi14" in df.columns
        assert "atr14" in df.columns

    def test_rsi_range_simple(self):
        """简单固定数据测试 RSI"""
        prices = pd.Series([10, 11, 12, 11, 10, 9, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17])
        rsi = compute_rsi(prices, 14)
        assert rsi.iloc[-1] > 50  # 明显上涨趋势

    def test_ma_simple(self):
        prices = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        ma3 = compute_ma(prices, 3)
        assert ma3.iloc[2] == 2.0
        assert ma3.iloc[9] == 9.0
