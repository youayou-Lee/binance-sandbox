# Binance Sandbox

> 连接 Binance 模拟沙盘 (Testnet) API，为自动化交易打基础。

## 目标

1. ✅ 程序化接入 Binance Spot Testnet
2. ⬜ 订单管理（限价/市价/止盈止损）
3. ⬜ WebSocket 实时行情订阅
4. ⬜ 账户资产与持仓管理
5. ⬜ 基础策略回测框架
6. ⬜ 自动交易引擎

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
├── README.md          # 本文件
├── main.py            # 入口脚本
├── config.py          # 配置管理
├── .env.example       # 环境变量模板
├── .env               # 个人 API Key（不提交）
├── data/              # 数据目录
├── logs/              # 日志目录
├── pyproject.toml     # 项目配置
└── .venv/             # 虚拟环境
```
