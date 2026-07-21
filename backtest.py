"""
Backtest entry point.

Usage:
    uv run python backtest.py                          # BTCUSDT, 1h, 30天
    uv run python backtest.py --symbol ETHUSDT         # 换币种
    uv run python backtest.py --interval 15m           # 15分钟线
    uv run python backtest.py --limit 100              # 只测100根K线
    uv run python backtest.py --capital 50000          # 初始资金5万
    uv run python backtest.py --force                  # 强制重新拉数据
"""

import argparse
import sys

from harness.run import backtest
from harness.data import CACHE_DIR
from harness.metrics import print_report


def main():
    parser = argparse.ArgumentParser(description="Crypto Agent 回测系统 v0.1")
    parser.add_argument("--symbol", default="BTCUSDT", help="交易对 (默认 BTCUSDT)")
    parser.add_argument("--interval", default="1h", help="K线周期 (默认 1h)")
    parser.add_argument("--limit", type=int, default=720, help="K线数量 (默认 720 ≈ 30天)")
    parser.add_argument("--capital", type=float, default=10_000, help="初始资金 USDT (默认 10,000)")
    parser.add_argument("--force", action="store_true", help="强制重新拉取数据")
    parser.add_argument("--clear-cache", action="store_true", help="清空缓存后重新拉取")
    args = parser.parse_args()

    if args.clear_cache:
        import shutil

        shutil.rmtree(CACHE_DIR)
        print("  ✓ 缓存已清空")
        CACHE_DIR.mkdir(exist_ok=True)

    print(f"\n  交易对: {args.symbol}")
    print(f"  周期:   {args.interval}")
    print(f"  数据量: {args.limit} 根 K 线 ≈ {args.limit // 24:.0f} 天")
    print(f"  本金:   ${args.capital:,.2f}")
    print("  " + "-" * 40)

    trades, final_value = backtest(
        symbol=args.symbol,
        interval=args.interval,
        limit=args.limit,
        capital=args.capital,
    )

    print_report(trades, args.capital, final_value, args.symbol)


if __name__ == "__main__":
    main()
