"""
Backtest engine: feeds klines to strategy one by one, records each trade.

Output: list of trades (each is a dict) + final portfolio value.
"""

import pandas as pd

from .data import fetch_klines
from .strategy import decide


def backtest(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    limit: int = 720,
    capital: float = 10_000.0,
) -> tuple[list[dict], float]:
    """
    Run a single backtest.

    Returns:
        trades: list of trade dicts with entry/exit times, prices, pnl%
        final_value: cash + position value at end
    """
    df = fetch_klines(symbol, interval, limit)
    prices = df["close"].tolist()

    cash = capital
    position = 0.0  # BTC held
    trades: list[dict] = []
    in_position = False
    entry_price = 0.0
    entry_time = None

    for i in range(len(df)):
        action = decide(prices[: i + 1])
        current_price = prices[i]
        current_time = df.iloc[i]["timestamp"]

        if action == 1 and not in_position:
            # BUY: go all-in
            position = cash / current_price
            cash = 0.0
            in_position = True
            entry_price = current_price
            entry_time = current_time

        elif action == -1 and in_position:
            # SELL: close position
            cash = position * current_price
            pnl_pct = (current_price - entry_price) / entry_price * 100
            trades.append(
                {
                    "entry_time": str(entry_time),
                    "exit_time": str(current_time),
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(current_price, 2),
                    "pnl_pct": round(pnl_pct, 2),
                }
            )
            position = 0.0
            in_position = False

    # Close any remaining position at last price
    if in_position:
        cash = position * prices[-1]
        pnl_pct = (prices[-1] - entry_price) / entry_price * 100
        trades.append(
            {
                "entry_time": str(entry_time),
                "exit_time": str(df.iloc[-1]["timestamp"]),
                "entry_price": round(entry_price, 2),
                "exit_price": round(prices[-1], 2),
                "pnl_pct": round(pnl_pct, 2),
            }
        )

    final_value = cash if not in_position else cash  # already closed
    return trades, final_value
