# 06 Longbridge / LongPort 接入规划

## 1. 目标

Athena 使用 Longbridge / LongPort 相关能力作为行情、基本面、市场与内容数据来源之一。

LongPort Python SDK 提供多个 Context 类型，包括 QuoteContext、TradeContext、ContentContext、FundamentalContext、MarketContext、CalendarContext 等。Athena 第一阶段只应使用只读研究能力，不应使用交易能力。

## 2. 接入原则

1. 只读优先。
2. 不自动交易。
3. 不调用下单接口。
4. 所有 Longbridge 数据必须转成 Evidence。
5. Provider 不做研究判断。

## 3. 第一阶段接入范围

### Quote / Market Data

用途：

- OHLCV
- adjusted close
- 实时/历史行情
- 技术指标计算

目标 Research Inputs：

- TC-001 Price Trend
- TC-002 Moving Average Alignment
- TC-005 Volatility / ATR
- TC-006 Support / Resistance
- RK-010 Drawdown / Stop-loss Risk

### Fundamental Data

用途：

- 财报
- 估值
- 分析师评级
- 股息
- 公司概览
- 股东信息

目标 Research Inputs：

- BQ-001 Revenue
- BQ-002 Gross Margin
- VL-001 Trailing PE
- VL-002 Forward PE
- GR-004 Estimate Revision

### Content / News / Community

用途：

- 新闻
- 社区讨论
- 热门主题

目标 Research Inputs：

- CA-010 Theme Acceleration
- sentiment / retail attention
- catalyst evidence

### Market Context

用途：

- 经纪商持仓
- 市场状态
- 异动提醒
- 指数成分

目标 Research Inputs：

- ETF / broker flow
- market regime
- positioning

## 4. 禁止接入范围

第一阶段禁止：

- 自动下单
- 改仓
- 融资融券操作
- 期权自动交易
- 任何 broker execution

## 5. Provider 输出格式

Longbridge Provider 输出必须统一为 Evidence：

```json
{
  "provider": "longbridge",
  "symbol": "NVDA",
  "as_of": "2026-07-02T09:30:00Z",
  "evidence_type": "market_price",
  "claim": "NVDA is above MA20 and MA50",
  "metrics": {
    "close": 123.45,
    "ma20": 118.2,
    "ma50": 112.6
  },
  "confidence": "High"
}
```

## 6. Implementation Notes

建议先实现：

1. `LongbridgeMarketProvider`
2. `LongbridgeFundamentalProvider`
3. `LongbridgeContentProvider`

但第一版只做 `LongbridgeMarketProvider`。

## 7. 安全边界

配置文件必须读取环境变量：

```text
LONGBRIDGE_APP_KEY
LONGBRIDGE_APP_SECRET
LONGBRIDGE_ACCESS_TOKEN
```

不得把密钥写入代码或输出报告。
