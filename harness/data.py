"""
Fetch historical K-line data from Binance public API.
"""

from pathlib import Path

import pandas as pd
from binance.client import Client

CACHE_DIR = Path(__file__).parent.parent / "data"
CACHE_DIR.mkdir(exist_ok=True)

PROXIES = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}


def fetch_klines(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    limit: int = 720,
    force: bool = False,
) -> pd.DataFrame:
    cache_path = CACHE_DIR / f"{symbol}-{interval}-{limit}.parquet"

    if cache_path.exists() and not force:
        return pd.read_parquet(cache_path)

    client = Client("", "", ping=False)
    client.session.proxies.update(PROXIES)

    # Binance API max is 1000 per call
    batch_size = 1000
    if limit <= batch_size:
        raw = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    else:
        # Fetch in batches, newest first
        all_raw = []
        remaining = limit
        end_time = None  # latest timestamp
        while remaining > 0:
            take = min(remaining, batch_size)
            params = {"symbol": symbol, "interval": interval, "limit": take}
            if end_time:
                params["endTime"] = end_time
            batch = client.get_klines(**params)
            if not batch:
                break
            all_raw = batch + all_raw  # prepend (older data first)
            end_time = int(batch[0][0])  # oldest timestamp in this batch
            remaining -= take
        raw = all_raw

    df = pd.DataFrame(
        raw,
        columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_vol", "trades", "taker_buy_vol",
            "taker_buy_quote", "ignore",
        ],
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    df = df[["timestamp", "open", "high", "low", "close", "volume"]]
    df.to_parquet(cache_path)
    print(f"  ✓ 已缓存到 {cache_path}")
    return df


if __name__ == "__main__":
    df = fetch_klines("BTCUSDT", "1h", 1000)
    print(f"共 {len(df)} 根 K 线")
