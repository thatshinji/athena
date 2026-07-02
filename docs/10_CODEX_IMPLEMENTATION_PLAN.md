# 10 Codex / AI Agent 实施计划

## 总原则

不要继续扩展复杂架构。先实现一个可用 MVP：

> 输入股票代码 → 拉取真实行情 → 计算技术面 → 结合基础财报/新闻占位 → 生成中文 +20% / -10% 研究报告。

## Phase 0：项目收敛

任务：

1. 阅读本目录所有文档。
2. 将 README 第一行改为 North Star。
3. 标记旧 mock report 为 legacy。
4. 不删除旧模块，但不要继续扩展。

验收：

- README 明确：Athena 只服务 +20% / -10% 研究判断。

## Phase 1：Price Evidence MVP

目标：把价格数据从 Placeholder 变成真实 Evidence。

实现：

1. 新增 `athena/data/market_provider.py`
2. 优先接入 Longbridge / LongPort 只读行情；如果本地环境不可用，允许先用 CSV fixture。
3. 拉取 OHLCV。
4. 计算：
   - adjusted close
   - MA20
   - MA50
   - MA200
   - RSI14
   - ATR14
   - volume average 20d
5. 输出 Evidence。
6. 映射到 Research Inputs：
   - TC-001 Price Trend
   - TC-002 Moving Average Alignment
   - TC-005 Volatility / ATR
   - RK-010 Drawdown / Stop-loss Risk

禁止：

- 不新增 Knowledge Layer。
- 不新增复杂报告。
- 不接交易接口。

验收：

- AAPL / NVDA price placeholder 变成 Real。
- 中文报告能说明技术面是否支持 -10% 风控。
- pytest 通过。

## Phase 2：LLM 中文研究报告 MVP

目标：生成真正可读的中文投资研究报告。

实现：

1. 新增 `athena/llm/analyst.py`
2. 输入结构化 Evidence + Signals。
3. 输出中文 Markdown + JSON。
4. 强制包含 Risk Officer 章节。
5. 不允许 LLM 编造数据。

验收：

- 输入 NVDA，输出中文报告。
- 明确 Candidate / Watch / Reject / Risk Alert。
- 明确 +20% 上行路径和 -10% 风险。

## Phase 3：Estimate Evidence MVP

目标：加入一致预期修正。

实现字段：

- forward EPS
- EPS revision
- revenue revision
- consensus rating

验收：

- GR-004 Estimate Revision 不再 Placeholder。
- 报告能说明盈利预期是否上修。

## Phase 4：Historical Cases

目标：建立 20 个真实历史 case。

验收：

- 每个 case 有 as-of evidence 和 outcome。
- 能计算 Candidate success rate。

## Phase 5：Probability Calibration

目标：判断 Candidate 胜率是否高于 33.3%。

输出：

- Candidate hit rate
- FalsePositive rate
- FalseNegative rate
- StopLossFirst rate
- UpsideFirst rate

## 当前立即执行的任务

请先执行：

> Phase 1：Price Evidence MVP

Codex 输出必须包含：

1. 修改文件列表
2. 行情数据来源
3. 技术指标计算方式
4. Evidence 示例
5. Research Input 映射
6. AAPL / NVDA 重新运行结果
7. 中文报告变化
8. 测试结果
9. 是否调用任何交易接口
