# LLM 市场数据传递形式 — 方向文档

> 状态：设计阶段 | 最后更新：2026-07-21

## 问题

当前 `llm.py` 将最近 100 根 K 线的收盘价以**裸数字列表**形式传给 DeepSeek：

```python
recent = prices[-lookback:][::-1]  # newest first
prompt = f"Recent {lookback} closing prices (newest->oldest):\n{recent}\n..."
```

这种方式可能存在信息损失和 LLM 理解困难。本文档梳理替代方案，设计对比实验。

## 候选方案

### A. 裸价格列表（当前方案）

**输入形式：**
```
Recent 100 closing prices (newest->oldest):
[68234.5, 68102.3, 68089.1, ...]
Range: 67500 - 68500
Current: 68234
```

**优点：** Token 消耗低，信息无预处理偏差。

**缺点：**
- LLM 需要自行从数字推演趋势、波动特征
- 丢失 OHLCV 中的高/低/量信息
- "newest→oldest" 排序反直觉（人类习惯 oldest→newest）
- BTC 级别价格小数部分被 `{low:.0f}` 截断

**适用场景：** 基线对照。

---

### B. OHLCV 结构化表格

**输入形式：** Markdown 表格，最近 N 根 K 线：

```
| Time              | Open    | High    | Low     | Close   | Volume   |
|-------------------|---------|---------|---------|---------|----------|
| 2026-07-21 14:00  | 68102.3 | 68290.0 | 68050.1 | 68234.5 | 1234.56  |
| 2026-07-21 13:00  | 68000.0 | 68150.2 | 67980.3 | 68102.3 | 1100.23  |
...
```

**优点：** 结构化、完整（O/H/L/C/V 都有）、时间戳保留。

**缺点：** Token 消耗高（20 行表头 + 数据），DeepSeek 对表格的数值推理能力待验证。

**适用场景：** 短窗口（N ≤ 20）时可能优于裸列表。

---

### C. 技术指标摘要（标量值）

**输入形式：** 预计算的关键指标：

```
Market Data Summary (1h candles, 100 bars):

Price Action:
  Current: 68234.50
  24h High/Low: 69100 / 67500
  20-period High/Low: 69100 / 66000

Trend Indicators:
  MA7:   68150  (price above ↑)
  MA25:  67890  (price above ↑)
  MA99:  66500  (price above ↑)
  MA7/MA25 cross: bullish (7 crossed above 25 at bar -3)

Momentum:
  RSI(14):  62.3  (neutral-bullish, not overbought)
  MACD:     145.2  (above signal line, histogram expanding ↑)
  MACD Signal: 120.1

Volatility:
  Bollinger Band Width: 3.2%  (normal range)
  ATR(14):  420.5  (1.4% of price)
  Current vs BB Upper/Mid/Lower: above mid, 68% to upper

Volume:
  Last 5 bars avg volume: 1450  (120% of 20-bar avg → elevated)
```

**优点：**
- Token 极低（~300 tokens vs 裸列表的 ~800+ tokens）
- 直接给出交易员常用的结构化信号
- LLM 不需要做数学计算，专注于推理判断

**缺点：**
- 指标选择 = 信息过滤 = 可能丢失 LLM 能自行发现的非传统模式
- 指标参数（MA 周期、RSI 窗口等）是主观选择
- 预处理依赖，增加了代码复杂度

**适用场景：** 最可能优于裸列表的方案。

---

### D. 价格变化率序列（收益率）

**输入形式：** 用收益率替代绝对价格：

```
Recent 100 hourly returns (%) (newest->oldest):
[+0.19, -0.02, +0.31, -0.15, +0.08, ...]
```

**优点：**
- 数值范围小（±几个百分点），LLM 更容易处理
- 跨币种可比（BTC +0.1% 和 ETH +0.1% 同样表达）
- 保留了完整的时间序列信息

**缺点：**
- 丢失绝对价格水平（$68k 的 BTC 和 $0.01 的某种币，行为可能截然不同）
- 同样有"newest→oldest"排序问题

**适用场景：** 多币种预测时，收益率比绝对价格更具可比性。

---

### E. 自然语言叙述

**输入形式：** 用人类交易员的分析语言描述：

