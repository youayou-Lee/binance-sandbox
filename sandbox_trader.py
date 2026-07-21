"""
纸面交易机器人：基于 LLM 预测，在 Binance 测试网模拟交易。

策略：
  - 20 个涨跌币，每个 5% 仓位
  - 每小时调 LLM 重新预测
  - 按 TP/SL 自动平仓
  - 24 小时不间断运行
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from binance.client import Client
from config import BINANCE_CONFIG

# ─── 配置 ─────────────────────────────────────────────

TRADING_COINS = [
    "ATMUSDT", "SYNUSDT", "PSGUSDT", "BARUSDT", "AAVEUSDT",
    "MUBUSDT", "DCRUSDT", "ELFUSDT", "JUVUSDT", "ASRUSDT",
    "BIFIUSDT", "REUSDT", "ALICEUSDT", "NEBLUSDT", "OPGUSDT",
    "KITEUSDT", "THETAUSDT", "STGUSDT", "AUTOUSDT", "MIRUSDT",
]

CAPITAL = 10_000.0          # 初始资金 (USDT)
ALLOC_PER_COIN = 0.05       # 每个币 5%
INTERVAL_SEC = 3600         # 1h 循环
CHECK_SEC = 10              # TP/SL 检查间隔
LOOKBACK = 100              # 喂给 LLM 的 K 线数
LOOKAHEAD = 12              # 预测窗口

STATE_FILE = Path(__file__).parent / "trader_state.json"


# ─── 数据 & API ──────────────────────────────────────

def get_binance_client():
    """初始化 Binance 客户端（公共数据 + testnet 交易）。"""
    # 公共数据走代理，不需要 key
    pub = Client("", "", ping=False)
    pub.session.proxies.update({"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"})
    # 交易用 testnet
    cfg = BINANCE_CONFIG
    tra = Client(cfg["api_key"], cfg["api_secret"], testnet=True, ping=False)
    return pub, tra


def fetch_klines_batch(pub: Client, symbols: list[str], limit: int = 200):
    """批量获取最新 K 线数据。"""
    result = {}
    for sym in symbols:
        try:
            raw = pub.get_klines(symbol=sym, interval="1h", limit=limit)
            closes = [float(k[4]) for k in raw]
            highs = [float(k[2]) for k in raw]
            lows = [float(k[3]) for k in raw]
            result[sym] = {"prices": closes, "highs": highs, "lows": lows}
        except Exception as e:
            logging.warning(f"  [{sym}] 获取数据失败: {e}")
            result[sym] = None
        time.sleep(0.05)  # 避免限流
    return result


def get_current_prices(pub: Client, symbols: list[str]) -> dict:
    """获取当前价格。"""
    prices = {}
    for sym in symbols:
        try:
            t = pub.get_symbol_ticker(symbol=sym)
            prices[sym] = float(t["price"])
        except:
            pass
        time.sleep(0.05)
    return prices


def llm_predict(prices: list[float]) -> dict | None:
    """调 LLM 预测。委托给共享 llm 模块。"""
    from llm import predict
    return predict(prices, lookback=LOOKBACK)


# ─── 交易状态管理 ────────────────────────────────────

def load_state() -> dict:
    """从文件加载交易状态。"""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"capital": CAPITAL, "positions": {}, "trades": [], "cycle": 0}


def save_state(state: dict):
    """保存交易状态。"""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_fee(price: float, qty: float, is_entry: bool = True) -> float:
    """估算手续费（现货 0.1% 双边）。"""
    return price * qty * 0.001


# ─── 主循环 ──────────────────────────────────────────

def trade_cycle(state: dict, pub: Client, tra: Client):
    """执行一轮交易。"""
    state["cycle"] += 1
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    logging.info(f"\n{'='*60}")
    logging.info(f"  第 {state['cycle']} 轮 @ {ts}")
    logging.info(f"{'='*60}")

    # 获取最新数据
    data = fetch_klines_batch(pub, TRADING_COINS, LOOKBACK + 10)
    prices_now = get_current_prices(pub, TRADING_COINS)

    # 遍历每个币
    for coin in TRADING_COINS:
        coin_data = data.get(coin)
        if coin_data is None or len(coin_data["prices"]) < LOOKBACK:
            continue

        prices = coin_data["prices"]
        current_price = prices_now.get(coin)
        if not current_price:
            continue

        pos = state["positions"].get(coin)
        in_position = pos and pos["status"] == "open"

        if in_position:
            # 检查 TP/SL
            entry = pos["entry_price"]
            tp = pos["tp"]
            sl = pos["sl"]
            direction = pos["direction"]

            if direction == "做多":
                if current_price >= tp:
                    pnl = (current_price - entry) / entry * 100
                    logging.info(f"  [{coin}] ✅ TP触及 @{current_price:.2f} 盈亏={pnl:+.2f}%")
                    state["capital"] += state["capital"] * ALLOC_PER_COIN * pnl / 100
                    state["positions"][coin]["status"] = "closed"
                    state["positions"][coin]["exit_price"] = current_price
                    state["positions"][coin]["exit_reason"] = "TP"
                    state["positions"][coin]["pnl_pct"] = round(pnl, 2)
                    state["trades"].append(state["positions"].pop(coin, None))
                    continue
                elif current_price <= sl:
                    pnl = (current_price - entry) / entry * 100
                    logging.info(f"  [{coin}] ❌ SL触及 @{current_price:.2f} 盈亏={pnl:+.2f}%")
                    state["capital"] += state["capital"] * ALLOC_PER_COIN * pnl / 100
                    state["positions"][coin]["status"] = "closed"
                    state["positions"][coin]["exit_price"] = current_price
                    state["positions"][coin]["exit_reason"] = "SL"
                    state["positions"][coin]["pnl_pct"] = round(pnl, 2)
                    state["trades"].append(state["positions"].pop(coin, None))
                    continue
            else:  # 做空
                if current_price <= tp:
                    pnl = (entry - current_price) / entry * 100
                    logging.info(f"  [{coin}] ✅ TP触及 @{current_price:.2f} 盈亏={pnl:+.2f}%")
                    state["capital"] += state["capital"] * ALLOC_PER_COIN * pnl / 100
                    state["positions"][coin]["status"] = "closed"
                    state["positions"][coin]["exit_price"] = current_price
                    state["positions"][coin]["exit_reason"] = "TP"
                    state["positions"][coin]["pnl_pct"] = round(pnl, 2)
                    state["trades"].append(state["positions"].pop(coin, None))
                    continue
                elif current_price >= sl:
                    pnl = (entry - current_price) / entry * 100
                    logging.info(f"  [{coin}] ❌ SL触及 @{current_price:.2f} 盈亏={pnl:+.2f}%")
                    state["capital"] += state["capital"] * ALLOC_PER_COIN * pnl / 100
                    state["positions"][coin]["status"] = "closed"
                    state["positions"][coin]["exit_price"] = current_price
                    state["positions"][coin]["exit_reason"] = "SL"
                    state["positions"][coin]["pnl_pct"] = round(pnl, 2)
                    state["trades"].append(state["positions"].pop(coin, None))
                    continue

            # 持有中，每小时用最新数据重新评估
            logging.info(f"  [{coin}] 持仓中: {direction} @{entry:.2f} TP={tp:.2f} SL={sl:.2f} 现价={current_price:.2f}")
            continue

        # 无持仓 → 开新仓
        pred = llm_predict(prices)
        if pred is None:
            continue

        direction = pred["方向"]
        tp = pred["止盈"]
        sl = pred["止损"]
        # Auto-correct TP/SL: ensure correct direction
        if direction == "做多":
            tp = max(tp, current_price * 1.001)  # TP must be above entry
            sl = min(sl, current_price * 0.999)  # SL must be below entry
        else:  # 做空
            tp = min(tp, current_price * 0.999)  # TP must be below entry
            sl = max(sl, current_price * 1.001)  # SL must be above entry
        # Minimum distance check
        min_dist = current_price * 0.002  # 0.2%
        if direction == "做多":
            tp = max(tp, current_price + min_dist)
            sl = min(sl, current_price - min_dist)
        else:
            tp = min(tp, current_price - min_dist)
            sl = max(sl, current_price + min_dist)

        # 用固定 TP/SL（LLM 只提供方向）
        if direction == "做多":
            tp = current_price * 1.02   # 2% take profit
            sl = current_price * 0.99   # 1% stop loss
        else:
            tp = current_price * 0.98   # 2% take profit (short: price down)
            sl = current_price * 1.01   # 1% stop loss (short: price up)
        
        pos_size = state["capital"] * ALLOC_PER_COIN / current_price
        fee = get_fee(current_price, pos_size)

        state["positions"][coin] = {
            "coin": coin,
            "direction": direction,
            "entry_price": current_price,
            "tp": tp,
            "sl": sl,
            "size": round(pos_size, 6),
            "entry_time": ts,
            "status": "open",
            "fee": round(fee, 2),
        }
        logging.info(f"  [{coin}] 🆕 {direction} @{current_price:.2f} "
                     f"TP={tp:.2f} SL={sl:.2f} "
                     f"仓位={pos_size:.4f} ({ALLOC_PER_COIN*100:.0f}%)")

    # 报告
    open_positions = sum(1 for p in state["positions"].values() if p["status"] == "open")
    logging.info(f"\n  📊 资金: ${state['capital']:.2f} | 持仓: {open_positions}/{len(TRADING_COINS)}")
    save_state(state)


def main():
    parser = argparse.ArgumentParser(description="纸面交易机器人")
    parser.add_argument("--once", action="store_true", help="只跑一轮")
    parser.add_argument("--reset", action="store_true", help="重置状态")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler("trader.log"),
            logging.StreamHandler(),
        ],
    )

    if args.reset:
        STATE_FILE.unlink(missing_ok=True)
        logging.info("状态已重置")

    state = load_state()
    pub, tra = get_binance_client()

    if state["capital"] <= 0:
        logging.error("资金不足，停止交易")
        return

    logging.info(f"  初始资金: ${CAPITAL}")
    logging.info(f"  当前资金: ${state['capital']:.2f}")
    logging.info(f"  币种数:   {len(TRADING_COINS)}")
    logging.info(f"  每币仓位: {ALLOC_PER_COIN*100:.0f}%")
    logging.info(f"  轮次间隔: {INTERVAL_SEC//60} 分钟")

    if args.once:
        trade_cycle(state, pub, tra)
        return

    # 连续运行
    while True:
        try:
            trade_cycle(state, pub, tra)
            # 在下一轮之前监控 TP/SL
            next_cycle = time.time() + INTERVAL_SEC
            while time.time() < next_cycle:
                # 检查 TP/SL (每 CHECK_SEC)
                prices_now = get_current_prices(pub, TRADING_COINS)
                for coin in TRADING_COINS:
                    pos = state["positions"].get(coin)
                    if not pos or pos["status"] != "open":
                        continue
                    current_price = prices_now.get(coin)
                    if not current_price:
                        continue
                    direction = pos["direction"]
                    tp = pos["tp"]
                    sl = pos["sl"]
                    entry = pos["entry_price"]

                    if direction == "做多":
                        if current_price >= tp:
                            pnl = (current_price - entry) / entry * 100
                            state["capital"] += state["capital"] * ALLOC_PER_COIN * pnl / 100
                            logging.info(f"  [{coin}] ✅ TP @{current_price:.2f} +{pnl:.2f}%")
                            pos["status"] = "closed"
                            pos["exit_price"] = current_price
                            pos["exit_reason"] = "TP"
                            pos["pnl_pct"] = round(pnl, 2)
                            state["trades"].append(pos)
                            del state["positions"][coin]
                        elif current_price <= sl:
                            pnl = (current_price - entry) / entry * 100
                            state["capital"] += state["capital"] * ALLOC_PER_COIN * pnl / 100
                            logging.info(f"  [{coin}] ❌ SL @{current_price:.2f} {pnl:.2f}%")
                            pos["status"] = "closed"
                            pos["exit_price"] = current_price
                            pos["exit_reason"] = "SL"
                            pos["pnl_pct"] = round(pnl, 2)
                            state["trades"].append(pos)
                            del state["positions"][coin]
                    else:  # 做空
                        if current_price <= tp:
                            pnl = (entry - current_price) / entry * 100
                            state["capital"] += state["capital"] * ALLOC_PER_COIN * pnl / 100
                            logging.info(f"  [{coin}] ✅ TP @{current_price:.2f} +{pnl:.2f}%")
                            pos["status"] = "closed"
                            pos["exit_price"] = current_price
                            pos["exit_reason"] = "TP"
                            pos["pnl_pct"] = round(pnl, 2)
                            state["trades"].append(pos)
                            del state["positions"][coin]
                        elif current_price >= sl:
                            pnl = (entry - current_price) / entry * 100
                            state["capital"] += state["capital"] * ALLOC_PER_COIN * pnl / 100
                            logging.info(f"  [{coin}] ❌ SL @{current_price:.2f} {pnl:.2f}%")
                            pos["status"] = "closed"
                            pos["exit_price"] = current_price
                            pos["exit_reason"] = "SL"
                            pos["pnl_pct"] = round(pnl, 2)
                            state["trades"].append(pos)
                            del state["positions"][coin]

                save_state(state)
                time.sleep(CHECK_SEC)
        except KeyboardInterrupt:
            logging.info("\n⏹️  停止交易")
            save_state(state)
            break
        except Exception as e:
            logging.error(f"错误: {e}")
            save_state(state)
            time.sleep(60)


if __name__ == "__main__":
    main()
