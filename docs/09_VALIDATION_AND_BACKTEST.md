# 09 历史验证与胜率校准

## 1. 验证目标

验证 Athena 的判断是否有实际价值。

核心问题：

> Athena 给出的 Candidate，在历史上是否有超过 33.3% 的成功率？

## 2. Outcome 定义

对每个历史 case，记录：

- as_of_date
- horizon_start
- horizon_end
- as_of_price
- target_price = as_of_price * 1.20
- stop_loss_price = as_of_price * 0.90
- first_hit_upside_date
- first_hit_stop_loss_date
- final_outcome

## 3. Outcome 分类

- UpsideFirst：先涨 +20%
- StopLossFirst：先跌 -10%
- Neither：周期内都没有触发
- Inconclusive：数据不足

## 4. Validation Label

- TruePositive：Candidate 且 UpsideFirst
- FalsePositive：Candidate 但 StopLossFirst
- TrueNegative：非 Candidate 且不是 UpsideFirst
- FalseNegative：非 Candidate 但 UpsideFirst

## 5. 胜率计算

```text
Candidate Success Rate = TruePositive / 所有 Candidate
```

如果长期：

```text
Candidate Success Rate > 33.3%
```

则说明系统可能具备正期望研究价值。

## 6. 样本要求

不能用 2 个 case 得结论。

阶段要求：

- 10 cases：只能做流程验证
- 30 cases：初步观察
- 100 cases：开始校准概率
- 300+ cases：才适合系统性评估

## 7. Case 选择原则

必须包含：

- 成功大涨股
- 失败大跌股
- 横盘股
- 热门科技股
- 周期股
- 防御股
- 小盘高波动股

不能只选 NVDA 这种赢家。

## 8. 避免未来函数

历史 case 必须严格区分：

- as-of-date 前可见 Evidence
- as-of-date 后 Outcome

Outcome 不能进入 Research。
