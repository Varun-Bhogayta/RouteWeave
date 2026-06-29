"""Middleware for API key to user role resolution.

Reads the ROLE_MAP environment variable and maps bearer tokens
to user roles. Used as a FastAPI dependency.
"""

from __future__ import annotations

import logging
import os

from fastapi import Header

logger = logging.getLogger(__name__)


# ── Core function ──────────────────────────────────────────────


def resolve_user_role(authorization: str | None) -> str:
    """Resolve a user role from an Authorization header.

    Reads ROLE_MAP from environment (format: "key1:role1,key2:role2"),
    extracts the bearer token from the Authorization header, and
    looks up the corresponding role.

    Args:
        authorization: The Authorization header value, expected in
            the format "Bearer <token>".

    Returns:
        The resolved role string, or "default" if no match is found,
        the header is missing, or the header is malformed.
    """
    # Read role map from env
    role_map_str = os.getenv("ROLE_MAP", "")
    if not role_map_str:
        return "default"

    # Parse "key1:role1,key2:role2" into dict
    role_map: dict[str, str] = {}
    for entry in role_map_str.split(","):
        entry = entry.strip()
        if ":" in entry:
            key, role = entry.split(":", 1)
            role_map[key.strip()] = role.strip()

    # Extract bearer token
    if not authorization:
        return "default"

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return "default"

    token = parts[1]

    # Look up role
    resolved = role_map.get(token, "default")

    if resolved != "default":
        logger.debug("Resolved role '%s' for token '***%s'", resolved, token[-4:])

    return resolved


# ── FastAPI dependency ─────────────────────────────────────────


def get_user_role(authorization: str | None = Header(None)) -> str:
    """FastAPI dependency for resolving user role from Authorization header.

    Usage:
        role: str = Depends(get_user_role)

    Args:
        authorization: The Authorization header value (injected by FastAPI).

    Returns:
        The resolved user role string.
    """
    return resolve_user_role(authorization)
