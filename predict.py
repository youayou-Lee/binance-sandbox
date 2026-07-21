"""
预测能力测试 v2：多币种 + 随机采样。

用法:
    uv run python predict.py --count 500 --threads 10
"""

import argparse
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from harness.data import fetch_klines
from harness.strategy import decide

# Top coins by volume (USDT pairs)
TOP_COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "BNBUSDT",
             "XRPUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT"]


def prepare_data(symbols: list[str], limit: int = 2000):
    """Download and cache data for all symbols."""
    datasets = {}
    for sym in symbols:
        df = fetch_klines(sym, "1h", limit)
        datasets[sym] = {
            "prices": df["close"].tolist(),
            "highs": df["high"].tolist(),
            "lows": df["low"].tolist(),
            "times": df["timestamp"].tolist(),
        }
    return datasets


def generate_test_points(
    datasets: dict, count: int, min_bars: int = 150, lookahead: int = 12
) -> list[tuple]:
    """Generate random test points across all coins."""
    all_points = []

    for sym, data in datasets.items():
        prices = data["prices"]
        max_start = len(prices) - min_bars - lookahead
        for t in range(min_bars, max_start):
            all_points.append((sym, t))

    random.shuffle(all_points)
    return all_points[:count]


def evaluate_one(args: tuple) -> dict | None:
    """Evaluate a single prediction point."""
    sym, t_idx, datasets, lookahead = args
    data = datasets[sym]

    slice_p = data["prices"][:t_idx]
    slice_h = data["highs"][:t_idx]
    slice_l = data["lows"][:t_idx]

    pred = decide(slice_p, slice_h, slice_l)
    if pred is None:
        return None

    entry = data["prices"][t_idx]
    direction = pred["方向"]
    tp = float(pred["止盈"])
    sl = float(pred["止损"])
    if direction == "做多":
        tp = max(tp, entry * 1.001)
        sl = min(sl, entry * 0.999)
    else:
        tp = min(tp, entry * 0.999)
        sl = max(sl, entry * 1.001)

    future_h = max(data["highs"][t_idx : t_idx + lookahead])
    future_l = min(data["lows"][t_idx : t_idx + lookahead])

    if direction == "做多":
        tp_hit = future_h >= tp
        sl_hit = future_l <= sl
    else:
        tp_hit = future_l <= tp
        sl_hit = future_h >= sl

    if tp_hit and not sl_hit:
        result = "✅ 正确"
    elif sl_hit and not tp_hit:
        result = "❌ 错误"
    elif tp_hit and sl_hit:
        if direction == "做多":
            result = "✅ 正确" if abs(future_h - tp) < abs(future_l - sl) else "❌ 错误"
        else:
            result = "✅ 正确" if abs(future_l - tp) < abs(future_h - sl) else "❌ 错误"
    else:
        result = "⏸️ 未触及"

    return {
        "symbol": sym,
        "direction": direction,
        "entry": round(entry, 2),
        "tp": round(tp, 2),
        "sl": round(sl, 2),
        "future_high": round(future_h, 2),
        "future_low": round(future_l, 2),
        "result": result,
    }


def run_test(count: int, symbols: list[str], threads: int):
    limit = max(2000, 150 + 12 + count * 2)  # ensure enough data
    print(f"  下载数据中 ({len(symbols)} 个币种, {limit} 根 K 线)...")
    datasets = prepare_data(symbols, limit)

    points = generate_test_points(datasets, count)
    print(f"  共 {len(points)} 个测试点, {threads} 路并发")

    results = []
    done = 0

    if threads > 1:
        with ThreadPoolExecutor(max_workers=threads) as ex:
            futures = {
                ex.submit(evaluate_one, (sym, t, datasets, 12)): (sym, t)
                for sym, t in points
            }
            for f in as_completed(futures):
                r = f.result()
                if r:
                    results.append(r)
                done += 1
                if done % 50 == 0:
                    print(f"  [{done}/{len(points)}] 完成...")
    else:
        for sym, t in points:
            r = evaluate_one((sym, t, datasets, 12))
            if r:
                results.append(r)
            done += 1
            if done % 50 == 0:
                print(f"  [{done}/{len(points)}] 完成...")

    return results


