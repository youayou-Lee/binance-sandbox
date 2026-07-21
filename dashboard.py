"""
Dashboard: monitor trading bot status, positions, logs.
"""

import json
import os
import subprocess
from pathlib import Path
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template_string
from binance.client import Client

app = Flask(__name__)

STATE_FILE = Path(__file__).parent / "trader_state.json"
LOG_FILE = Path(__file__).parent / "trader.log"

# Binance client for live prices
pub = Client("", "", ping=False)
pub.session.proxies.update({"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"})


def load_state() -> dict:
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return {"capital": 10000, "positions": {}, "trades": [], "cycle": 0}


def get_live_prices(symbols: list[str]) -> dict:
    """Fetch current prices + 24h change (concurrent)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    result = {}
    def fetch(sym):
        try:
            t = pub.get_ticker(symbol=sym)
            return sym, {
                "price": float(t["lastPrice"]),
                "change_24h": float(t["priceChangePercent"]),
                "high_24h": float(t["highPrice"]),
                "low_24h": float(t["lowPrice"]),
                "volume": float(t["quoteVolume"]),
            }
        except:
            return sym, None
    with ThreadPoolExecutor(max_workers=10) as ex:
        fut = {ex.submit(fetch, s): s for s in symbols}
        for f in as_completed(fut):
            sym, data = f.result()
            if data:
                result[sym] = data
    return result


def get_logs(lines: int = 50) -> list[str]:
    """Get recent log lines."""
    try:
        with open(LOG_FILE) as f:
            all_lines = f.readlines()
        return all_lines[-lines:]
    except:
        return []


@app.route("/")
def index():
    return render_template_string(HTML)


REMOTE_API = os.environ.get("REMOTE_API", "")

def fetch_remote(path):
    import requests
    try:
        r = requests.get(REMOTE_API + path, timeout=5)
        return r.json()
    except:
        return None

@app.route("/api/status")
def api_status():
    if REMOTE_API:
        return jsonify(fetch_remote("/api/status") or {"error": "无法连接"})

    state = load_state()
    positions = [p for p in state["positions"].values() if p["status"] == "open"]
    symbols = [p["coin"] for p in positions]
    prices = get_live_prices(symbols)

    # Enrich positions with live data
    enriched = []
    for p in positions:
        coin = p["coin"]
        info = prices.get(coin, {})
        current = info.get("price", p["entry_price"])
        direction = p["direction"]
        if direction == "做多":
            unrealized_pnl = (current - p["entry_price"]) / p["entry_price"] * 100
        else:
            unrealized_pnl = (p["entry_price"] - current) / p["entry_price"] * 100

        enriched.append({
            **p,
            "current_price": round(current, 6),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "change_24h": info.get("change_24h", 0),
            "volume_24h": info.get("volume", 0),
        })

    total_unrealized = sum(p["unrealized_pnl"] * (state["capital"] / len(positions) if positions else 0) / 100
                          for p in enriched) if enriched else 0

    return jsonify({
        "capital": round(state["capital"], 2),
        "initial": 10000,
        "total_pnl": round((state["capital"] - 10000) / 10000 * 100, 2),
        "cycle": state["cycle"],
        "open_positions": len(enriched),
        "total_positions": len(state["positions"]),
        "positions": enriched,
        "total_unrealized": round(total_unrealized, 2),
    })


@app.route("/api/logs")
def api_logs():
    if REMOTE_API:
        return jsonify(fetch_remote("/api/logs") or {"logs": []})
    return jsonify({"logs": get_logs(100)})


@app.route("/api/trades")
def api_trades():
    if REMOTE_API:
        return jsonify(fetch_remote("/api/trades") or {"trades": []})
    state = load_state()
    closed = [t for t in state.get("trades", []) if t.get("status") == "closed"]
    return jsonify({"trades": closed[-50:]})


# ─── HTML Template ─────────────────────────────────

HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>交易监控面板</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, 'Segoe UI', sans-serif; background: #0f0f1a; color: #e0e0e0; padding: 20px; }
h1 { font-size: 20px; margin-bottom: 16px; color: #8888cc; }
.card { background: #1a1a2e; border-radius: 10px; padding: 16px; margin-bottom: 12px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }
.stat { text-align: center; }
.stat .label { font-size: 12px; color: #888; }
.stat .value { font-size: 22px; font-weight: 700; margin-top: 4px; }
.stat .value.green { color: #00c853; }
.stat .value.red { color: #ff1744; }
.stat .value.yellow { color: #ffd600; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; color: #888; padding: 8px 6px; border-bottom: 1px solid #2a2a3e; font-weight: 500; }
td { padding: 8px 6px; border-bottom: 1px solid #222; }
.positive { color: #00c853; }
.negative { color: #ff1744; }
.logs { font-family: 'Courier New', monospace; font-size: 12px; line-height: 1.5; max-height: 300px; overflow-y: auto; }
.logs div { padding: 2px 0; }
.tab-bar { display: flex; gap: 8px; margin-bottom: 12px; }
.tab { padding: 8px 16px; border-radius: 6px; cursor: pointer; background: #1a1a2e; color: #888; }
.tab.active { background: #2a2a5e; color: #fff; }
.refresh { float: right; font-size: 12px; color: #666; cursor: pointer; }
.refresh:hover { color: #aaa; }
</style>
</head>
<body>
<h1>📊 交易监控面板 <span class="refresh" onclick="location.reload()">⟳ 刷新</span></h1>

<div class="card">
  <div class="grid" id="summary">
    <div class="stat"><div class="label">资金</div><div class="value" id="capital">-</div></div>
    <div class="stat"><div class="label">总盈亏</div><div class="value" id="totalPnl">-</div></div>
    <div class="stat"><div class="label">未实现盈亏</div><div class="value" id="unrealizedPnl">-</div></div>
    <div class="stat"><div class="label">持仓</div><div class="value" id="positions">-</div></div>
    <div class="stat"><div class="label">轮次</div><div class="value" id="cycle">-</div></div>
    <div class="stat"><div class="label">运行时间</div><div class="value" id="uptime">-</div></div>
  </div>
</div>

<div class="tab-bar">
  <div class="tab active" onclick="switchTab('positions')">持仓明细</div>
  <div class="tab" onclick="switchTab('trades')">交易记录</div>
  <div class="tab" onclick="switchTab('logs')">实时日志</div>
</div>

<div id="positions-tab">
  <div class="card"><div id="loading" style="text-align:center;padding:30px;color:#666">加载中...</div><div id="positionsTable"></div></div>
</div>
<div id="trades-tab" style="display:none">
  <div class="card" id="tradesList"></div>
</div>
<div id="logs-tab" style="display:none">
  <div class="card"><div class="logs" id="logsContent"></div></div>
</div>

<script>
let startTime = Date.now();

function update() {
  fetch('/api/status').then(r=>r.json()).then(d => {
    document.getElementById('capital').textContent = '$' + d.capital.toLocaleString();
    document.getElementById('capital').className = 'value' + (d.total_pnl >= 0 ? ' green' : ' red');

    document.getElementById('totalPnl').textContent = (d.total_pnl >= 0 ? '+' : '') + d.total_pnl.toFixed(2) + '%';
    document.getElementById('totalPnl').className = 'value' + (d.total_pnl >= 0 ? ' green' : ' red');

    document.getElementById('unrealizedPnl').textContent = (d.total_unrealized >= 0 ? '+' : '') + d.total_unrealized.toFixed(2);
    document.getElementById('unrealizedPnl').className = 'value' + (d.total_unrealized >= 0 ? ' green' : ' red');

    document.getElementById('positions').textContent = d.open_positions + '/' + d.total_positions;
    document.getElementById('cycle').textContent = d.cycle;
    document.getElementById('uptime').textContent = Math.floor((Date.now()-startTime)/60000) + 'm';

    // Table
    let table = '<table><tr><th>币种</th><th>方向</th><th>入场价</th><th>现价</th><th>TP</th><th>SL</th><th>浮动盈亏</th><th>24h涨跌</th></tr>';
    for (const p of d.positions) {
      const pnlClass = p.unrealized_pnl >= 0 ? 'positive' : 'negative';
      const chgClass = p.change_24h >= 0 ? 'positive' : 'negative';
      table += '<tr><td>' + p.coin + '</td><td>' + p.direction + '</td>'
        + '<td>' + p.entry_price.toFixed(p.entry_price < 1 ? 4 : 2) + '</td>'
        + '<td>' + p.current_price.toFixed(p.current_price < 1 ? 4 : 2) + '</td>'
        + '<td>' + p.tp.toFixed(p.tp < 1 ? 4 : 2) + '</td>'
        + '<td>' + p.sl.toFixed(p.sl < 1 ? 4 : 2) + '</td>'
        + '<td class="' + pnlClass + '">' + (p.unrealized_pnl >= 0 ? '+' : '') + p.unrealized_pnl.toFixed(2) + '%</td>'
        + '<td class="' + chgClass + '">' + (p.change_24h >= 0 ? '+' : '') + p.change_24h.toFixed(1) + '%</td></tr>';
    }
    if (d.positions.length === 0) table += '<tr><td colspan="8" style="text-align:center;color:#666;padding:20px">无持仓</td></tr>';
    table += '</table>';
    document.getElementById('positionsTable').innerHTML = table;
  });
}

function loadTrades() {
  fetch('/api/trades').then(r=>r.json()).then(d => {
    let html = '<table><tr><th>币种</th><th>方向</th><th>入场价</th><th>出场价</th><th>盈亏</th><th>原因</th><th>时间</th></tr>';
    for (const t of d.trades) {
      const cls = (t.pnl_pct || 0) >= 0 ? 'positive' : 'negative';
      html += '<tr><td>' + t.coin + '</td><td>' + t.direction + '</td>'
        + '<td>' + (t.entry_price || 0).toFixed(2) + '</td>'
        + '<td>' + (t.exit_price || 0).toFixed(2) + '</td>'
        + '<td class="' + cls + '">' + (t.pnl_pct >= 0 ? '+' : '') + (t.pnl_pct || 0).toFixed(2) + '%</td>'
        + '<td>' + (t.exit_reason || '-') + '</td>'
        + '<td>' + (t.entry_time || '-') + '</td></tr>';
    }
    if (d.trades.length === 0) html += '<tr><td colspan="7" style="text-align:center;color:#666;padding:20px">暂无交易记录</td></tr>';
    html += '</table>';
    document.getElementById('tradesList').innerHTML = html;
  });
}

function loadLogs() {
  fetch('/api/logs').then(r=>r.json()).then(d => {
    document.getElementById('logsContent').innerHTML = d.logs.map(l => '<div>' + l.replace(/</g,'&lt;') + '</div>').join('');
    document.getElementById('logsContent').scrollTop = document.getElementById('logsContent').scrollHeight;
  });
}

function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
  document.querySelectorAll('[id$="-tab"]').forEach(t => t.style.display = 'none');
  document.getElementById(name + '-tab').style.display = 'block';
  if (name === 'trades') loadTrades();
  if (name === 'logs') loadLogs();
}

// Update every 5 seconds
update();
setTimeout(function() { document.getElementById('loading').style.display='none'; }, 30000);
setInterval(update, 5000);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 13212))
    print(f"Dashboard: http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
