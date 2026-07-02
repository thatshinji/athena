# 05 AI Agent 工作流

## 1. Agent 角色

Athena 推荐由多个 Agent 协作，但第一版可以由单 Agent 串行执行。

### 1.1 Data Agent

职责：

- 拉取行情
- 拉取财报
- 拉取新闻
- 拉取 ETF / 持仓数据
- 拉取社交数据
- 统一转成 Evidence

禁止：输出投资结论。

### 1.2 Technical Analyst Agent

职责：

- 计算 K 线指标
- 判断趋势、波动率、止损可执行性
- 识别 -10% 风险

### 1.3 Fundamental Analyst Agent

职责：

- 阅读财报
- 分析收入、利润率、现金流、EPS、业务分部
- 判断基本面是否支持 20% 上行

### 1.4 News & Catalyst Agent

职责：

- 汇总新闻、公告、财报事件
- 判断未来 3–6 个月催化剂
- 标记风险事件

### 1.5 Flow & Sentiment Agent

职责：

- 分析 ETF 持仓变化
- 分析机构/政治人物披露
- 分析社交热度与情绪

### 1.6 Risk Officer Agent

职责：

- 找下跌 -10% 的风险
- 找 thesis invalidation
- 检查是否过度乐观
- 给出风险等级

### 1.7 Chief Investment Analyst Agent

职责：

- 综合所有 Agent 结果
- 输出 Candidate / Watch / Reject / Risk Alert
- 输出中文研究报告

## 2. 标准执行流程

```text
输入股票代码
↓
Data Agent 收集证据
↓
各分析 Agent 生成结构化分析
↓
Risk Officer 反向审查
↓
Chief Analyst 综合判断
↓
输出中文报告
↓
保存 case
↓
未来验证 +20% / -10% 结果
```

## 3. 每个 Agent 的输出格式

```json
{
  "agent": "Technical Analyst",
  "symbol": "NVDA",
  "summary": "技术面强势，但 ATR 偏高",
  "bullish_evidence": [],
  "bearish_evidence": [],
  "risk_flags": [],
  "confidence": "Medium",
  "questions": []
}
```

## 4. Agent 纪律

- 必须中文输出。
- 必须引用 Evidence ID。
- 不得编造数据。
- 不得输出 buy/sell/hold。
- 不得忽略 -10% 风险。
- Risk Officer 必须主动寻找反证。
