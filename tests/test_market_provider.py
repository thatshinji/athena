"""测试市场 Provider（fixture 模式）"""

import pytest
from athena.data.market_provider import LongbridgeMarketProvider


class TestMarketProvider:
    def test_fetch_nvda(self):
        p = LongbridgeMarketProvider()
        df = p.fetch_history("NVDA", 250)
        assert df.shape[0] == 250
        assert list(df.columns) == [
            "date", "open", "high", "low", "close", "adj_close", "volume"
        ]
        assert df["close"].iloc[-1] > 0

    def test_fetch_aapl(self):
        p = LongbridgeMarketProvider()
        df = p.fetch_history("AAPL", 100)
        assert df.shape[0] == 100
        assert df["close"].iloc[-1] > 0

    def test_any_symbol_works(self):
        """任意美股代码应能生成有效 fixture 数据"""
        p = LongbridgeMarketProvider()
        # 之前不支持的代码现在也能工作
        df = p.fetch_history("CBRS", 30)
        assert df.shape[0] == 30
        assert df["close"].iloc[-1] > 0
        assert list(df.columns) == [
            "date", "open", "high", "low", "close", "adj_close", "volume"
        ]

    def test_derived_symbol_deterministic(self):
        """hash 推导的符号每次应生成相同数据"""
        p1 = LongbridgeMarketProvider()
        df1 = p1.fetch_history("TSLA", 30)
        p2 = LongbridgeMarketProvider()
        df2 = p2.fetch_history("TSLA", 30)
        assert df1["close"].iloc[-1] == df2["close"].iloc[-1]

    def test_reproducible(self):
        """两次调用应生成相同数据（固定随机种子）"""
        p1 = LongbridgeMarketProvider()
        df1 = p1.fetch_history("NVDA", 30)
        p2 = LongbridgeMarketProvider()
        df2 = p2.fetch_history("NVDA", 30)
        assert df1["close"].iloc[-1] == df2["close"].iloc[-1]
