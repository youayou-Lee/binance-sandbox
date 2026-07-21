"""
Backtest engine: feeds klines to strategy one by one, records each trade.

Strategy: LLM-powered directional prediction (做多/做空) with TP/SL.
For spot trading: 做多 signals BUY, 做空 signals SELL (close position).

Output: list of trades (each is a dict) + final portfolio value.
"""

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
    position = 0.0  # base asset held
    trades: list[dict] = []
    in_position = False
    entry_price = 0.0
    entry_time = None
    tp = None
    sl = None

    # Need enough history for strategy to work (lookback=100)
    MIN_BARS = 100

    for i in range(MIN_BARS, len(df)):
        pred = decide(prices[: i + 1], df["high"].tolist()[: i + 1], df["low"].tolist()[: i + 1])
        current_price = prices[i]
        current_time = df.iloc[i]["timestamp"]

        if pred is None:
            continue

        direction = pred.get("方向", "")
        pred_tp = pred.get("止盈", None)
        pred_sl = pred.get("止损", None)

        if direction == "做多" and not in_position:
            # BUY: go all-in
            position = cash / current_price
            cash = 0.0
            in_position = True
            entry_price = current_price
            entry_time = current_time
            tp = float(pred_tp) if pred_tp is not None else current_price * 1.02
            sl = float(pred_sl) if pred_sl is not None else current_price * 0.99

        elif direction == "做空" and in_position:
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
                    "direction": "做多",
                    "tp": round(tp, 2) if tp else None,
                    "sl": round(sl, 2) if sl else None,
                }
            )
            position = 0.0
            in_position = False
            tp = None
            sl = None

        # Check TP/SL while in position
        if in_position:
            if tp and current_price >= tp:
                cash = position * current_price
                pnl_pct = (current_price - entry_price) / entry_price * 100
                trades.append(
                    {
                        "entry_time": str(entry_time),
                        "exit_time": str(current_time),
                        "entry_price": round(entry_price, 2),
                        "exit_price": round(current_price, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "direction": "做多",
                        "exit_reason": "TP",
                        "tp": round(tp, 2),
                        "sl": round(sl, 2) if sl else None,
                    }
                )
                position = 0.0
                in_position = False
                tp = None
                sl = None
            elif sl and current_price <= sl:
                cash = position * current_price
                pnl_pct = (current_price - entry_price) / entry_price * 100
                trades.append(
                    {
                        "entry_time": str(entry_time),
                        "exit_time": str(current_time),
                        "entry_price": round(entry_price, 2),
                        "exit_price": round(current_price, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "direction": "做多",
                        "exit_reason": "SL",
                        "tp": round(tp, 2) if tp else None,
                        "sl": round(sl, 2),
                    }
                )
                position = 0.0
                in_position = False
                tp = None
                sl = None

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
                "direction": "做多",
            }
        )

    final_value = cash
    return trades, final_value
