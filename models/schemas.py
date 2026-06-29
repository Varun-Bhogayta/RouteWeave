"""Pydantic v2 schemas for RouteWeave."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ── Classifier output ──────────────────────────────────────────


class ClassifierOutput(BaseModel):
    """Output from the prompt classifier."""

    task_category: Literal["code", "reasoning", "data", "general"]
    complexity: Literal["low", "medium", "high"]
    subtask: Optional[str] = None
    estimated_tokens: int = Field(gt=0)
    confidence: float = Field(ge=0.0, le=1.0)


# ── Tier config ────────────────────────────────────────────────

VALID_PROVIDERS = Literal["ollama", "openai", "anthropic", "google", "groq", "mistral"]
VALID_COMPLEXITY = Literal["low", "medium", "high"]
VALID_CATEGORY = Literal["code", "reasoning", "data", "general"]


class CostLimit(BaseModel):
    """Cost limits for a tier."""

    max_tokens_per_request: int = Field(gt=0)
    max_usd_per_day: Optional[float] = Field(default=None, gt=0)


class TierConditions(BaseModel):
    """Conditions that determine when a tier is selected."""

    complexity: list[VALID_COMPLEXITY]
    category: list[VALID_CATEGORY]

    @field_validator("complexity", "category")
    @classmethod
    def no_empty_list(cls, v: list[str]) -> list[str]:
        """Ensure lists are not empty."""
        if not v:
            raise ValueError("must contain at least one value")
        return v


class TierConfig(BaseModel):
    """Configuration for a routing tier."""

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    label: str
    model: str
    provider: VALID_PROVIDERS
    conditions: TierConditions
    cost_limit: CostLimit
    fallback: None = None  # always null — fail fast by design


# ── Request / Response ─────────────────────────────────────────


class PromptRequest(BaseModel):
    """Internal prompt request format."""

    prompt: str = Field(min_length=1)
    user_role: str = "default"
    conversation_history: list[dict] = []
    budget_state: dict = {}


class RouterResponse(BaseModel):
    """Internal router response format."""

    tier_id: str
    model: str
    provider: str
    classifier_output: ClassifierOutput
    response: str
    latency_ms: float
    estimated_cost_usd: float = 0.0


# ── Error responses ────────────────────────────────────────────


class ErrorDetail(BaseModel):
    """Structured error response."""

    error: str  # machine-readable snake_case key
    message: str  # human-readable explanation
    classifier_output: Optional[ClassifierOutput] = None
    available_tiers: Optional[list[str]] = None
    tier_id: Optional[str] = None
    daily_limit_usd: Optional[float] = None
    current_spend_usd: Optional[float] = None


# ── OpenAI-compatible request ──────────────────────────────────


class OpenAIMessage(BaseModel):
    """OpenAI-compatible message format."""

    role: Literal["system", "user", "assistant"]
    content: str


class OpenAIChatRequest(BaseModel):
    """OpenAI-compatible chat completion request."""

    model: str  # ignored — router decides
    messages: list[OpenAIMessage]
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    user: Optional[str] = None  # can carry user_role here


# ── OpenAI-compatible response ─────────────────────────────────


class OpenAIChoice(BaseModel):
    """OpenAI-compatible choice format."""

    index: int
    message: OpenAIMessage
    finish_reason: str = "stop"


class OpenAIUsage(BaseModel):
    """OpenAI-compatible usage format."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class OpenAIChatResponse(BaseModel):
    """OpenAI-compatible chat completion response."""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[OpenAIChoice]
    usage: OpenAIUsage
