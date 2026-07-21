"""
Backtest engine v0.2: feeds klines to strategy, records each trade.

Fixes (from docs/backtest-issues.md):
  - #1 Look-ahead: predict on prices[:i], execute at bar i's open
  - #2 Short selling: 做空 opens short, 做多 opens long
  - #3 Decision interval: call LLM every N bars (default 12)
  - #4 Position sizing: configurable fraction (default 1.0 = all-in)
  - #5 Trading costs: commission deducted per trade (default 0.1%)
  - #6 TP/SL checked against intra-bar high/low

Output: list of trades (each is a dict) + final portfolio value.
"""

from .data import fetch_klines
from .strategy import decide


def backtest(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    limit: int = 720,
    capital: float = 10_000.0,
    position_size: float = 1.0,
    commission: float = 0.001,
    decision_interval: int = 12,
) -> tuple[list[dict], float]:
    """
    Run a single backtest.

    Args:
        symbol: Trading pair (e.g. BTCUSDT).
        interval: K-line interval (e.g. 1h, 15m).
        limit: Number of K-lines to fetch.
        capital: Initial capital in USDT.
        position_size: Fraction of capital per trade (0.0-1.0).
        commission: Fee rate per trade (default 0.001 = 0.1%).
        decision_interval: Bars between LLM calls (default 12).

    Returns:
        trades: list of trade dicts with entry/exit, pnl%, direction.
        final_value: portfolio value at end of backtest.
    """
    df = fetch_klines(symbol, interval, limit)
    prices = df["close"].tolist()
    highs = df["high"].tolist()
    lows = df["low"].tolist()

    cash = capital
    position = 0.0          # >0 = long base, <0 = short base, ==0 = flat
    trades: list[dict] = []
    entry_price = 0.0
    entry_time = None
    tp = None
    sl = None
    direction = None

    MIN_BARS = 100  # need enough history for strategy lookback
    last_decision = -999  # force first decision immediately

    for i in range(MIN_BARS, len(df)):
        current_open = float(df.iloc[i]["open"])
        current_high = highs[i]
        current_low = lows[i]
        current_close = prices[i]
        current_time = df.iloc[i]["timestamp"]

        # ── TP/SL check (every bar while in position) ──────────
        if position != 0:
            hit_tp = False
            hit_sl = False

            if direction == "做多":
                if current_high >= tp:
                    hit_tp = True
                if current_low <= sl:
                    hit_sl = True

                if hit_tp and hit_sl:
                    # both hit this bar — use open price to determine which came first
                    tp_dist = abs(current_open - tp)
                    sl_dist = abs(current_open - sl)
                    hit_tp = tp_dist <= sl_dist
                    hit_sl = not hit_tp

                if hit_tp:
                    exit_price = tp
                    pnl_pct = (exit_price - entry_price) / entry_price * 100
                elif hit_sl:
                    exit_price = sl
                    pnl_pct = (exit_price - entry_price) / entry_price * 100

            else:  # 做空
                if current_low <= tp:
                    hit_tp = True
                if current_high >= sl:
                    hit_sl = True

                if hit_tp and hit_sl:
                    tp_dist = abs(current_open - tp)
                    sl_dist = abs(current_open - sl)
                    hit_tp = tp_dist <= sl_dist
                    hit_sl = not hit_tp

                if hit_tp:
                    exit_price = tp
                    pnl_pct = (entry_price - exit_price) / entry_price * 100
                elif hit_sl:
                    exit_price = sl
                    pnl_pct = (entry_price - exit_price) / entry_price * 100

            if hit_tp or hit_sl:
                # Apply commission to both entry and exit
                gross_pnl = capital * position_size * pnl_pct / 100
                fee = capital * position_size * commission * 2  # entry + exit
                net_pnl_pct = (gross_pnl - fee) / (capital * position_size) * 100

                cash = capital + gross_pnl - fee
                capital = cash

                trades.append({
                    "entry_time": str(entry_time),
                    "exit_time": str(current_time),
                    "entry_price": round(entry_price, 6),
                    "exit_price": round(exit_price, 6),
                    "pnl_pct": round(net_pnl_pct, 2),
                    "direction": direction,
                    "exit_reason": "TP" if hit_tp else "SL",
                    "tp": round(tp, 6),
                    "sl": round(sl, 6),
                })
                position = 0.0
                direction = None
                tp = None
                sl = None
                continue

        # ── Decision point ─────────────────────────────────────
        bars_since_last = i - last_decision
        if bars_since_last < decision_interval:
            continue

        # Predict using data UP TO but NOT INCLUDING current bar (fix #1)
        pred = decide(prices[:i], highs[:i], lows[:i])

        if pred is None:
            continue

        pred_dir = pred.get("方向", "")
        pred_tp = pred.get("止盈", None)
        pred_sl = pred.get("止损", None)

        # Execute at current bar's open (approximation of "next bar open")
        exec_price = current_open
        last_decision = i

        # ── Open new position ──────────────────────────────────
        if position == 0:
            trade_capital = capital * position_size
            fee_entry = trade_capital * commission

            if pred_dir == "做多":
                quantity = (trade_capital - fee_entry) / exec_price
                position = quantity
                direction = "做多"
                entry_price = exec_price
                entry_time = current_time
                tp = float(pred_tp) if pred_tp is not None else exec_price * 1.02
                sl = float(pred_sl) if pred_sl is not None else exec_price * 0.99
                # Enforce TP > entry > SL for long
                tp = max(tp, exec_price * 1.001)
                sl = min(sl, exec_price * 0.999)
                cash = capital - trade_capital  # remaining cash not in trade

            elif pred_dir == "做空":
                quantity = (trade_capital - fee_entry) / exec_price
                position = -quantity
                direction = "做空"
                entry_price = exec_price
                entry_time = current_time
                tp = float(pred_tp) if pred_tp is not None else exec_price * 0.98
                sl = float(pred_sl) if pred_sl is not None else exec_price * 1.01
                # Enforce TP < entry < SL for short
                tp = min(tp, exec_price * 0.999)
                sl = max(sl, exec_price * 1.001)
                cash = capital - trade_capital

        # ── Reverse position (close + open opposite) ───────────
        else:
            # Close existing position
            if direction == "做多":
                close_value = abs(position) * exec_price
                gross_pnl = (exec_price - entry_price) / entry_price * (capital * position_size)
            else:  # 做空
                close_value = abs(position) * exec_price
                gross_pnl = (entry_price - exec_price) / entry_price * (capital * position_size)

            fee_close = abs(position) * exec_price * commission
            capital = cash + close_value - fee_close

            pnl_pct = (gross_pnl / (capital * position_size)) * 100 if capital > 0 else 0

            trades.append({
                "entry_time": str(entry_time),
                "exit_time": str(current_time),
                "entry_price": round(entry_price, 6),
                "exit_price": round(exec_price, 6),
                "pnl_pct": round(pnl_pct, 2),
                "direction": direction,
                "exit_reason": "REVERSE",
                "tp": round(tp, 6) if tp else None,
                "sl": round(sl, 6) if sl else None,
            })

            # Open new position in opposite direction
            trade_capital = capital * position_size
            fee_entry = trade_capital * commission

            if pred_dir == "做多":
                quantity = (trade_capital - fee_entry) / exec_price
                position = quantity
                direction = "做多"
            elif pred_dir == "做空":
                quantity = (trade_capital - fee_entry) / exec_price
                position = -quantity
                direction = "做空"
            else:
                position = 0.0
                direction = None
                tp = None
                sl = None
                continue

            entry_price = exec_price
            entry_time = current_time
            tp = float(pred_tp) if pred_tp is not None else (
                exec_price * 1.02 if direction == "做多" else exec_price * 0.98)
            sl = float(pred_sl) if pred_sl is not None else (
                exec_price * 0.99 if direction == "做多" else exec_price * 1.01)

            if direction == "做多":
                tp = max(tp, exec_price * 1.001)
                sl = min(sl, exec_price * 0.999)
            else:
                tp = min(tp, exec_price * 0.999)
                sl = max(sl, exec_price * 1.001)

            cash = capital - trade_capital

    # ── Close any remaining position at last price ──────────
    if position != 0:
        last_price = prices[-1]
        if direction == "做多":
            close_value = abs(position) * last_price
            pnl_pct = (last_price - entry_price) / entry_price * 100
        else:
            close_value = abs(position) * last_price
            pnl_pct = (entry_price - last_price) / entry_price * 100

        fee_close = abs(position) * last_price * commission
        capital = cash + close_value - fee_close

        trades.append({
            "entry_time": str(entry_time),
            "exit_time": str(df.iloc[-1]["timestamp"]),
            "entry_price": round(entry_price, 6),
            "exit_price": round(last_price, 6),
            "pnl_pct": round(pnl_pct, 2),
            "direction": direction,
            "exit_reason": "EOD",
            "tp": round(tp, 6) if tp else None,
            "sl": round(sl, 6) if sl else None,
        })

    final_value = capital if position == 0 else cash + abs(position) * prices[-1]
    return trades, final_value
