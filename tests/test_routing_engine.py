"""Tests for router/routing_engine.py."""

from __future__ import annotations

import pytest

from models.schemas import ClassifierOutput, TierConfig
from router.routing_engine import BudgetExceededError, NoTierMatchedError, select_tier


@pytest.fixture
def sample_tiers() -> list[TierConfig]:
    """Create sample tiers for routing tests."""
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


def test_exact_match_selects_correct_tier(sample_tiers: list[TierConfig]) -> None:
    """Test that an exact match selects the correct tier."""
    output = ClassifierOutput(
        task_category="code",
        complexity="low",
        subtask="bug_fix",
        estimated_tokens=350,
        confidence=0.94,
    )
    result = select_tier(output, sample_tiers)
    assert result.id == "local-fast"


def test_prefers_more_specific_tier(sample_tiers: list[TierConfig]) -> None:
    """Test that a more specific tier is preferred over a broader one."""
    # Add a broad tier that also covers low+code
    broad_tier = TierConfig(
        id="broad-tier",
        label="Broad",
        model="some-model",
        provider="ollama",
        conditions={
            "complexity": ["low", "medium"],
            "category": ["code", "general", "data", "reasoning"],
        },
        cost_limit={"max_tokens_per_request": 4000},
    )
    tiers = sample_tiers + [broad_tier]

    output = ClassifierOutput(
        task_category="code",
        complexity="low",
        subtask="syntax_fix",
        estimated_tokens=200,
        confidence=0.95,
    )
    result = select_tier(output, tiers)
    # local-fast has score 3 (1 complexity + 2 categories)
    # broad-tier has score 6 (2 complexity + 4 categories)
    # local-fast should win
    assert result.id == "local-fast"


def test_no_match_raises_no_tier_matched_error(sample_tiers: list[TierConfig]) -> None:
    """Test that no matching tier raises NoTierMatchedError."""
    # Remove the premium tier so high+code has no match
    tiers = [t for t in sample_tiers if t.id != "premium-cloud"]

    output = ClassifierOutput(
        task_category="code",
        complexity="high",
        subtask="architecture_design",
        estimated_tokens=4000,
        confidence=0.88,
    )

    with pytest.raises(NoTierMatchedError) as exc_info:
        select_tier(output, tiers)

    assert exc_info.value.classifier_output.task_category == "code"
    assert exc_info.value.classifier_output.complexity == "high"


def test_budget_exceeded_raises(sample_tiers: list[TierConfig]) -> None:
    """Test that exceeding budget raises BudgetExceededError."""
    output = ClassifierOutput(
        task_category="code",
        complexity="high",
        subtask="system_design",
        estimated_tokens=5000,
        confidence=0.92,
    )

    budget_state = {"premium-cloud": 25.0}

    with pytest.raises(BudgetExceededError) as exc_info:
        select_tier(output, sample_tiers, budget_state=budget_state)

    assert exc_info.value.tier_id == "premium-cloud"
    assert exc_info.value.limit_usd == 20.0
    assert exc_info.value.current_spend_usd == 25.0
