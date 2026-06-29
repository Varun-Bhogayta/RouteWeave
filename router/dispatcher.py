"""LLM dispatcher using LiteLLM for multi-provider model calls.

Dispatches requests to the selected model via LiteLLM's async
completion interface and tracks latency and estimated cost.
"""

from __future__ import annotations

import logging
import time

import litellm

from models.schemas import TierConfig

logger = logging.getLogger(__name__)


# ── Exceptions ─────────────────────────────────────────────────


class DispatchError(Exception):
    """Raised when LLM dispatch fails.

    Attributes:
        tier_id: The ID of the tier that was being dispatched to.
        original_error: String representation of the original error.
    """

    def __init__(self, tier_id: str, original_error: str) -> None:
        self.tier_id = tier_id
        self.original_error = original_error
        super().__init__(
            f"Dispatch to tier '{tier_id}' failed: {original_error}"
        )


# ── Core function ──────────────────────────────────────────────


async def dispatch(
    tier: TierConfig,
    messages: list[dict],
    max_tokens: int,
) -> tuple[str, float, float]:
    """Dispatch a request to the selected LLM model via LiteLLM.

    Builds the model string from the tier's provider and model name,
    calls litellm.acompletion, and returns the response text along
    with latency and estimated cost.

    Args:
        tier: The selected tier configuration.
        messages: List of message dicts in OpenAI format
            (e.g. [{"role": "user", "content": "..."}]).
        max_tokens: Maximum tokens for the response.

    Returns:
        A tuple of (response_text, latency_ms, estimated_cost_usd).

    Raises:
        DispatchError: If the LiteLLM call fails for any reason.
    """
    # Step 1 — Build model string
    # ollama provider → "ollama/{model}"
    # all others → "{provider}/{model}"
    model_str = f"{tier.provider}/{tier.model}"

    logger.info(
        "Dispatching to model '%s' (tier: %s, max_tokens: %d)",
        model_str,
        tier.id,
        max_tokens,
    )

    try:
        # Step 2 — Record start time
        start = time.perf_counter()

        # Step 3 — Call LiteLLM
        response = await litellm.acompletion(
            model=model_str,
            messages=messages,
            max_tokens=max_tokens,
        )

        # Step 4 — Calculate latency
        latency_ms = (time.perf_counter() - start) * 1000

        # Step 5 — Extract response text
        response_text = response.choices[0].message.content

        # Step 6 — Estimate cost
        try:
            cost = litellm.completion_cost(completion_response=response)
        except Exception:
            # Some providers don't support cost estimation
            cost = 0.0

        logger.info(
            "Dispatch complete: tier='%s', latency=%.1fms, cost=$%.4f",
            tier.id,
            latency_ms,
            cost,
        )

        # Step 7 — Return results
        return (response_text, latency_ms, cost)

    except Exception as e:
        logger.error(
            "Dispatch failed for tier '%s' (model: %s): %s",
            tier.id,
            model_str,
            str(e),
        )
        raise DispatchError(tier_id=tier.id, original_error=str(e)) from e