def report(results: list[dict], total_points: int):
    total = len(results)
    if total == 0:
        print("\n没有有效预测！")
        return

    correct = sum(1 for r in results if r["result"].startswith("✅"))
    wrong = sum(1 for r in results if r["result"].startswith("❌"))
    expired = sum(1 for r in results if r["result"].startswith("⏸️"))

    # Contrarian accuracy
    cont_correct = wrong
    cont_total = correct + wrong
    cont_acc = cont_correct / cont_total * 100 if cont_total > 0 else 0

    print()
    print("=" * 55)
    print("          预测能力测试报告 v2")
    print("=" * 55)
    print(f"  测试点总数: {total_points}")
    print(f"  有效预测:   {total}  ({total/total_points*100:.0f}%)")
    print(f"  正确:       {correct}  ({correct/total*100:.1f}%)")
    print(f"  错误:       {wrong}  ({wrong/total*100:.1f}%)")
    print(f"  未触及:     {expired}  ({expired/total*100:.1f}%)")
    print(f"  准确率:     {correct/cont_total*100:.1f}% (排除未触及)")
    print(f"  反指准确率: {cont_acc:.1f}% (反着做)")
    print("=" * 55)

    # Per-coin breakdown
    coins = set(r["symbol"] for r in results)
    print(f"\n  {'币种':>10}  {'次数':>4}  {'正确':>4}  {'错误':>4}  {'未触及':>4}  {'准确率':>6}  {'反指':>6}")
    print(f"  {'-'*52}")
    for coin in sorted(coins):
        cr = [r for r in results if r["symbol"] == coin]
        n = len(cr)
        c = sum(1 for r in cr if r["result"].startswith("✅"))
        w = sum(1 for r in cr if r["result"].startswith("❌"))
        e = sum(1 for r in cr if r["result"].startswith("⏸️"))
        acc = c / (c + w) * 100 if (c + w) > 0 else 0
        cont = w / (c + w) * 100 if (c + w) > 0 else 0
        print(f"  {coin:>10}  {n:>4}  {c:>4}  {w:>4}  {e:>4}  {acc:>5.1f}%  {cont:>5.1f}%")

    # Segments
    seg_count = 5
    seg_size = max(1, total // seg_count)
    print(f"\n  {'分段':->46}")
    print(f"  {'段':>4}  {'次数':>4}  {'正确':>4}  {'错误':>4}  {'未触及':>4}  {'准确率':>6}  {'反指':>6}")
    print(f"  {'-'*46}")
    for seg in range(seg_count):
        start = seg * seg_size
        end = min(start + seg_size, total)
        seg_data = results[start:end]
        sc = sum(1 for r in seg_data if r["result"].startswith("✅"))
        sw = sum(1 for r in seg_data if r["result"].startswith("❌"))
        se = sum(1 for r in seg_data if r["result"].startswith("⏸️"))
        s_acc = sc / (sc + sw) * 100 if (sc + sw) > 0 else 0
        s_cont = sw / (sc + sw) * 100 if (sc + sw) > 0 else 0
        print(f"  {seg+1:>4}  {len(seg_data):>4}  {sc:>4}  {sw:>4}  {se:>4}  {s_acc:>5.1f}%  {s_cont:>5.1f}%")

    # Direction breakdown
    shorts = [r for r in results if r["direction"] == "做空"]
    longs = [r for r in results if r["direction"] == "做多"]
    print(f"\n  做空预测: {len(shorts)}/{total} ({len(shorts)/total*100:.0f}%)"
          f"  正确率: {sum(1 for r in shorts if r['result'].startswith('✅'))/(len(shorts) or 1)*100:.0f}%")
    print(f"  做多预测: {len(longs)}/{total} ({len(longs)/total*100:.0f}%)"
          f"  正确率: {sum(1 for r in longs if r['result'].startswith('✅'))/(len(longs) or 1)*100:.0f}%")


def main():
    parser = argparse.ArgumentParser(description="LLM 预测能力测试 v2")
    parser.add_argument("--count", type=int, default=500, help="测试次数")
    parser.add_argument("--threads", type=int, default=10, help="并发")
    parser.add_argument("--coins", nargs="+", default=TOP_COINS[:3], help="币种列表")
    args = parser.parse_args()

    print(f"  测试次数: {args.count}")
    print(f"  并发:     {args.threads}")
    print(f"  币种:     {', '.join(args.coins)}")
    print("  " + "-" * 40)

    t0 = time.time()
    results = run_test(args.count, args.coins, args.threads)
    elapsed = time.time() - t0

    import json
    with open("predict-results.json", "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  ✓ 结果已保存 ({len(results)} 条, {elapsed:.0f}s)")
    report(results, args.count)


if __name__ == "__main__":
    main()
