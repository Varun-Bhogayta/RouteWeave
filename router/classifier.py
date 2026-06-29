"""Prompt classifier using a local Ollama model.

Analyzes user prompts and returns structured classification output
(task category, complexity, subtask, estimated tokens, confidence).
"""

from __future__ import annotations

import logging
import os

import httpx

from models.schemas import ClassifierOutput, PromptRequest

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────

CLASSIFIER_MODEL: str = os.getenv("CLASSIFIER_MODEL", "phi3:mini")
LLAMA_CPP_URL: str = os.getenv("LLAMA_CPP_URL", "http://localhost:8080")
CLASSIFIER_TIMEOUT_SEC: int = 15

# ── System prompt ──────────────────────────────────────────────

SYSTEM_PROMPT: str = """You are a prompt classifier for an intelligent AI routing system.
Analyze the user prompt and return ONLY a valid JSON object. No explanation. No markdown.

Output schema:
{
  "task_category": one of ["code", "reasoning", "data", "general"],
  "complexity": one of ["low", "medium", "high"],
  "subtask": short string (e.g. "syntax_fix", "architecture_design", "sql_query"),
  "estimated_tokens": integer — estimated tokens for a complete response,
  "confidence": float between 0.0 and 1.0
}

Complexity rules:
  low    → syntax fix, one-liner, factual lookup, format conversion
  medium → moderate codegen, summarization, structured analysis, explanation
  high   → system design, multi-step reasoning, architecture, complex debugging

Category rules:
  code      → writing, fixing, reviewing, or explaining code
  reasoning → logic, math, planning, decision-making, analysis
  data      → SQL, data transformation, CSV/JSON processing, schemas
  general   → everything else

Return ONLY the JSON object.
"""


# ── Exceptions ─────────────────────────────────────────────────


class ClassifierError(Exception):
    """Raised when prompt classification fails.

    Attributes:
        raw_output: The raw response from the classifier model, if available.
    """

    def __init__(self, message: str, raw_output: str = "") -> None:
        self.raw_output = raw_output
        super().__init__(message)


# ── Core function ──────────────────────────────────────────────


async def classify_prompt(request: PromptRequest) -> ClassifierOutput:
    """Classify a user prompt using a local llama.cpp model.

    Builds context from conversation history (last 3 turns), sends the
    prompt to Ollama for classification, and returns a validated
    ClassifierOutput.

    Args:
        request: The prompt request containing the user prompt and
            optional conversation history.

    Returns:
        A validated ClassifierOutput with task category, complexity,
        subtask, estimated tokens, and confidence.

    Raises:
        ClassifierError: If the classifier model returns invalid JSON,
            an HTTP error occurs, or the request times out.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Build context from last 3 conversation history turns
    if request.conversation_history:
        recent = request.conversation_history[-3:]
        for turn in recent:
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": request.prompt})

    # Call llama.cpp server
    payload = {
        "model": CLASSIFIER_MODEL,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "temperature": 0.0,
    }

    try:
        async with httpx.AsyncClient(timeout=CLASSIFIER_TIMEOUT_SEC) as client:
            response = await client.post(
                f"{LLAMA_CPP_URL}/v1/chat/completions",
                json=payload,
            )
            response.raise_for_status()
    except httpx.TimeoutException as e:
        logger.error("Classifier request timed out after %ds", CLASSIFIER_TIMEOUT_SEC)
        raise ClassifierError(
            f"Classifier timed out after {CLASSIFIER_TIMEOUT_SEC}s"
        ) from e
    except httpx.HTTPStatusError as e:
        logger.error("Classifier HTTP error: %s", e.response.status_code)
        raise ClassifierError(
            f"Classifier HTTP error: {e.response.status_code}",
            raw_output=e.response.text,
        ) from e
    except httpx.HTTPError as e:
        logger.error("Classifier HTTP error: %s", str(e))
        raise ClassifierError(f"Classifier HTTP error: {e}") from e

    # Parse the response
    try:
        resp_data = response.json()
        raw_output = resp_data.get("choices", [])[0].get("message", {}).get("content", "")
    except Exception as e:
        logger.error("Failed to parse llama.cpp response JSON")
        raise ClassifierError(
            "Failed to parse llama.cpp response", raw_output=response.text
        ) from e

    # Parse the classifier's JSON output
    import json

    try:
        parsed = json.loads(raw_output)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error("Classifier returned invalid JSON: %s", raw_output[:200])
        raise ClassifierError(
            f"Classifier returned invalid JSON: {e}",
            raw_output=raw_output,
        ) from e

    # Validate against schema
    try:
        result = ClassifierOutput(**parsed)
    except Exception as e:
        logger.error("Classifier output failed validation: %s", str(e))
        raise ClassifierError(
            f"Classifier output failed validation: {e}",
            raw_output=raw_output,
        ) from e

    # Warn on low confidence
    if result.confidence < 0.6:
        prompt_snippet = request.prompt[:80]
        logger.warning(
            "Low classifier confidence (%.2f) for prompt: '%s'",
            result.confidence,
            prompt_snippet,
        )

    return result
