"""Tests for router/classifier.py."""

from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from models.schemas import PromptRequest
from router.classifier import ClassifierError, classify_prompt


@pytest.fixture
def valid_classifier_data() -> dict:
    """Valid classifier output data."""
    return {
        "task_category": "code",
        "complexity": "low",
        "subtask": "bug_fix",
        "estimated_tokens": 350,
        "confidence": 0.94,
    }


def _make_llama_cpp_mock(data: dict):
    """Create a mock httpx client that returns the given data as llama.cpp response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    
    response_data = {
        "choices": [{"message": {"content": json.dumps(data)}}]
    }
    mock_response.json.return_value = response_data
    mock_response.raise_for_status = MagicMock()
    mock_response.text = json.dumps(response_data)

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


@pytest.mark.asyncio
async def test_valid_response_parses_correctly(valid_classifier_data: dict) -> None:
    """Test that a valid llama.cpp response parses into ClassifierOutput correctly."""
    mock_client = _make_llama_cpp_mock(valid_classifier_data)

    with patch("httpx.AsyncClient", return_value=mock_client):
        request = PromptRequest(prompt="Fix the off-by-one error in my binary search")
        result = await classify_prompt(request)

    assert result.task_category == "code"
    assert result.complexity == "low"
    assert result.subtask == "bug_fix"
    assert result.estimated_tokens == 350
    assert result.confidence == 0.94


@pytest.mark.asyncio
async def test_invalid_json_raises_classifier_error() -> None:
    """Test that invalid JSON from llama.cpp raises ClassifierError with raw output."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    
    response_data = {
        "choices": [{"message": {"content": "sorry I can't classify this"}}]
    }
    mock_response.json.return_value = response_data
    mock_response.raise_for_status = MagicMock()
    mock_response.text = json.dumps(response_data)

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        request = PromptRequest(prompt="test prompt")
        with pytest.raises(ClassifierError) as exc_info:
            await classify_prompt(request)

    assert "sorry I can't classify" in exc_info.value.raw_output


@pytest.mark.asyncio
async def test_low_confidence_logs_warning(
    valid_classifier_data: dict, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that low confidence (< 0.6) logs a warning but still returns result."""
    valid_classifier_data["confidence"] = 0.5
    mock_client = _make_llama_cpp_mock(valid_classifier_data)

    with patch("httpx.AsyncClient", return_value=mock_client):
        request = PromptRequest(prompt="some ambiguous prompt")
        with caplog.at_level(logging.WARNING):
            result = await classify_prompt(request)

    assert result.confidence == 0.5
    assert "Low classifier confidence" in caplog.text


@pytest.mark.asyncio
async def test_conversation_history_included_in_prompt(valid_classifier_data: dict) -> None:
    """Test that only the last 3 turns of conversation history are included."""
    mock_client = _make_llama_cpp_mock(valid_classifier_data)
    captured_body = {}

    async def capture_post(url, json=None, **kwargs):
        captured_body.update(json or {})
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        
        response_data = {
            "choices": [{"message": {"content": json_module.dumps(valid_classifier_data)}}]
        }
        mock_resp.json.return_value = response_data
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    import json as json_module

    mock_client.post = capture_post

    with patch("httpx.AsyncClient", return_value=mock_client):
        request = PromptRequest(
            prompt="current prompt",
            conversation_history=[
                {"role": "user", "content": "turn 1"},
                {"role": "assistant", "content": "turn 2"},
                {"role": "user", "content": "turn 3"},
                {"role": "assistant", "content": "turn 4"},
                {"role": "user", "content": "turn 5"},
            ],
        )
        await classify_prompt(request)

    # Only last 3 turns + system prompt + user prompt should be in the messages
    messages = captured_body.get("messages", [])
    content = str(messages)
    assert "turn 3" in content
    assert "turn 4" in content
    assert "turn 5" in content
    assert "turn 1" not in content


@pytest.mark.asyncio
async def test_timeout_raises_classifier_error() -> None:
    """Test that a timeout raises ClassifierError."""
    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.TimeoutException("Connection timed out")
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        request = PromptRequest(prompt="test prompt")
        with pytest.raises(ClassifierError, match="timed out"):
            await classify_prompt(request)