```
BTCUSDT 1h Market Summary:
Over the past 100 hours, BTC has been in a steady uptrend, rising from 66000 to 68234 (+3.4%).
The move accelerated 12 hours ago, with 5 consecutive green candles pushing through the 68000 resistance.
Price is now consolidating near 68200 with decreasing volume, forming a potential flag pattern.
RSI is at 62 — bullish but approaching overbought territory.
The 7-period MA just crossed above the 25-period MA, confirming short-term momentum.
Support sits at 67500 (prior resistance turned support), resistance at 69100 (24h high).
Volatility is normal (Bollinger Band width 3.2%), no signs of an impending breakout.
```

**优点：**
- LLM 最擅长理解和推理的形式（自然语言）
- 可以注入领域知识（"forming a flag pattern"）
- 同时包含定性和定量信息

**缺点：**
- 叙述质量取决于预处理代码的质量
- 主观性较强（"steady uptrend" vs "choppy rise" 是解释问题）
- 不同币种的叙述模板化可能导致 LLM 给出同质化预测

**适用场景：** 如果 LLM 本身有较强的金融 NLP 能力，这可能是最优方案。

---

### F. 多模态（K 线图截图 + 文本）

**输入形式：** 给 LLM 传一张 K 线图（含均线、布林带）的截图 + 简短文本说明。

**优点：** 视觉模式识别是 LLM 的强项（尤其是支持视觉的模型）。

**缺点：**
- DeepSeek Chat 不支持图片输入（Vision 能力需确认）
- Token 消耗极高
- 渲染图表需要额外依赖（matplotlib / mplfinance）

**适用场景：** 如果切换到 GPT-4o / Claude 等支持视觉的模型可尝试。

---

### G. 混合方案（指标 + 收益率序列 + 简述）

**输入形式：**
```
BTCUSDT | 1h | 100 bars | Current: 68234.50

Price Returns (last 20 bars, oldest→newest, %):
+0.12, -0.05, +0.08, +0.31, +0.22, -0.10, +0.15, +0.09, -0.03, +0.18,
+0.25, +0.41, +0.30, -0.08, +0.05, -0.02, +0.11, -0.06, +0.04, +0.19

Indicators:
  MA7=68150(↑)  MA25=67890(↑)  MA99=66500(↑)  → uptrend confirmed
  RSI(14)=62.3  MACD=145.2↑  Vol=120% avg
  BB width=3.2%  ATR=420

Pattern: 5 consecutive higher closes, volume declining → possible exhaustion.
```

**优点：** 结合了 C（指标）和 D（收益率序列）的优点，并加入简单的模式识别。
**缺点：** 中等复杂度。

**适用场景：** 推荐作为第一轮实验的候选方案。

---

## 对比实验设计

### 评估方法

利用 `predict.py` 框架：同一批历史时间点，只改 `llm.py` 的 prompt，比较各方案的预测准确率。

```bash
# 对照组（当前方案 A）
uv run python predict.py --count 500 --threads 10 --coins BTCUSDT ETHUSDT SOLUSDT

# 实验组（方案 C/G/...）
# 修改 llm.py 的 predict() 函数后重新运行
```

### 评估指标

| 指标 | 含义 |
|:---|:---|
| 准确率（排除未触及） | TP 先于 SL 触发的比例 |
| 反指准确率 | 反向操作的准确率（>50% 说明 LLM 是反指） |
| 未触及率 | 12 根 K 线内 TP/SL 均未触发 |
| 方向分布 | 做多 vs 做空的比例是否均衡 |
| 按币种准确率 | 不同波动特征的币种表现差异 |

### 实验计划

| 阶段 | 方案 | 目标 |
|:---|:---|:---|
| 1（基线） | A. 裸价格列表 | 建立基线准确率 |
| 2 | C. 技术指标摘要 | 验证"指标优于裸数据"假设 |
| 3 | G. 混合方案 | 验证"指标+收益率序列"是否进一步提升 |
| 4 | E. 自然语言（如 2/3 不理想） | 验证 LLM 对叙事的理解能力 |

### 控制变量

- 同一个 DeepSeek Chat 模型
- 同一批历史时间点（random seed 固定）
- 同样的 lookback（100）和 lookahead（12）
- 同样的 TP/SL 判定逻辑

---

## 待办

- [ ] 实现方案 C 的 prompt 模板
- [ ] 实现方案 G 的 prompt 模板
- [ ] 运行 500 点对比实验
- [ ] 记录实验结果到本文档"实验结果"章节
- [ ] 根据结果选择最优方案，更新 `llm.py`
