# 07 LLM 研究协议与中文输出规范

## 1. LLM 的定位

LLM 是研究分析师，不是数据源，不是交易员。

LLM 只允许基于 Evidence 和 Signal 输入进行推理。

## 2. 输入给 LLM 的结构

```json
{
  "symbol": "NVDA",
  "horizon": "3-6m",
  "trade_rule": {
    "upside_target": 0.20,
    "downside_risk": -0.10
  },
  "evidence": [],
  "signals": {
    "technical": {},
    "fundamental": {},
    "valuation": {},
    "catalyst": {},
    "flow": {},
    "sentiment": {},
    "risk": {}
  }
}
```

## 3. LLM 必须回答的问题

1. 未来 3–6 个月 +20% 上行路径是什么？
2. 哪些证据支持这个路径？
3. 未来先跌 -10% 的风险在哪里？
4. 哪些证据支持风险判断？
5. 当前是 Candidate / Watch / Reject / Risk Alert？
6. 置信度是多少？为什么？
7. 还缺哪些证据？
8. 下一步该观察什么？

## 4. 中文报告格式

```markdown
# {symbol} 3–6 个月交易窗口研究

## 一、研究结论

## 二、+20% 上行路径

## 三、-10% 下行风险

## 四、技术面判断

## 五、基本面判断

## 六、估值与预期判断

## 七、消息面与催化剂

## 八、资金流与情绪

## 九、风险官反驳

## 十、最终判断与观察清单
```

## 5. 语言要求

- 全中文。
- 简洁但信息密度高。
- 不要空泛表述。
- 不要写“可能上涨也可能下跌”这种废话。
- 必须明确倾向和证据强弱。

## 6. 禁止事项

LLM 禁止：

- 编造数据。
- 直接输出买入/卖出。
- 忽略风险。
- 把社交情绪当作核心证据。
- 用未来数据解释历史判断。
- 给出没有证据的概率。

## 7. 输出 JSON Schema

```json
{
  "symbol": "NVDA",
  "status": "Candidate | Watch | Reject | Risk Alert",
  "upside_probability_range": [0.35, 0.55],
  "downside_probability_range": [0.20, 0.35],
  "confidence": "High | Medium | Low | Not Ready",
  "upside_path": [],
  "downside_risks": [],
  "key_evidence": [],
  "missing_evidence": [],
  "watchlist": [],
  "final_commentary_zh": ""
}
```
