# Binance Sandbox — Project Instructions

> 基于 LLM 的加密货币自动化交易实验平台，运行在 Binance Spot Testnet。

## 项目架构

```
binance-sandbox/
├── main.py               # 入口：Binance Testnet 连接测试
├── config.py             # 配置管理（.env → BINANCE_CONFIG）
├── llm.py                # 共享 LLM 模块：DeepSeek 方向预测
├── sandbox_trader.py     # 纸面交易机器人（实验性，待重构）
├── backtest.py           # 回测 CLI 入口
├── predict.py            # LLM 预测能力独立评估
├── dashboard.py          # Flask 实时监控面板
│
├── harness/              # 回测引擎子包
│   ├── data.py           # K 线数据获取 + Parquet 缓存
│   ├── strategy.py       # 策略层（委托 llm.py）
│   ├── run.py            # 回测引擎核心循环
│   └── metrics.py        # 绩效指标计算 + 报告
│
├── data/                 # K 线缓存（.parquet，gitignore）
├── logs/                 # 日志目录（gitignore）
├── docs/                 # 设计文档
└── templates/            # Flask 模板（预留）
```

## 模块依赖关系

```
config.py  ←── 所有模块
llm.py     ←── sandbox_trader.py, harness/strategy.py
harness/   ←── backtest.py, predict.py
dashboard.py ←── trader_state.json, trader.log（sandbox_trader.py 产出）
```

## 技术约定

- **Python 包管理**：使用 `uv`（`uv add xxx` 安装依赖，`uv run python xxx.py` 运行脚本）
- **Python 版本**：3.12+
- **Lint**：`ruff check`
- **测试**：`pytest`
- **API Key**：通过 `.env` 管理（复制 `.env.example` 填入真实 key）
- **Binance 公共数据**：通过 SOCKS5 代理 `127.0.0.1:7890` 访问
- **LLM 调用**：通过 OpenAI 兼容 SDK 调 DeepSeek Chat API

## 数据流

```
Binance 公共 API (代理) → harness/data.py → Parquet 缓存 → 策略/回测/预测评估
Binance Testnet API     → sandbox_trader.py（未来：真实下单）

DeepSeek API            → llm.py → 方向预测 {做多/做空, TP, SL, 理由}
```

## 已知架构问题

1. **sandbox_trader.py 与 harness/ 职责重叠**：`sandbox_trader.py` 目前是本地模拟交易（不调 testnet 下单接口），其纸面交易功能应与回测引擎统一。短期保留用于验证实时数据管道，长期应合并或明确分工。
2. **回测引擎仅支持做多**：`harness/run.py` 中做空信号 = 平仓，而 `llm.py` 输出同时包含做多做空。需要扩展回测支持双向交易。
3. **LLM prompt 待优化**：目前传递裸价格列表，参见 `docs/llm-data-transmission.md`。

## 常用命令

```bash
# 连接测试
uv run python main.py

# 回测
uv run python backtest.py --symbol BTCUSDT --interval 1h --limit 720

# 预测能力评估
uv run python predict.py --count 100 --threads 5

# 实时交易（实验性）
uv run python sandbox_trader.py --once

# 监控面板
uv run python dashboard.py

# Lint
uv run ruff check .

# 安装新依赖
uv add <package-name>
```
