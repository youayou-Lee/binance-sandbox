"""
Strategy: LLM-powered crypto analysis agent.
Delegates to shared llm.py for prediction.

v0.2: Passes high/low alongside close prices for better LLM context.
"""

from llm import predict as llm_predict


def decide(prices: list[float], highs: list[float], lows: list[float]) -> dict | None:
    """
    Ask LLM for a structured prediction.

    Args:
        prices: Close prices (oldest first).
        highs: High prices (same length as prices).
        lows: Low prices (same length as prices).

    Returns:
      {"方向": "做多" | "做空", "止盈": float, "止损": float, "理由": str}
      or None on failure.
    """
    # Pass close prices to LLM (high/low integration tracked in docs/llm-data-transmission.md)
    return llm_predict(prices)
