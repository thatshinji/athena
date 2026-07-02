# 03 数据源与证据契约

## 1. 数据源优先级

Athena 应优先接入直接影响 +20% / -10% 判断的数据。

## 2. 第一优先级：行情与技术面

用途：判断 -10% 风险、趋势质量、止损可执行性。

字段：

- adjusted_close
- open / high / low / close / volume
- MA20 / MA50 / MA200
- RSI14
- ATR14
- 20 日成交量均值
- 52 周高低点
- 相对 SPY / QQQ 强弱

输出 Evidence：

```json
{
  "symbol": "NVDA",
  "evidence_type": "price_technical",
  "as_of": "2024-02-22",
  "claim": "NVDA trades above MA20/MA50/MA200 with strong momentum",
  "metrics": {
    "close": 78.39,
    "ma20": 72.1,
    "ma50": 64.3,
    "rsi14": 68.2,
    "atr14": 3.1
  },
  "source": "longbridge_or_market_provider",
  "confidence": "High"
}
```

## 3. 第二优先级：基本面与财报

用途：判断公司质量、成长、盈利弹性。

字段：

- revenue
- revenue_growth
- gross_margin
- operating_margin
- net_income
- EPS
- free_cash_flow
- debt / cash
- segment_growth

## 4. 第三优先级：估值与一致预期

用途：判断 +20% 是否还有空间。

字段：

- trailing PE
- forward PE
- price / sales
- EV / EBITDA
- FCF yield
- forward EPS
- EPS revision
- revenue revision
- target price revision
- analyst rating change

## 5. 第四优先级：消息面与催化剂

用途：判断 3–6 个月内是否存在预期变化。

字段：

- earnings release
- guidance change
- product launch
- M&A
- regulation / policy
- lawsuit
- management change
- supply chain event
- industry theme acceleration

## 5a. 供应链与产业链（催化剂扩展）

用途：监测产业链上下游联动信号，判断成本压力和供应风险。

数据来源：

- 供应商股价联动：自动拉取已知供应商近期行情，计算供应商指数
- 供应链新闻：检测芯片短缺/涨价/关税/物流/人工等关键词
- 成本方向：从新闻文本判断成本上升/下降/稳定的趋势信号

输出 Evidence：

```json
{
  "symbol": "AAPL",
  "evidence_type": "supply_chain",
  "as_of": "2026-07-02",
  "claim": "5家供应商: 平均+2.3% (3涨1跌1平), 供应链新闻8条: chip_shortage(3) cost_pressure(3) tariff(2)",
  "source": "longbridge",
  "confidence": "Medium"
}
```

## 6. 第五优先级：资金流与持仓

用途：判断资金是否正在进入或撤出。

字段：

- ETF holdings change
- ETF weight change
- institutional ownership
- 13F changes
- insider transactions
- political trades
- options flow
- short interest

## 7. 第六优先级：社交与情绪

用途：辅助判断热门主题与拥挤度。

字段：

- Reddit / X / LongPort community mentions
- sentiment score
- abnormal discussion volume
- influencer posts
- retail attention

社交数据不能单独形成 Candidate，只能作为辅助催化或风险信号。

## 8. Evidence 标准结构

所有数据源必须转换成统一 Evidence：

```json
{
  "evidence_id": "NVDA_PRICE_2024-02-22",
  "symbol": "NVDA",
  "as_of": "2024-02-22T21:00:00Z",
  "source": "longbridge",
  "source_type": "market_data",
  "evidence_type": "technical",
  "claim": "NVDA is in strong uptrend",
  "metrics": {},
  "url": null,
  "confidence": "High",
  "limitations": []
}
```

## 9. 禁止事项

- 禁止无来源数据。
- 禁止 LLM 编造数据。
- 禁止用未来数据做历史研究。
- 禁止社交情绪单独决定 Candidate。
