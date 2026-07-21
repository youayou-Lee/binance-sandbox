"""Configuration for Binance Sandbox trading client."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


# Binance Spot Testnet configuration
BINANCE_CONFIG = {
    "api_key": os.getenv("BINANCE_TESTNET_API_KEY", ""),
    "api_secret": os.getenv("BINANCE_TESTNET_API_SECRET", ""),
    "testnet": True,
    # Spot Testnet REST endpoint
    "rest_url": "https://testnet.binance.vision",
    # Spot Testnet WebSocket endpoint
    "ws_url": "wss://testnet.binance.vision/ws",
    # Request timeout (seconds)
    "timeout": 30,
}

# Project paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
