"""
Metrics: eats trade log, outputs performance report.
No I/O, pure calculation.
"""

import math


def calculate(trades: list[dict], initial_capital: float, final_capital: float) -> dict:
    """Calculate performance metrics from trade log."""

    total_return = (final_capital / initial_capital - 1) * 100
    total_trades = len(trades)

    if total_trades == 0:
        return {
            "total_return_pct": round(total_return, 2),
            "total_trades": 0,
            "win_rate_pct": 0.0,
            "profit_factor": 0.0,
            "avg_win_pct": 0.0,
            "avg_loss_pct": 0.0,
            "max_consecutive_losses": 0,
            "best_trade_pct": 0.0,
            "worst_trade_pct": 0.0,
        }

    winning = [t for t in trades if t["pnl_pct"] > 0]
    losing = [t for t in trades if t["pnl_pct"] <= 0]

    win_rate = len(winning) / total_trades * 100

    avg_win = sum(t["pnl_pct"] for t in winning) / len(winning) if winning else 0
    avg_loss = sum(t["pnl_pct"] for t in losing) / len(losing) if losing else 0

    total_gross_profit = sum(t["pnl_pct"] for t in winning)
    total_gross_loss = abs(sum(t["pnl_pct"] for t in losing))
    profit_factor = total_gross_profit / total_gross_loss if total_gross_loss > 0 else float("inf")

    # Consecutive losses
    max_consec = 0
    current_streak = 0
    for t in trades:
        if t["pnl_pct"] <= 0:
            current_streak += 1
            max_consec = max(max_consec, current_streak)
        else:
            current_streak = 0

    best_trade = max(trades, key=lambda t: t["pnl_pct"])
    worst_trade = min(trades, key=lambda t: t["pnl_pct"])

    return {
        "total_return_pct": round(total_return, 2),
        "total_trades": total_trades,
        "win_rate_pct": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "max_consecutive_losses": max_consec,
        "best_trade_pct": round(best_trade["pnl_pct"], 2),
        "worst_trade_pct": round(worst_trade["pnl_pct"], 2),
    }


def print_report(
    trades: list[dict],
    initial_capital: float,
    final_capital: float,
    symbol: str = "BTCUSDT",
):
    """Pretty-print the backtest report."""
    m = calculate(trades, initial_capital, final_capital)
    width = 50

    print()
    print("=" * width)
    print("         回测评测报告")
    print("=" * width)
    print(f"  交易对:        {symbol}")
    print(f"  初始资金:      ${initial_capital:,.2f}")
    print(f"  最终资金:      ${final_capital:,.2f}")
    print(f"  总收益率:      {m['total_return_pct']:+.2f}%")
    print("-" * width)
    print(f"  总交易次数:    {m['total_trades']}")
    print(f"  胜率:          {m['win_rate_pct']}%")
    print(f"  盈亏比:        {m['profit_factor']}")
    print(f"  平均盈利:      {m['avg_win_pct']:+.2f}%")
    print(f"  平均亏损:      {m['avg_loss_pct']:.2f}%")
    print(f"  最大连亏:      {m['max_consecutive_losses']} 次")
    print(f"  最佳单笔:      {m['best_trade_pct']:+.2f}%")
    print(f"  最差单笔:      {m['worst_trade_pct']:.2f}%")
    print("=" * width)

    if m["total_trades"] > 0:
        print("\n交易明细 (最近 5 笔):")
        print(f"  {'时间':>20}  {'方向':>4}  {'入场':>10}  {'出场':>10}  {'盈亏':>8}")
        print("  " + "-" * 58)
        for t in trades[-5:]:
            label = "BUY " if t["pnl_pct"] >= 0 else "SELL"
            print(
                f"  {str(t['exit_time'])[:19]:>20}  {label:>4}  "
                f"{t['entry_price']:>10.2f}  {t['exit_price']:>10.2f}  "
                f"{t['pnl_pct']:>+7.2f}%"
            )
