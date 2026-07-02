# RKLB 报告外部评审反馈分析

## 评审人评分：7.5 / 10

> 「可以作为 Daily Review，但还不能作为真正的投资决策依据。」

---

## 问题一：概率模型是"拍脑袋"，没有统计基础

### 问题描述
所有 `upside_probability_range` / `downside_probability_range` 来自规则引擎的加权打分（bullish +1 / bearish +2），不是历史统计模型。评审人期望看到类似"过去 15 年类似成长股在同样条件下，3 个月内上涨 20% 的实际概率是 39%"这样的统计推断。

### 当前实现
| 组件 | 方式 | 问题 |
|------|------|------|
| `probability/engine.py` | bullish/bearish 因子累加 → 比例映射到 5-90% 区间 | 权重是人为主观设定的，无可验证性 |
| `validation/metrics.py` | 计算历史 Candidate 胜率 | **已有统计基础设施**，但未反馈到当前预测 |
| 数据 | 61 个历史案例 | 案例是模拟手工构造的，不是真实回测 |

### 根因
概率引擎是第一版「规则 + 信号驱动」，按文档要求做了，但从未接入真实的历史回测数据。`validation/` 模块独立计算胜率，但两个模块之间没有数据通路。

### 可行性
**高**。系统已经有一个 61 案例的数据库和 `compute_calibration()` 函数。需要：将历史案例按信号条件分组，计算条件概率，替换当前的加权打分逻辑。

---

## 问题二：技术分析太浅

### 问题描述
只有 MA/RSI/ATR/52 周高低。缺少：
- 相对行业 ETF 强弱（RKLB vs ITA/XAR，不只是 SPY/QQQ）
- Volume Profile（套牢盘/真空区/阻力位）
- Market Structure（HH/HL/LH/LL）

### 当前实现
| 能力 | 状态 | 缺失 |
|------|------|------|
| SPY/QQQ 相对强弱 | ✅ `technical.py` `compute_relative_strength` | — |
| 行业 ETF 对比 | ❌ | 未拉取 ITA/XAR 等 |
| Volume Profile | ❌ | 完全未实现 |
| Market Structure | ❌ | 完全未实现 |

### 根因
`technical.py` 只实现了 03_DATA_SOURCE_CONTRACT.md §2 要求的基础指标，文档未要求 Volume Profile 和 Market Structure。

### 可行性
**中**。行业 ETF 对比只需加几行拉取代码（ITA/XAR 等 ETF 行情）。Volume Profile 需要 OHLCV 数据做价格区间的成交量累积，原理不复杂但需要新写算法。Market Structure 可用现有 OHLCV 数据检测 HH/HL/LH/LL 形态。

---

## 问题三：催化剂写得太虚

### 问题描述
"检测到 20 个潜在催化剂" —— 但不知道是什么、什么时候、概率多大、影响多大。

### 当前实现
| 组件 | 方式 | 问题 |
|------|------|------|
| `signals/catalysts.py` | 关键词扫描 | 只有分类标签（ai_data_center, product），无具体内容 |
| `corp_actions` | 结构化事件 | 有日期和类型（DividendExDate 等），但未 forward-project |

### 根因
关键词扫描是目前能做的极限。要输出「概率 + 影响 + 时间轴」需要：
1. 事件数据库或预测模型
2. 对每个事件做影响量化

### 可行性
**低**。事件概率和影响量化需要人工判断或专家模型，AI 系统难以自动完成。可改进部分：在消费股价信息前，先输出催化剂列表的详细内容（标题、日期），让用户自己判断。

---

## 问题四：基本面没有真正分析业务

### 问题描述
"Revenue +63% 结束" —— 没有分析为什么增长、增长来自哪块业务、收入结构、订单 backlog、政府/商业占比。

### 当前实现
| 能力 | 状态 |
|------|------|
| 营收 YoY | ✅ IncomeStatement |
| 营收 Beat/Miss | ✅ consensus |
| Revenue Mix | ❌ Longbridge 不提供分部数据 |
| Backlog | ❌ 需要 SEC 文件解析 |
| Government/Commercial split | ❌ 需要人工标注 |

