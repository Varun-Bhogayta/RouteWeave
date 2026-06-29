"""Configuration loader for RouteWeave tier configs."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

import yaml
from pydantic import ValidationError

from models.schemas import TierConfig

logger = logging.getLogger(__name__)


def load_tiers(config_path: str) -> list[TierConfig]:
    """Load and validate tier configuration from a file.

    Auto-detects format from file extension (.yaml/.yml → YAML, .json → JSON).
    Validates each tier against TierConfig schema and checks for duplicates
    and ambiguous conditions.

    Args:
        config_path: Path to the tier configuration file.

    Returns:
        List of validated TierConfig objects.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If tier validation fails, duplicate IDs exist,
            or ambiguous conditions are detected.
    """
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path.absolute()}")

    # Auto-detect format from extension
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        tiers = _load_yaml(path)
    elif suffix == ".json":
        tiers = _load_json(path)
    else:
        raise ValueError(f"Unsupported config format: {suffix}. Use .yaml, .yml, or .json")

    # Validate and check for issues
    _validate_tiers(tiers)

    return tiers


def _load_yaml(path: Path) -> list[TierConfig]:
    """Load tiers from a YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)

    if not data or "tiers" not in data:
        raise ValueError("Config file must contain a 'tiers' key")

    return _parse_tiers(data["tiers"])


def _load_json(path: Path) -> list[TierConfig]:
    """Load tiers from a JSON file."""
    with open(path) as f:
        data = json.load(f)

    if not data or "tiers" not in data:
        raise ValueError("Config file must contain a 'tiers' key")

    return _parse_tiers(data["tiers"])


def _parse_tiers(raw_tiers: list[dict]) -> list[TierConfig]:
    """Parse raw tier dictionaries into TierConfig objects."""
    tiers = []
    for tier_data in raw_tiers:
        try:
            tier = TierConfig(**tier_data)
            tiers.append(tier)
        except ValidationError as e:
            tier_id = tier_data.get("id", "unknown")
            raise ValueError(f"Tier '{tier_id}': {e}") from e
    return tiers


def _validate_tiers(tiers: list[TierConfig]) -> None:
    """Validate tiers for duplicates and ambiguous conditions."""
    # Check for duplicate IDs
    seen_ids: set[str] = set()
    for tier in tiers:
        if tier.id in seen_ids:
            raise ValueError(f"Duplicate tier id: '{tier.id}'")
        seen_ids.add(tier.id)

    # Check for ambiguous conditions
    condition_map: dict[tuple, list[str]] = {}
    for tier in tiers:
        key = (
            tuple(sorted(tier.conditions.complexity)),
            tuple(sorted(tier.conditions.category)),
        )
        if key in condition_map:
            existing = condition_map[key]
            raise ValueError(
                f"Ambiguous conditions: tiers '{existing[0]}' and '{tier.id}' "
                f"have identical complexity and category sets"
            )
        condition_map[key] = [tier.id]

    # Coverage warnings
    _check_coverage(tiers)


def _check_coverage(tiers: list[TierConfig]) -> None:
    """Log warnings for missing complexity or category coverage."""
    all_complexity = {"low", "medium", "high"}
    all_category = {"code", "reasoning", "data", "general"}

    covered_complexity: set[str] = set()
    covered_category: set[str] = set()

    for tier in tiers:
        covered_complexity.update(tier.conditions.complexity)
        covered_category.update(tier.conditions.category)

    missing_complexity = all_complexity - covered_complexity
    if missing_complexity:
        logger.warning(
            f"No tier covers complexity levels: {', '.join(sorted(missing_complexity))}"
        )

    missing_category = all_category - covered_category
    if missing_category:
        logger.warning(
            f"No tier covers categories: {', '.join(sorted(missing_category))}"
        )


def persist_tiers(tiers: list[TierConfig], config_path: str) -> None:
    """Persist tier configuration to disk as YAML.

    Uses atomic write (temp file + os.replace) to prevent corruption.

    Args:
        tiers: List of TierConfig objects to save.
        config_path: Path to write the configuration file.
    """
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to serializable format
    data = {"tiers": [tier.model_dump() for tier in tiers]}

    # Atomic write
    dir_path = path.parent
    with tempfile.NamedTemporaryFile(
        mode="w", dir=dir_path, suffix=".tmp", delete=False
    ) as tmp_file:
        tmp_path = tmp_file.name
        yaml.dump(data, tmp_file, default_flow_style=False, sort_keys=False)

    os.replace(tmp_path, path)
    logger.info(f"Persisted {len(tiers)} tiers to {path}")
