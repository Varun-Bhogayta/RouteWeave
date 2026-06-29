"""Routing engine for selecting the best tier based on classifier output.

Implements the tier matching algorithm with specificity scoring and
budget enforcement.
"""

from __future__ import annotations

import logging

from models.schemas import ClassifierOutput, TierConfig

logger = logging.getLogger(__name__)


# ── Exceptions ─────────────────────────────────────────────────


class NoTierMatchedError(Exception):
    """Raised when no configured tier matches the classifier output.

    Attributes:
        classifier_output: The classifier output that failed to match.
    """

    def __init__(self, message: str, classifier_output: ClassifierOutput) -> None:
        self.classifier_output = classifier_output
        super().__init__(message)


class BudgetExceededError(Exception):
    """Raised when a tier's daily budget has been exceeded.

    Attributes:
        tier_id: The ID of the tier that exceeded its budget.
        limit_usd: The daily USD limit for the tier.
        current_spend_usd: The current daily spend for the tier.
    """

    def __init__(self, tier_id: str, limit_usd: float, current_spend_usd: float) -> None:
        self.tier_id = tier_id
        self.limit_usd = limit_usd
        self.current_spend_usd = current_spend_usd
        super().__init__(
            f"Tier '{tier_id}' has reached its daily limit of "
            f"${limit_usd:.2f} (current: ${current_spend_usd:.2f})."
        )


# ── Core function ──────────────────────────────────────────────


def select_tier(
    classifier_output: ClassifierOutput,
    tiers: list[TierConfig],
    user_role: str = "default",
    budget_state: dict = {},
) -> TierConfig:
    """Select the best matching tier for a classified prompt.

    Matching algorithm (in order):
        1. Filter tiers where both complexity and category match.
        2. If no tiers match, raise NoTierMatchedError.
        3. If multiple tiers match, rank by specificity score
           (lower = more specific = preferred).
        4. Check budget on the selected tier.
        5. Return the selected tier.

    Args:
        classifier_output: The structured output from the classifier.
        tiers: List of available tier configurations.
        user_role: The user's role (for future Phase 2 filtering).
        budget_state: Dict mapping tier_id to current daily spend in USD.

    Returns:
        The best matching TierConfig.

    Raises:
        NoTierMatchedError: If no tier matches the classifier output.
        BudgetExceededError: If the selected tier's daily budget is exceeded.
    """
    # TODO Phase 2: filter tiers by user_role before passing to routing engine

    # Step 1 — Filter: keep tiers where BOTH complexity AND category match
    matched: list[TierConfig] = []
    for tier in tiers:
        complexity_match = classifier_output.complexity in tier.conditions.complexity
        category_match = classifier_output.task_category in tier.conditions.category
        if complexity_match and category_match:
            matched.append(tier)

    # Step 2 — No matches
    if not matched:
        available_ids = [t.id for t in tiers]
        logger.warning(
            "No tier matched for category='%s' complexity='%s'. Available tiers: %s",
            classifier_output.task_category,
            classifier_output.complexity,
            available_ids,
        )
        raise NoTierMatchedError(
            f"No configured tier handles category='{classifier_output.task_category}' "
            f"complexity='{classifier_output.complexity}'. Check your tier config.",
            classifier_output=classifier_output,
        )

    # Step 3 — Rank by specificity (lower score = more specific)
    def specificity_score(tier: TierConfig) -> int:
        return len(tier.conditions.complexity) + len(tier.conditions.category)

    matched.sort(key=specificity_score)
    selected = matched[0]

    logger.info(
        "Selected tier '%s' (score=%d) from %d candidates for category='%s' complexity='%s'",
        selected.id,
        specificity_score(selected),
        len(matched),
        classifier_output.task_category,
        classifier_output.complexity,
    )

    # Step 4 — Budget check
    if selected.cost_limit.max_usd_per_day is not None:
        current = budget_state.get(selected.id, 0.0)
        if current >= selected.cost_limit.max_usd_per_day:
            logger.warning(
                "Budget exceeded for tier '%s': limit=$%.2f, current=$%.2f",
                selected.id,
                selected.cost_limit.max_usd_per_day,
                current,
            )
            raise BudgetExceededError(
                tier_id=selected.id,
                limit_usd=selected.cost_limit.max_usd_per_day,
                current_spend_usd=current,
            )

    # Step 5 — Return selected tier
    return selected