### 根因
**数据源天花板**。Longbridge 的基本面 API 提供 IS/BS/CF 三表，但不提供业务分部（segment）数据。Segment data 通常只在 10-K/10-Q 原文中出现。

### 可行性
**低**。需要接入 SEC EDGAR 文件并做 NLP 解析（10-K Item 1 Business、MD&A 等）。这是另一个工程级别的项目。

---

## 问题五：估值分析对成长股用错了指标

### 问题描述
"PE -188 结束" —— 成长亏损公司不应该看 Trailing PE。应该看 EV/Sales、P/S、DCF、Backlog Multiple、同行对比。

### 当前实现
| 指标 | 状态 |
|------|------|
| Trailing PE | ✅ `valuation.py` VL-001 |
| Forward PE | ✅ VL-002 |
| P/S | ✅ 从 Longbridge valuation 获取 |
| FCF Yield | ✅ VL-003 |
| EV/EBIT | ✅ VL-004 |
| PE 同行对比 | ✅ `macro.py` MA-001 |

### 问题
系统**已经**有 P/S、FCF Yield、EV/EBIT 和行业对比，但 **LLM prompt 里没有指导 LLM 对成长亏损公司使用正确的估值框架**。LLM 被提示「PE 低 + EPS Beat → 看多」，这对于 RKLB 这种 PE 为负的成长股完全错误。

### 可行性
**高**。只需要修改 `llm/prompts.py`，增加对亏损成长公司的估值判断指导（「PE 为负时忽略 PE，使用 P/S + EV/Sales + 同行对比 + 营收增速」）。

---

## 问题六～九：行业/竞争/时间轴/叙事分析

| 问题 | 可行性 | 说明 |
|------|--------|------|
| 行业分析（国防预算、NASA 预算） | **低** | 需要结构化行业数据源 |
| 竞争格局（SpaceX、Blue Origin） | **低** | 需要人工构建竞争关系图谱 |
| 催化剂时间轴 | **中** | `corp_actions` 有日期，可向前投影 3-6 个月 |
| 叙事分析（"为什么市场买 RKLB"） | **中** | 可通过增强 LLM prompt 实现，但依赖 LLM 能力 |

---

## 评审人提出的 10 维升级框架

| 维度 | 当前覆盖 | 优先级 | 可行性 |
|------|---------|--------|--------|
| 1. 一句话投资结论 | ✅ 已有 | — | — |
| 2. 投资逻辑树 | ⚠️ 部分（LLM 自由文本） | 🟠 | 高（prompt 增强） |
| 3. 业务拆解 | ❌ 缺 segment | 🔴 | 低（数据天花板） |
| 4. 行业与竞争 | ❌ | 🔴 | 低（数据天花板） |
| 5. 估值框架 | ⚠️ 成长股用错指标 | 🟠 | 高（prompt 增强） |
| 6. 资金行为 | ✅ 机构/ETF/经纪商 | — | — |
| 7. 技术面 | ⚠️ 缺 Vol Profile/Structure | 🟡 | 中 |
| 8. 催化剂日历 | ⚠️ 只有标签 | 🟡 | 中 |
| 9. 风险矩阵 | ⚠️ 只有评分无概率 | 🟡 | 中 |
| 10. 证据评分 | ❌ | 🟢 | 高（scoring layer） |

---

## 总结

| 类别 | 数量 | 说明 |
|------|------|------|
| 可快速修复（prompt/逻辑） | 4 项 | 估值框架、投资逻辑树、证据评分、催化剂详情输出 |
| 中等难度（算法/数据管道） | 3 项 | Vol Profile、催化剂日历、风险概率矩阵 |
| 数据天花板（需新数据源） | 6 项 | 业务拆解、行业分析、竞争格局、叙事、segment、backlog |

**核心根因**：系统按照 docs 设计完成，但 docs 本身的设计目标是 MVP 级别（daily review），不是机构级投资决策工具。评审人的期望值是机构 Buy-side 水准，这需要数据源升级和算法升级。
