"""
Strategy: LLM-powered crypto analysis agent.
Delegates to shared llm.py for prediction.
"""

from llm import predict as llm_predict


def decide(prices: list[float], highs: list[float], lows: list[float]) -> dict | None:
    """
    Ask LLM for a structured prediction.

    Returns:
      {"方向": "做多" | "做空", "止盈": float, "止损": float, "理由": str}
      or None on failure.
    """
    return llm_predict(prices)
