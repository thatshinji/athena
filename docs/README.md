# Athena — AI 投资研究系统

> **North Star**（第一行）：基于当前可获得的行情、基本面、消息面、社交情绪、ETF 持仓、机构与政治人物披露等信息，判断某只股票未来 3–6 个月是否更可能先上涨 +20%，还是先下跌 -10%。

系统不输出 buy/sell/hold，不自动下单，不保证收益。它输出的是：

- Candidate：值得进入重点候选池
- Watch：继续观察
- Reject：暂不考虑
- Risk Alert：下跌 -10% 风险显著上升

## 文档目录

1. `01_PRODUCT_REQUIREMENTS.md`：产品需求与边界
2. `02_SYSTEM_ARCHITECTURE.md`：完整系统架构图与模块说明
3. `03_DATA_SOURCE_CONTRACT.md`：数据源与证据契约
4. `04_SIGNAL_FRAMEWORK.md`：技术面、基本面、消息面、资金面信号框架
5. `05_AGENT_WORKFLOW.md`：AI Agent 执行流程与任务分工
6. `06_LONGBRIDGE_INTEGRATION.md`：Longbridge / LongPort 接入边界与用法规划
7. `07_LLM_RESEARCH_PROTOCOL.md`：LLM 分析协议与中文输出规范
8. `08_RISK_AND_DECISION_RULES.md`：+20% / -10% 风险收益判断规则
9. `09_VALIDATION_AND_BACKTEST.md`：历史验证与胜率校准
10. `10_CODEX_IMPLEMENTATION_PLAN.md`：给 Codex / AI Agent 的实施计划

## 使用方式

把整个目录交给 AI Agent / Codex。要求它先阅读 `README.md`，再按 `10_CODEX_IMPLEMENTATION_PLAN.md` 执行。
