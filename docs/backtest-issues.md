# 回测引擎问题分析

> 分支：`docs/backtest-issues-analysis` | 日期：2026-07-21 | 状态：待修复

## 概述

对 `harness/run.py` 回测引擎进行逐行审计，发现 3 个致命问题、3 个高优问题和 2 个改进项。

---

## 🔴 致命问题

### 1. 未来函数（Look-ahead Bias）

**位置：** `harness/run.py:42-44`

```python
for i in range(MIN_BARS, len(df)):
    pred = decide(prices[: i + 1], ...)  # ← 使用了 bar i 的收盘价
    current_price = prices[i]             # ← 同一时刻执行交易
```

**问题：**
- 预测使用了 `prices[:i+1]`，即包含了 bar `i` 的收盘价
- 交易也在 bar `i` 的收盘价执行
- 现实中：收盘后才知道收盘价 → 调 LLM → 下一根 bar 开盘才能成交

**影响：** 策略"偷看"了当前 K 线的收盘价再做决定。回测结果**系统性偏高**，不可信。

**修复方向：**
- 预测输入：`prices[:i]`（不包含当前 bar）
- 执行价格：`df.iloc[i+1]["open"]`（下一根 bar 开盘价，模拟延迟）
- 或至少用 `df.iloc[i]["open"]`（当前 bar 开盘即决策，仍有信息优势但更接近实战）

---

### 2. 无法做空

**位置：** `harness/run.py:64-83`

```python
elif direction == "做空" and in_position:
    # SELL: close position（平仓）
    cash = position * current_price
```

**问题：**
- LLM 输出"做空" = 平掉多仓，**而非开空仓**
- 如果无持仓且 LLM 预测做空 → 什么都不做
- 如果市场持续下跌，LLM 一直预测做空 → 空仓观望 → 收益率为 0

**影响：** 策略只能从上涨获利，无法评估 LLM 做空预测的真实质量。

**修复方向：**
- 现货：做多 = 买入，做空 = 卖出（平仓），不持币（这是当前逻辑）
- 如果希望利用做空信号，需要支持：
  - 做空 = 借币卖出（现货 margin），等跌了买回
  - 或在回测中允许"空仓"状态（持有 USDT），做空信号表示不参与
- 替代方案：做空信号 = 买入反向 ETF 或做空合约（需要合约/杠杆支持）

---

### 3. 每根 K 线调一次 LLM

**位置：** `harness/run.py:42-44`

```python
for i in range(MIN_BARS, len(df)):  # 720 - 100 = 620 次
    pred = decide(...)                # 每次都调 DeepSeek API
```

**问题：**
- 720 根 K 线 = **620 次 API 调用**
- 按每次 ~1s + token 计费，单币种回测耗时约 10 分钟
- 实盘中交易机器人每小时调一次 LLM（`INTERVAL_SEC = 3600`），回测应按同样频率

**影响：** 慢 + 贵 + 与实盘逻辑不一致。

**修复方向：**
- 增加 `decision_interval` 参数（默认 12 = 每 12h 决策一次）
- 或只在持仓状态下逐 bar 检查 TP/SL，无持仓时按周期调 LLM

---

## 🟡 高优先级问题

### 4. 全仓进出，无仓位管理

```python
position = cash / current_price  # 100% all-in
cash = 0.0
```

每次做多信号 = 100% 资金买入。没有：
- 分批建仓（试探仓 → 确认仓）
- 动态仓位（波动率高时减仓）
- 止损后的冷却期

**修复方向：** 增加 `position_size` 参数（固定比例 / Kelly 公式 / 波动率倒数）。

---

### 5. 无交易成本

回测引擎未扣除：
- 手续费（现货 0.1% × 2 = 双边 0.2%）
- 滑点（市价单与预期价的偏差）

30 笔交易 × 0.2% = 6% 的本金损耗，对于短线策略是致命影响。

**修复方向：** 在每笔交易的 `pnl_pct` 中扣除 `commission_rate`。

---

### 6. `strategy.py` 丢弃了 high/low 数据

```python
# harness/strategy.py
def decide(prices, highs, lows):   # highs, lows 传进来了
    return llm_predict(prices)      # 但没传给 LLM
```

`data.py` 拉取了完整 OHLCV，但 LLM 只收到收盘价。high/low 对判断支撑/阻力、波动范围至关重要。

**修复方向：** 将 high/low 纳入 LLM prompt（参见 `docs/llm-data-transmission.md` 方案 C/G）。

---

## 🟢 改进项

### 7. 单币种架构

`backtest()` 函数签名是 `symbol: str`。做多币种组合回测需要外部循环调用，无法评估组合层面的相关性、最大回撤等指标。

### 8. 单持仓限制

`in_position` 是布尔值，同一时间只能有一个头寸。要同时运行多个独立信号，需要改为 `positions: dict[str, Position]` 结构。

---

## 与 sandbox_trader.py 的关系

`sandbox_trader.py` 和 `harness/run.py` 是同一套策略逻辑的两份独立实现：

| 维度 | sandbox_trader.py | harness/run.py |
|:---|:---|:---|
| 数据源 | Binance 实时 API | Parquet 历史缓存 |
| 做空 | 支持（开空仓） | 不支持（= 平多仓） |
| TP/SL | 固定 2%/1%（忽略 LLM） | 使用 LLM 输出（fallback 2%/1%） |
| 选币 | 固定 20 个 | 单币种 |
| 仓位 | 每币 5% | 100% all-in |
| 调用频率 | 每小时 | 每根 K 线 |
| 真实下单 | ❌ | ❌ |

两者应统一为：一套策略定义 + 两个执行后端（历史回测 / Testnet 实盘）。

---

## 修复优先级建议

| 优先级 | 问题 | 理由 |
|:--|:---|:---|
| P0 | #1 未来函数 | 回测结果完全不可信，必须先修 |
| P0 | #2 做空逻辑 | 策略能力的根本性缺失 |
| P1 | #3 LLM 调用频率 | 成本 + 速度 + 逻辑一致性 |
| P1 | #5 交易成本 | 短线策略的隐藏收益吞噬 |
| P2 | #4 仓位管理 | 影响风险收益特征 |
| P2 | #6 high/low 数据 | 影响 LLM 预测质量 |
| P3 | #7 多币种 | 架构扩展 |
| P3 | #8 多持仓 | 架构扩展 |
