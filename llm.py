"""
Shared LLM module: DeepSeek-powered crypto directional prediction.

Used by both sandbox_trader.py and harness/strategy.py.
"""

import json
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")


def predict(prices: list[float], lookback: int = 100) -> dict | None:
    """
    Call DeepSeek for directional prediction.

    Args:
        prices: List of closing prices (oldest first).
        lookback: Number of most recent bars to feed (default 100).

    Returns:
        {"方向": "做多"|"做空", "止盈": float, "止损": float, "理由": str}
        or None on failure.
    """
    if len(prices) < lookback:
        return None

    recent = prices[-lookback:][::-1]  # newest first
    current = recent[0]
    low, high = min(recent), max(recent)

    prompt = (
        "You are a crypto analyst. Predict the next 12 hours.\n\n"
        f"Recent {lookback} closing prices (newest->oldest):\n{recent}\n"
        f"Range: {low:.0f} - {high:.0f}\n"
        f"Current: {current:.0f}\n\n"
        "Respond ONLY with valid JSON.\n"
        "For 做多: 止盈 > 当前价 > 止损.\n"
        "For 做空: 止盈 < 当前价 < 止损.\n"
        '{"方向": "做多" or "做空", "止盈": <number>, "止损": <number>, "理由": "<reason>"}'
    )

    return _call_deepseek(prompt)


def _call_deepseek(prompt: str, max_tokens: int = 300, temperature: float = 0.5) -> dict | None:
    """Send prompt to DeepSeek and parse JSON response. Retries once."""
    for attempt in range(2):
        try:
            client = OpenAI(
                api_key=API_KEY,
                base_url="https://api.deepseek.com/v1",
                timeout=10.0,
            )
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = (resp.choices[0].message.content or "").strip()
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(content[start:end])
                if "方向" in data and "止盈" in data and "止损" in data:
                    data["止盈"] = float(data["止盈"])
                    data["止损"] = float(data["止损"])
                    return data
        except Exception:
            time.sleep(0.5)

    return None
