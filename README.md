# Athena — AI 投资研究系统

> **North Star**: 判断某只股票未来 3–6 个月是否更可能先上涨 +20%，还是先下跌 -10%。

基于行情、基本面、估值、新闻、资金流等多维度数据，输出 **Candidate / Watch / Reject / Risk Alert** 判断及完整中文研究报告。

## 快速开始

```bash
# 安装依赖
pip install -e .

# 配置 .env（LONGBRIDGE_* + DEEPSEEK_API_KEY）

# 运行研究
python -m athena run AAPL          # 技术面 + 基本面 + 估值 + 风险 + 催化剂
python -m athena run NVDA --report # 含 LLM 中文研报
python -m athena run MRVL --json   # JSON 输出
```

## 项目结构

```
athena/
  cli.py              命令行入口
  config.py           配置管理（.env）
  data/               数据层（market/fundamental/content/flow）
  signals/            信号层（technical/fundamental/valuation/risk/catalyst/flow/sentiment）
  evidence/           证据层（models/store/normalizer）
  llm/                LLM 分析（analyst/prompts/schema）
  probability/        概率引擎（规则兜底）
  validation/         回测验证（案例管理/胜率校准）
  reports/            报告生成
  outputs/            输出报告（.md + .json）
tests/                测试
docs/                 设计文档
```

## 数据源

- **Longbridge OpenAPI**: 实时行情、基本面、一致预期、新闻、经纪商数据
- **yfinance**: 备选行情（Yahoo Finance）
- **DeepSeek**: LLM 研究分析

## 文档

完整设计文档见 `docs/` 目录。
