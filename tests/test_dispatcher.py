"""Tests for router/dispatcher.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.schemas import TierConfig
from router.dispatcher import DispatchError, dispatch


@pytest.fixture
def ollama_tier() -> TierConfig:
    """An Ollama tier for testing."""
    return TierConfig(
        id="local-fast",
        label="Local Fast",
        model="phi3:mini",
        provider="ollama",
        conditions={"complexity": ["low"], "category": ["code"]},
        cost_limit={"max_tokens_per_request": 2000},
    )


@pytest.fixture
def cloud_tier() -> TierConfig:
    """An Anthropic tier for testing."""
    return TierConfig(
        id="premium-cloud",
        label="Premium",
        model="claude-sonnet-4-5",
        provider="anthropic",
        conditions={"complexity": ["high"], "category": ["code"]},
        cost_limit={"max_tokens_per_request": 32000, "max_usd_per_day": 20.0},
    )


def _make_litellm_mock(response_text: str = "Here is the answer", cost: float = 0.001):
    """Create mock for litellm.acompletion."""
    mock_message = MagicMock()
    mock_message.content = response_text

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_fn = AsyncMock(return_value=mock_response)
    return mock_fn, mock_response, cost


@pytest.mark.asyncio
async def test_dispatch_returns_response_text(ollama_tier: TierConfig) -> None:
    """Test that dispatch returns the response text from LiteLLM."""
    mock_fn, _, cost = _make_litellm_mock("Here is the answer")

    with patch("litellm.acompletion", mock_fn), \
         patch("litellm.completion_cost", return_value=cost):
        text, latency, est_cost = await dispatch(
            ollama_tier,
            [{"role": "user", "content": "test"}],
            max_tokens=2000,
        )

    assert text == "Here is the answer"


@pytest.mark.asyncio
async def test_latency_ms_is_positive(ollama_tier: TierConfig) -> None:
    """Test that latency_ms is a positive number."""
    mock_fn, _, cost = _make_litellm_mock()

    with patch("litellm.acompletion", mock_fn), \
         patch("litellm.completion_cost", return_value=cost):
        _, latency, _ = await dispatch(
            ollama_tier,
            [{"role": "user", "content": "test"}],
            max_tokens=2000,
        )

    assert latency > 0.0


@pytest.mark.asyncio
async def test_ollama_model_string_format(ollama_tier: TierConfig) -> None:
    """Test that Ollama models use 'ollama/{model}' format."""
    mock_fn, _, cost = _make_litellm_mock()

    with patch("litellm.acompletion", mock_fn), \
         patch("litellm.completion_cost", return_value=cost):
        await dispatch(
            ollama_tier,
            [{"role": "user", "content": "test"}],
            max_tokens=2000,
        )

    call_args = mock_fn.call_args
    assert call_args.kwargs["model"] == "ollama/phi3:mini"


@pytest.mark.asyncio
async def test_cloud_model_string_format(cloud_tier: TierConfig) -> None:
    """Test that cloud models use '{provider}/{model}' format."""
    mock_fn, _, cost = _make_litellm_mock()

    with patch("litellm.acompletion", mock_fn), \
         patch("litellm.completion_cost", return_value=cost):
        await dispatch(
            cloud_tier,
            [{"role": "user", "content": "test"}],
            max_tokens=32000,
        )

    call_args = mock_fn.call_args
    assert call_args.kwargs["model"] == "anthropic/claude-sonnet-4-5"


@pytest.mark.asyncio
async def test_litellm_exception_raises_dispatch_error(ollama_tier: TierConfig) -> None:
    """Test that a LiteLLM exception raises DispatchError with tier_id."""
    mock_fn = AsyncMock(side_effect=Exception("API connection refused"))

    with patch("litellm.acompletion", mock_fn):
        with pytest.raises(DispatchError) as exc_info:
            await dispatch(
                ollama_tier,
                [{"role": "user", "content": "test"}],
                max_tokens=2000,
            )

    assert exc_info.value.tier_id == "local-fast"
    assert "API connection refused" in exc_info.value.original_error
