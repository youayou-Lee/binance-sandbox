"""
Backtest entry point.

Usage:
    uv run python backtest.py                              # BTCUSDT, 1h, 720 bars, default params
    uv run python backtest.py --symbol ETHUSDT             # Different pair
    uv run python backtest.py --interval 15m --limit 200   # 15-min bars
    uv run python backtest.py --capital 50000              # Custom capital
    uv run python backtest.py --position-size 0.5          # Half-size positions
    uv run python backtest.py --commission 0.002           # 0.2% fee
    uv run python backtest.py --decision-interval 6        # Decide every 6 bars
    uv run python backtest.py --force                      # Re-fetch data
"""

import argparse

from harness.run import backtest
from harness.data import CACHE_DIR
from harness.metrics import print_report


def main():
    parser = argparse.ArgumentParser(description="Crypto Agent 回测系统 v0.2")
    parser.add_argument("--symbol", default="BTCUSDT", help="交易对 (默认 BTCUSDT)")
    parser.add_argument("--interval", default="1h", help="K线周期 (默认 1h)")
    parser.add_argument("--limit", type=int, default=720, help="K线数量 (默认 720)")
    parser.add_argument("--capital", type=float, default=10_000, help="初始资金 USDT (默认 10,000)")
    parser.add_argument("--position-size", type=float, default=1.0,
                        help="每次交易资金比例 0.0-1.0 (默认 1.0)")
    parser.add_argument("--commission", type=float, default=0.001,
                        help="手续费率 (默认 0.001 = 0.1%%)")
    parser.add_argument("--decision-interval", type=int, default=12,
                        help="决策间隔 K 线数 (默认 12, 1h=每12小时决策)")
    parser.add_argument("--force", action="store_true", help="强制重新拉取数据")
    parser.add_argument("--clear-cache", action="store_true", help="清空缓存后重新拉取")
    args = parser.parse_args()

    if args.clear_cache:
        import shutil
        shutil.rmtree(CACHE_DIR)
        print("  ✓ 缓存已清空")
        CACHE_DIR.mkdir(exist_ok=True)

    print(f"\n  交易对:       {args.symbol}")
    print(f"  周期:         {args.interval}")
    print(f"  数据量:       {args.limit} 根 K 线")
    print(f"  本金:         ${args.capital:,.2f}")
    print(f"  仓位比例:     {args.position_size * 100:.0f}%")
    print(f"  手续费:       {args.commission * 100:.2f}%")
    print(f"  决策间隔:     {args.decision_interval} bars")
    print("  " + "-" * 40)

    trades, final_value = backtest(
        symbol=args.symbol,
        interval=args.interval,
        limit=args.limit,
        capital=args.capital,
        position_size=args.position_size,
        commission=args.commission,
        decision_interval=args.decision_interval,
    )

    print_report(trades, args.capital, final_value, args.symbol)


if __name__ == "__main__":
    main()
