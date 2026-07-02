# Athena 使用教程

## 简介

Athena 是一个 AI 投资研究系统。它回答一个核心问题：

> 某只股票未来 3–6 个月，更可能先涨 +20%，还是先跌 -10%？

系统输出四种判断：**⭐ Candidate**（值得关注）、**👀 Watch**（继续观察）、**❌ Reject**（暂不考虑）、**⚠️ Risk Alert**（下跌风险）。

**Athena 不做的事**：不自动下单、不输出 buy/sell/hold、不保证收益。

---

## 1. 环境准备

### 1.1 安装依赖

```bash
cd athena/
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 1.2 配置 .env

在项目根目录创建 `.env` 文件：

```bash
# Longbridge 行情数据（必须）
LONGBRIDGE_APP_KEY=你的AppKey
LONGBRIDGE_APP_SECRET=你的AppSecret
LONGBRIDGE_ACCESS_TOKEN=你的AccessToken

# DeepSeek LLM（如需 AI 研报）
DEEPSEEK_API_KEY=你的APIKey
```

> **获取 Longbridge 凭证**：登录 [Longbridge](https://open.longbridge.com/) 开放平台 → 个人中心 → 创建应用即可获得 App Key / Secret / Access Token。LV1 行情权限可免费使用。

> **获取 DeepSeek Key**：在 [DeepSeek 官网](https://platform.deepseek.com/) 注册并获取 API Key。不配置也可以使用（会走规则引擎兜底）。

---

## 2. 基本使用

### 2.1 快速研究（规则引擎）

```bash
python -m athena run AAPL
```

输出包含：
- 📊 技术面（均线、RSI、ATR、52 周高低点、相对 SPY 强弱）
- 💰 基本面（营收、EPS、毛利率、净利率、ROE、FCF、债务）
- 🏷️ 估值（PE、Forward PE）
- 📰 催化剂（新闻检测）
- 💵 资金流（经纪商买卖方向）
- 😊 情绪（新闻正负面分析）
- ⚠️ 风险评级（0–10 综合评分）
- ⭐ 最终判断（Candidate / Watch / Reject / Risk Alert）
- 📊 历史校准（案例胜率）

### 2.2 AI 深度研报（LLM）

```bash
python -m athena run NVDA --report
```

在规则引擎基础上，调用 DeepSeek 生成完整中文研报，包含 10 个章节（研究结论 → 上行路径 → 下行风险 → 各维度分析 → 风险官反驳 → 最终判断）。

报告保存在 `athena/outputs/` 目录（.md + .json 双格式）。

### 2.3 JSON 输出

```bash
python -m athena run MRVL --json
```

输出结构化 JSON，包含所有 Evidence、Signals、Research Inputs，方便程序化处理。

---

## 3. 输出解读

### 3.1 四种判断

| 判断 | 含义 | 触发条件 |
|------|------|---------|
| ⭐ Candidate | 值得进入候选池 | 技术+基本面+估值至少 2 类同向，风险可控，上行路径清晰 |
| 👀 Watch | 继续观察 | 有些亮点但催化不足，或信号矛盾 |
| ❌ Reject | 暂不考虑 | 没有合理上行路径，或基本面恶化，或估值透支 |
| ⚠️ Risk Alert | 下跌风险 | 风险评分 ≥ 5，-10% 概率显著高于 +20% |

### 3.2 风险评分（0–10）

- 0–2：低风险
- 3–4：中等风险
- 5–6：高风险（Risk Alert）
- 7–10：极高风险

评分考虑因素：均线排列、ATR、营收/EPS miss、估值透支等。

### 3.3 概率校准

每次 `--report` 运行会自动保存案例。后续运行会显示：

```
📊 历史校准 (已结 19 案例):
   Candidate 胜率: 100.0% (✅ 高于盈亏平衡)
   +20% 先达率: 42.1%  -10% 先达率: 37.5%
