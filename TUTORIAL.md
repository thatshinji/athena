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

# DeepSeek LLM（可选，不配置则使用规则引擎）
DEEPSEEK_API_KEY=你的APIKey

# Quiver Quantitative（可选，国会交易/内幕数据）
QUIVER_API_KEY=你的APIKey
```

> **获取 Longbridge 凭证**：登录 [Longbridge](https://open.longbridge.com/) 开放平台 → 个人中心 → 创建应用即可获得 App Key / Secret / Access Token。LV1 行情权限可免费使用。

> **获取 DeepSeek Key**：在 [DeepSeek 官网](https://platform.deepseek.com/) 注册并获取 API Key。

> **获取 Quiver Key**：在 [Quiver Quantitative](https://www.quiverquant.com/) 注册免费账号获取。

---

## 2. 基本使用

### 2.1 快速研究（规则引擎，默认）

```bash
python -m athena run AAPL
```

### 2.2 AI 深度研报

```bash
python -m athena run NVDA --report
```
生成完整中文研报（10 章），保存在 `athena/outputs/`（.md + .json）。

### 2.3 JSON 输出

```bash
python -m athena run MRVL --json
```

---

## 3. 输出解读

### 3.1 四种判断

| 判断 | 含义 |
|------|------|
| ⭐ Candidate | 上行路径清晰 + 下行风险可控 + 多信号同向 |
| 👀 Watch | 有亮点但催化不足，或信号矛盾 |
| ❌ Reject | 无合理上行路径 / 基本面恶化 / 估值透支 |
| ⚠️ Risk Alert | 风险评分 ≥ 5，-10% 概率显著高于 +20% |

### 3.2 风险评分（0–10）

- 0–2：低风险
- 3–4：中等风险
- 5–6：高风险（触发 Risk Alert）
- 7–10：极高风险

### 3.3 概率校准

每次 `--report` 运行自动保存案例，后续运行显示校准面板：

```
📊 历史校准 (已结 59 案例):
   Candidate 胜率: 100.0% (✅ 高于盈亏平衡)
   +20% 先达率: 42.1%  -10% 先达率: 37.5%
```

盈亏平衡胜率 33.3%（+20%/-10% 盈亏比 2:1）。

---

## 4. 信号体系

Athena 分析一只股票时计算 **9 类信号**、**35+ Research Inputs**：

| 类别 | 包含指标 | 数据来源 |
|------|---------|---------|
| 技术面 | MA20/50/200、RSI、ATR、52周高低、相对SPY/QQQ | Longbridge 行情 |
| 基本面 | 营收/EPS beat/miss、营收YoY、毛利率、净利率、ROE、EPS增速、营业利润率、净利润、FCF、债务/现金、经营现金流 | Longbridge 财报（IS/BS/CF） |
| 估值 | Trailing PE、Forward PE、PS、FCF Yield、EV/EBIT | Longbridge 估值 + 一致预期 |
| 风险 | 综合风险评分 0–10（跨信号聚合） | 技术+基本+估值 |
| 催化剂 | 新闻关键词 + 结构化公司事件（分红/拆股/财报日） | Longbridge 新闻 + corp_actions |
| 资金流 | 经纪商买卖 + ETF/基金持仓 + 机构增减持 | Longbridge 市场 + 股东数据 |
| 情绪 | 新闻情绪 + LongPort 社区讨论 | Longbridge 新闻 + 社区 |
| 政治 | 国会交易（需要 Quiver API key） | Quiver Quantitative |
| 宏观 | 行业估值对比（同行 PE 中位/折溢价） | Longbridge 行业 |
| 供应链 | 供应商股价指数 + 供应链新闻监测 | Longbridge 行情 + 新闻 |

---

## 5. 数据源

```
Longbridge SDK → yfinance → fixture（自动降级，永不崩溃）
```

- **Longbridge**：免费 LV1 权限覆盖行情、财报、新闻、社区、行业
- **yfinance**：免费备选行情源
- **DeepSeek**：LLM 研究分析
- **Quiver**：国会交易/内幕数据（可选）

---

## 6. 常见场景

```bash
# 快速扫描多只股票
for sym in AAPL NVDA MSFT GOOGL TSLA; do
  python -m athena run $sym 2>/dev/null | grep "判断:"
done

# 只看结论
python -m athena run AAPL 2>/dev/null | grep -E "判断:|数据源:|Evidence:"

# 导出 JSON
python -m athena run NVDA --json > nvda.json

# 查看历史校准
python -c "from athena.validation import store; import json; print(json.dumps(store.calibration_metrics(), indent=2))"
```

---

## 7. 故障排查

| 问题 | 原因 | 解决 |
|------|------|------|
| `Longbridge SDK 网络不可达` | 网络波动 | 自动降级到 yfinance/fixture |
| `数据源: fixture` | 所有外部源不可用 | 置信度 Low，仅作参考 |
| `LLM 分析失败` | DeepSeek API 异常 | 规则引擎自动兜底 |
| 基本面无数据 | Longbridge 未连通 | 检查 .env 凭证 |

---

## 8. 项目结构

```
athena/
  cli.py              命令行入口
  config.py            配置管理
  data/                数据层（market/fundamental/content/flow/social/political）
  signals/             信号层（9 类信号）
  evidence/            证据层（models/store/normalizer）
  llm/                 LLM 分析（analyst/prompts/schema）
  probability/         概率引擎（规则兜底）
  validation/          回测验证（案例管理/胜率校准）
  reports/             报告生成
  outputs/             输出报告（.md + .json）
tests/                 26 个测试
docs/                  完整设计文档
```

## 9. 测试

```bash
python -m pytest tests/ -v
# 预期输出：26 passed
```
