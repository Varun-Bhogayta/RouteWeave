"""Shared test fixtures for RouteWeave tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.schemas import TierConfig


@pytest.fixture
def sample_tiers() -> list[TierConfig]:
    """Create a list of 3 valid sample tiers for testing."""
    return [
        TierConfig(
            id="local-fast",
            label="Local Fast",
            model="phi3:mini",
            provider="ollama",
            conditions={"complexity": ["low"], "category": ["code", "general"]},
            cost_limit={"max_tokens_per_request": 2000},
        ),
        TierConfig(
            id="mid-cloud",
            label="Mid Cloud",
            model="gemini-1.5-flash",
            provider="google",
            conditions={
                "complexity": ["medium"],
                "category": ["code", "data", "reasoning", "general"],
            },
            cost_limit={"max_tokens_per_request": 8000, "max_usd_per_day": 5.0},
        ),
        TierConfig(
            id="premium-cloud",
            label="Premium",
            model="claude-sonnet-4-5",
            provider="anthropic",
            conditions={
                "complexity": ["high"],
                "category": ["code", "reasoning", "data", "general"],
            },
            cost_limit={"max_tokens_per_request": 32000, "max_usd_per_day": 20.0},
        ),
    ]


@pytest.fixture
def mock_llama_cpp_response():
    """Fixture factory that patches httpx.AsyncClient.post with mock llama.cpp responses.

    Usage:
        def test_something(mock_llama_cpp_response):
            mock_llama_cpp_response({"task_category": "code", ...})
    """
    def _factory(data: dict):
        import json

        mock_response = MagicMock()
        mock_response.status_code = 200
        # Mock OpenAI-compatible response format
        response_data = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(data)
                    }
                }
            ]
        }
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()
        mock_response.text = json.dumps(response_data)

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        patcher = patch("httpx.AsyncClient", return_value=mock_client)
        patcher.start()

        return mock_client, patcher

    yield _factory


@pytest.fixture
def mock_litellm():
    """Fixture factory that patches litellm.acompletion with mock responses.

    Usage:
        def test_something(mock_litellm):
            mock_litellm("Here is the answer")
    """
    def _factory(response_text: str = "Mock response", cost: float = 0.001):
        mock_message = MagicMock()
        mock_message.content = response_text

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_acompletion = AsyncMock(return_value=mock_response)

        patcher_completion = patch("litellm.acompletion", mock_acompletion)
        patcher_cost = patch("litellm.completion_cost", return_value=cost)

        patcher_completion.start()
        patcher_cost.start()

        return mock_acompletion, mock_response, patcher_completion, patcher_cost

    yield _factory
