"""RouteWeave Python SDK client."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# ── Exceptions ─────────────────────────────────────────────────


class RouterClientError(Exception):
    """Raised when the router API returns an error response.

    Args:
        message: Human-readable error description.
        status_code: HTTP status code from the server.
        error_key: Machine-readable error key (e.g. ``"budget_exceeded"``).
        detail: Full error detail dict from the response body.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 0,
        error_key: str = "",
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.error_key = error_key
        self.detail = detail or {}
        super().__init__(message)


# ── Response dataclasses ────────────────────────────────────────


class ClassifierResult:
    """Classifier output attached to a route response.

    Attributes:
        task_category: One of ``code``, ``reasoning``, ``data``, ``general``.
        complexity: One of ``low``, ``medium``, ``high``.
        subtask: Optional short subtask label.
        estimated_tokens: Estimated tokens for the completion.
        confidence: Classifier confidence score (0.0–1.0).
    """

    __slots__ = ("task_category", "complexity", "subtask", "estimated_tokens", "confidence")

    def __init__(self, data: dict[str, Any]) -> None:
        self.task_category: str = data["task_category"]
        self.complexity: str = data["complexity"]
        self.subtask: str | None = data.get("subtask")
        self.estimated_tokens: int = data["estimated_tokens"]
        self.confidence: float = data["confidence"]

    def __repr__(self) -> str:
        return (
            f"ClassifierResult(category={self.task_category!r}, "
            f"complexity={self.complexity!r}, confidence={self.confidence})"
        )


class RouteResult:
    """Response from ``POST /route``.

    Attributes:
        tier_id: ID of the selected tier (e.g. ``"local-fast"``).
        model: Model name used for the response.
        provider: Provider name (e.g. ``"ollama"``, ``"anthropic"``).
        classifier: Classifier output that drove the routing decision.
        response: The LLM's text response.
        latency_ms: End-to-end latency in milliseconds.
        estimated_cost_usd: Estimated cost in USD (0.0 for local models).
    """

    __slots__ = (
        "tier_id", "model", "provider", "classifier", "response",
        "latency_ms", "estimated_cost_usd",
    )

    def __init__(self, data: dict[str, Any]) -> None:
        self.tier_id: str = data["tier_id"]
        self.model: str = data["model"]
        self.provider: str = data["provider"]
        self.classifier = ClassifierResult(data["classifier_output"])
        self.response: str = data["response"]
        self.latency_ms: float = data["latency_ms"]
        self.estimated_cost_usd: float = data.get("estimated_cost_usd", 0.0)

    def __repr__(self) -> str:
        return (
            f"RouteResult(tier={self.tier_id!r}, model={self.model!r}, "
            f"latency_ms={self.latency_ms:.1f}, cost=${self.estimated_cost_usd:.6f})"
        )


# ── Main client ─────────────────────────────────────────────────