```

盈亏平衡胜率为 33.3%（+20%/-10% 盈亏比 2:1）。只有胜率 > 33.3% 系统才有正向预期。

---

## 4. 数据源说明

Athena 采用多数据源自动降级：

```
Longbridge SDK（实时行情） → yfinance（Yahoo Finance） → fixture（合成数据）
```

- **Longbridge**：免费 LV1 权限覆盖美股实时行情、基本面、一致预期、新闻、经纪商数据
- **yfinance**：免费备选行情源
- **fixture**：以上均不可用时，生成合成数据保证系统不崩溃。此时证据置信度为 Low

当前运行的数据来源会在输出首行显示（`数据源: longbridge`）。

---

## 5. 信号体系

Athena 分析一只股票时，会计算以下 7 类信号：

| 类别 | 包含指标 | 数据来源 |
|------|---------|---------|
| 技术面 | MA20/50/200、RSI、ATR、52周高低、相对SPY | Longbridge 行情 |
| 基本面 | 营收/EPS beat/miss、营收YoY、毛利率、净利率、ROE、EPS增速 | Longbridge 财报 |
| 估值 | PE、Forward PE、PE 历史分位 | Longbridge 估值 |
| 风险 | 综合风险评分 0–10 | 跨信号聚合 |
| 催化剂 | 新闻关键词检测、财报事件 | Longbridge 新闻 |
| 资金流 | 经纪商买卖方向 | Longbridge 市场 |
| 情绪 | 新闻正负面分析 | 新闻文本分析 |

每类信号对应 1–8 个 Research Input（如 BQ-001 营收、VL-001 PE、CA-001 催化剂检测）。

---

## 6. 常见场景

### 快速扫描多只股票

```bash
for sym in AAPL NVDA MSFT GOOGL TSLA; do
  echo "=== $sym ==="
  python -m athena run $sym 2>/dev/null | grep "判断:"
done
```

### 只看结论不看详情

```bash
python -m athena run AAPL 2>/dev/null | grep -E "判断:|数据源:|Evidence:"
```

### 导出 JSON 分析

```bash
python -m athena run NVDA --json > nvda_analysis.json
```

### 查看历史校准

```bash
python -c "from athena.validation import store; import json; print(json.dumps(store.calibration_metrics(), indent=2))"
```

---

## 7. 故障排查

| 问题 | 原因 | 解决 |
|------|------|------|
| `Longbridge SDK 网络不可达` | 网络波动 | 系统会自动降级到 yfinance 或 fixture |
| `yfinance 不可用` | Yahoo 限流 | 正常，等几分钟重试 |
| `数据源: fixture` | 所有外部源不可用 | 数据为合成，置信度 Low，仅作参考 |
| `LLM 分析失败` | DeepSeek API 异常 | 规则引擎会自动兜底输出判断 |
| `基本面无数据` | Longbridge 未连通 | 检查 .env 凭证是否正确 |

---

## 8. 进阶：运行测试

```bash
python -m pytest tests/ -v
# 预期输出：26 passed
```

## 9. 项目结构

```
athena/
  cli.py              命令行入口
  config.py            配置管理
  data/                数据层（market/fundamental/content/flow 等）
  signals/             信号层（7 类信号）
  evidence/            证据层（models/store/normalizer）
  llm/                 LLM 分析（analyst/prompts/schema）
  probability/         概率引擎（规则兜底）
  validation/          回测验证（案例管理/胜率校准）
  reports/             报告生成
  outputs/             输出报告（.md + .json）
tests/                 26 个测试
docs/                  完整设计文档
```

---

## 10. 设计哲学

1. **证据驱动**：所有结论必须可追溯到具体证据（Evidence）
2. **不编造数据**：缺失数据明确标注"证据不足"
3. **风险优先**：每份报告必须有独立的风险官反驳
4. **渐进降级**：数据源不可用时自动降级，绝不崩溃
5. **中文输出**：所有报告、分析、结论均为中文
