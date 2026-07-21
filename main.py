"""
Binance Sandbox — 连接 Binance 模拟沙盘 API 的入口脚本。

用法：
    python main.py              # 执行完整连接测试
    python main.py --ping       # 仅测试网络连通性
    python main.py --balances   # 查看账户余额
    python main.py --prices     # 查看当前行情
"""

import argparse
import logging
import sys

from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException

from config import BINANCE_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def get_client() -> Client:
    """初始化并返回 Binance Testnet 客户端。"""
    cfg = BINANCE_CONFIG
    if not cfg["api_key"] or not cfg["api_secret"]:
        log.error("API Key 或 Secret 未配置！请复制 .env.example 为 .env 并填入你的 Testnet API Key。")
        log.error("注册地址：https://testnet.binance.vision/")
        sys.exit(1)

    client = Client(
        api_key=cfg["api_key"],
        api_secret=cfg["api_secret"],
        testnet=cfg["testnet"],
        requests_params={"timeout": cfg["timeout"]},
    )
    return client


def ping() -> dict:
    """测试与 Binance Testnet 的网络连通性。"""
    log.info("测试 Binance Testnet 连通性...")
    client = get_client()
    result = client.ping()
    log.info("✓ 连通正常！返回: %s", result)
    return result


def get_server_time() -> dict:
    """获取 Binance Testnet 服务器时间。"""
    client = get_client()
    info = client.get_server_time()
    log.info("✓ 服务器时间: %s (UTC+8: %s)", info["serverTime"], _to_beijing(info["serverTime"]))
    return info


def get_account_balances():
    """查询 Testnet 账户余额。"""
    log.info("查询账户余额...")
    client = get_client()
    info = client.get_account()
    balances = [b for b in info["balances"] if float(b["free"]) > 0 or float(b["locked"]) > 0]
    if not balances:
        log.info("账户余额为空（所有资产为 0）")
    else:
        log.info("账户余额:")
        for b in balances:
            log.info("  %s: 可用=%s  锁定=%s", b["asset"], b["free"], b["locked"])
    return balances


def get_prices(symbol: str = None):
    """获取当前行情价格。"""
    client = get_client()
    if symbol:
        ticker = client.get_symbol_ticker(symbol=symbol)
        log.info("  %s: %s", ticker["symbol"], ticker["price"])
        return [ticker]
    else:
        tickers = client.get_symbol_ticker()
        log.info("共获取 %d 个交易对价格", len(tickers))
        # 只显示 USDT 交易对，方便阅读
        usdt_pairs = [t for t in tickers if t["symbol"].endswith("USDT")]
        for t in usdt_pairs[:20]:  # 前 20 个
            log.info("  %s: %s", t["symbol"], t["price"])
        log.info("...（共 %d 个 USDT 交易对，仅显示前 20）", len(usdt_pairs))
        return tickers


def full_connection_test():
    """完整连接测试：ping → 服务器时间 → 余额 → 行情摘要。"""
    log.info("=" * 50)
    log.info("Binance Testnet — 完整连接测试")
    log.info("=" * 50)

    try:
        ping()
        get_server_time()
        get_account_balances()
        get_prices("BTCUSDT")
        log.info("")
        log.info("✓ 全部测试通过！Binance Testnet 连接正常。")
        log.info("  下一步方向：订单接口测试、WebSocket 行情订阅、策略回测")

    except BinanceAPIException as e:
        log.error("Binance API 错误: %s", e)
        sys.exit(1)
    except BinanceRequestException as e:
        log.error("网络请求错误: %s", e)
        sys.exit(1)
    except Exception as e:
        log.error("未知错误: %s", e)
        sys.exit(1)


def _to_beijing(ts_ms: int) -> str:
    """将毫秒时间戳转为北京时间字符串。"""
    from datetime import datetime, timezone, timedelta

    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc) + timedelta(hours=8)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def main():
    parser = argparse.ArgumentParser(description="Binance Testnet 沙盘客户端")
    parser.add_argument("--ping", action="store_true", help="仅测试网络连通性")
    parser.add_argument("--balances", action="store_true", help="查看账户余额")
    parser.add_argument("--prices", type=str, nargs="?", const="BTCUSDT", help="查看行情（默认 BTCUSDT，不传参显示全部）")
    parser.add_argument("--time", action="store_true", help="获取服务器时间")
    args = parser.parse_args()

    if args.ping:
        ping()
    elif args.balances:
        get_account_balances()
    elif args.prices:
        get_prices(args.prices if args.prices != "BTCUSDT" else None)
    elif args.time:
        get_server_time()
    else:
        full_connection_test()


if __name__ == "__main__":
    main()