class RouterClient:
    """Synchronous client for the RouteWeave router API.

    Args:
        base_url: Base URL of the running router (e.g. ``"http://localhost:8000"``).
        api_key: Optional Bearer token sent in the ``Authorization`` header.
        timeout: Request timeout in seconds (default: 30).

    Example::

        from routeweave import RouterClient

        client = RouterClient("http://localhost:8000", api_key="devkey456")
        result = client.route("explain binary search")
        print(result.tier_id)        # "local-fast"
        print(result.response)       # model's answer
        print(result.latency_ms)     # 342.1
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.Client(
            base_url=self._base_url,
            headers=headers,
            timeout=self._timeout,
        )

    # ── Public methods ──────────────────────────────────────────

    def route(
        self,
        prompt: str,
        *,
        user_role: str = "default",
        conversation_history: list[dict[str, str]] | None = None,
        budget_state: dict[str, float] | None = None,
    ) -> RouteResult:
        """Route a prompt through the intelligent router.

        Args:
            prompt: The user's input prompt (must be non-empty).
            user_role: Role string for logging/future tier filtering.
            conversation_history: Previous turns as ``[{"role": ..., "content": ...}]``.
                Only the last 3 turns are used by the classifier.
            budget_state: Per-tier daily spend map (e.g. ``{"premium-cloud": 4.5}``).
                Leave empty to let Redis handle budget state server-side.

        Returns:
            A :class:`RouteResult` with tier, model, response, latency, and cost.

        Raises:
            RouterClientError: On any HTTP 4xx/5xx response.
            httpx.TimeoutException: If the request exceeds the timeout.
        """
        payload: dict[str, Any] = {
            "prompt": prompt,
            "user_role": user_role,
            "conversation_history": conversation_history or [],
            "budget_state": budget_state or {},
        }
        resp = self._request("POST", "/route", json=payload)
        return RouteResult(resp)

    def get_tiers(self) -> list[dict[str, Any]]:
        """Fetch all configured routing tiers.

        Returns:
            List of tier config dicts as returned by ``GET /tiers``.

        Raises:
            RouterClientError: On any HTTP error.
        """
        data = self._request("GET", "/tiers")
        return data.get("tiers", [])

    def create_tier(self, tier: dict[str, Any]) -> dict[str, Any]:
        """Create a new routing tier.

        Args:
            tier: Tier config dict matching the ``TierConfig`` schema.

        Returns:
            The created tier config dict.

        Raises:
            RouterClientError: On validation failure (422) or duplicate ID (409).
        """
        return self._request("POST", "/tiers", json=tier)

    def update_tier(self, tier_id: str, tier: dict[str, Any]) -> dict[str, Any]:
        """Replace an existing tier by ID.

        Args:
            tier_id: The slug ID of the tier to replace.
            tier: Full replacement tier config dict.

        Returns:
            The updated tier config dict.

        Raises:
            RouterClientError: If tier not found (404) or validation fails (422).
        """
        return self._request("PUT", f"/tiers/{tier_id}", json=tier)

    def delete_tier(self, tier_id: str) -> dict[str, Any]:
        """Delete a tier by ID.

        Args:
            tier_id: The slug ID of the tier to delete.

        Returns:
            ``{"status": "deleted", "tier_id": "..."}``

        Raises:
            RouterClientError: If tier not found (404).
        """
        return self._request("DELETE", f"/tiers/{tier_id}")

    def reload(self) -> dict[str, Any]:
        """Hot-reload tier config from disk without restarting.

        Returns:
            ``{"status": "reloaded", "tier_count": N, "warnings": [...]}``

        Raises:
            RouterClientError: On any HTTP error.
        """
        return self._request("POST", "/reload")

    def get_budget(self) -> dict[str, Any]:
        """Fetch today's budget spend per tier.

        Returns:
            ``{"date": "YYYY-MM-DD", "tiers": {"tier_id": spend_usd, ...}}``

        Raises:
            RouterClientError: On any HTTP error.
        """
        return self._request("GET", "/budget")

    def get_health(self) -> dict[str, Any]:
        """Check router health status.

        Returns:
            ``{"status": "ok", "tier_count": N, "classifier_model": "...",
            "redis_connected": True|False}``

        Raises:
            RouterClientError: On any HTTP error.
        """
        return self._request("GET", "/health")

    # ── Context manager ─────────────────────────────────────────

    def close(self) -> None:
        """Close the underlying HTTP client and release connections."""
        self._client.close()

    def __enter__(self) -> RouterClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ── Internal ────────────────────────────────────────────────

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Execute an HTTP request and handle errors.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            path: URL path relative to base_url.
            **kwargs: Passed directly to ``httpx.Client.request``.

        Returns:
            Parsed JSON response body as a dict.

        Raises:
            RouterClientError: On HTTP 4xx or 5xx responses.
        """
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise httpx.TimeoutException(
                f"Request to {method} {path} timed out after {self._timeout}s"
            ) from exc

        if not response.is_success:
            try:
                body: dict[str, Any] = response.json()
            except Exception:
                body = {"message": response.text}

            error_key = body.get("error", "")
            message = body.get("message", f"HTTP {response.status_code}")
            logger.error(
                "Router API error %s %s → %d %s: %s",
                method, path, response.status_code, error_key, message,
            )
            raise RouterClientError(
                message,
                status_code=response.status_code,
                error_key=error_key,
                detail=body,
            )

        return response.json()
