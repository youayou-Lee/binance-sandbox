# Binance Sandbox

> 连接 Binance 模拟沙盘 (Testnet) API，为自动化交易打基础。

## 目标

1. ✅ 程序化接入 Binance Spot Testnet
2. ✅ 基础策略回测框架（`harness/`）
3. ✅ LLM 驱动的自动交易引擎（`sandbox_trader.py`，实验性）
4. ✅ 实时监控面板（`dashboard.py`）
5. ✅ LLM 预测能力评估（`predict.py`）
6. ⬜ 订单管理（限价/市价/止盈止损 — Testnet 真实下单）
7. ⬜ WebSocket 实时行情订阅
8. ⬜ LLM 数据传递形式优化（参见 `docs/llm-data-transmission.md`）

## 快速开始

### 前置条件

1. 注册 [Binance Spot Testnet](https://testnet.binance.vision/)
2. 在 Dashboard 创建 API Key（HMAC-SHA256）
3. 通过 Faucet 领取测试 USDT / BTC

### 配置

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 Testnet API Key 和 Secret：

```env
BINANCE_TESTNET_API_KEY=your_api_key_here
BINANCE_TESTNET_API_SECRET=your_api_secret_here
```

### 运行

```bash
# 完整连接测试
uv run python main.py

# 仅测试网络连通性
uv run python main.py --ping

# 查看账户余额
uv run python main.py --balances

# 查看 BTCUSDT 行情
uv run python main.py --prices

# 查看全部 USDT 交易对行情
uv run python main.py --prices all
```

### 预期输出

```
==================================================
Binance Testnet — 完整连接测试
==================================================
17:58:30 [INFO] 测试 Binance Testnet 连通性...
17:58:31 [INFO] ✓ 连通正常！返回: {}
17:58:31 [INFO] ✓ 服务器时间: 1750291110000 (UTC+8: 2026-06-18 17:58:30)
17:58:31 [INFO] 查询账户余额...
17:58:31 [INFO]   账户余额:
17:58:31 [INFO]     USDT: 可用=10000.0  锁定=0.0
17:58:31 [INFO]     BTC: 可用=1.0  锁定=0.0
17:58:31 [INFO]   BTCUSDT: 68234.50

✓ 全部测试通过！Binance Testnet 连接正常。
```

## 技术栈

| 组件 | 版本 |
|:---|:---|
| Python | 3.12 |
| python-binance | 1.0.37 |
| python-dotenv | 1.x |

## 目录结构

```
binance-sandbox/
├── README.md           # 本文件
├── CLAUDE.md           # 项目架构与开发指引
├── main.py             # 入口：连接测试
├── config.py           # 配置管理
├── llm.py              # 共享 LLM 预测模块
├── sandbox_trader.py   # 纸面交易机器人（实验性）
├── backtest.py         # 回测 CLI 入口
├── predict.py          # LLM 预测能力评估
├── dashboard.py        # Flask 实时监控面板
├── harness/            # 回测引擎子包
│   ├── data.py         # K 线数据 + Parquet 缓存
│   ├── strategy.py     # 策略层
│   ├── run.py          # 回测核心循环
│   └── metrics.py      # 绩效指标
├── docs/               # 设计文档
│   └── llm-data-transmission.md
├── data/               # K 线缓存（.parquet）
├── logs/               # 日志目录
├── .env.example        # 环境变量模板
├── .env                # 个人 API Key（不提交）
├── pyproject.toml      # 项目配置
└── .venv/              # 虚拟环境
```
