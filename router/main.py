"""FastAPI application for RouteWeave — Intelligent LLM Prompt Router.

Provides all API routes, lifespan management, and static file serving
for the dashboard.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from models.schemas import (
    ErrorDetail,
    OpenAIChatRequest,
    OpenAIChatResponse,
    OpenAIChoice,
    OpenAIMessage,
    OpenAIUsage,
    PromptRequest,
    RouterResponse,
    TierConfig,
)
from router import budget_tracker
from router.classifier import ClassifierError, classify_prompt
from router.config_loader import load_tiers, persist_tiers
from router.dispatcher import DispatchError, dispatch
from router.middleware import get_user_role
from router.routing_engine import BudgetExceededError, NoTierMatchedError, select_tier

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────

TIER_CONFIG_PATH: str = os.getenv("TIER_CONFIG_PATH", "config/tiers.yaml")
CLASSIFIER_MODEL: str = os.getenv("CLASSIFIER_MODEL", "phi3:mini")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


# ── Logging setup ─────────────────────────────────────────────


def _setup_logging() -> None:
    """Configure logging with the format specified in the plan."""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


# ── Lifespan ──────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    On startup:
        - Sets up logging
        - Loads tier configuration from disk
        - Connects to Redis and logs status

    On shutdown:
        - Closes Redis connection
    """
    _setup_logging()
    logger.info("Starting RouteWeave...")

    # Load tiers
    try:
        tiers = load_tiers(TIER_CONFIG_PATH)
        app.state.tiers = tiers
        app.state.config_path = TIER_CONFIG_PATH
        logger.info("Loaded %d tiers from %s", len(tiers), TIER_CONFIG_PATH)
    except Exception as e:
        logger.error("Failed to load tiers: %s", e)
        app.state.tiers = []
        app.state.config_path = TIER_CONFIG_PATH

    # Check Redis
    redis_ok = await budget_tracker.ping()
    if redis_ok:
        logger.info("Redis connected at %s", budget_tracker.REDIS_URL)
    else:
        logger.warning(
            "Redis not available at %s — budget tracking disabled",
            budget_tracker.REDIS_URL,
        )

    yield

    # Shutdown
    await budget_tracker.close_redis()
    logger.info("RouteWeave shut down.")


# ── App ────────────────────────────────────────────────────────

app = FastAPI(
    title="RouteWeave",
    description="Intelligent LLM Prompt Router — route prompts to the right model automatically.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── POST /route ───────────────────────────────────────────────


@app.post("/route", response_model=RouterResponse)
async def route_prompt(
    request: PromptRequest,
    role: str = Depends(get_user_role),
) -> RouterResponse:
    """Route a prompt to the best matching LLM model.

    Steps:
        1. Resolve user role from Authorization header.
        2. Classify the prompt using the local classifier model.
        3. Select the best tier based on classification.
        4. Get daily budget spend from Redis.
        5. Dispatch to the selected model.
        6. Record spend in Redis.
        7. Return the response with metadata.

    Args:
        request: The prompt request body.
        role: The resolved user role (from Depends).

    Returns:
        RouterResponse with tier info, classifier output, response,
        latency, and estimated cost.
    """
    # Step 1 — Role resolved via Depends

    # Step 2 — Classify
    try:
        classifier_output = await classify_prompt(request)
    except ClassifierError as e:
        logger.error("Classification failed: %s", e)
        raise HTTPException(
            status_code=422,
            detail=ErrorDetail(
                error="classifier_error",
                message=str(e),
            ).model_dump(),
        )

    # Step 3 — Select tier (with budget state from Redis)
    budget_state: dict[str, float] = {}
    for tier in app.state.tiers:
        if tier.cost_limit.max_usd_per_day is not None:
            spend = await budget_tracker.get_daily_spend(tier.id)
            budget_state[tier.id] = spend

    try:
        selected_tier = select_tier(
            classifier_output=classifier_output,
            tiers=app.state.tiers,
            user_role=role,
            budget_state=budget_state,
        )
    except NoTierMatchedError as e:
        raise HTTPException(
            status_code=422,
            detail=ErrorDetail(
                error="no_tier_matched",
                message=str(e),
                classifier_output=e.classifier_output,
                available_tiers=[t.id for t in app.state.tiers],
            ).model_dump(),
        )
    except BudgetExceededError as e:
        raise HTTPException(
            status_code=429,
            detail=ErrorDetail(
                error="budget_exceeded",
                message=str(e),
                tier_id=e.tier_id,
                daily_limit_usd=e.limit_usd,
                current_spend_usd=e.current_spend_usd,
            ).model_dump(),
        )

    # Step 4 — Build messages
    messages = []
    for turn in request.conversation_history:
        messages.append(turn)
    messages.append({"role": "user", "content": request.prompt})

    # Step 5 — Dispatch
    try:
        response_text, latency_ms, cost = await dispatch(
            tier=selected_tier,
            messages=messages,
            max_tokens=selected_tier.cost_limit.max_tokens_per_request,
        )
    except DispatchError as e:
        raise HTTPException(
            status_code=502,
            detail=ErrorDetail(
                error="dispatch_error",
                message=str(e),
            ).model_dump(),
        )

    # Step 6 — Record spend
    if cost > 0:
        await budget_tracker.add_spend(selected_tier.id, cost)

    # Step 7 — Return response
    return RouterResponse(
        tier_id=selected_tier.id,
        model=selected_tier.model,
        provider=selected_tier.provider,
        classifier_output=classifier_output,
        response=response_text,
        latency_ms=round(latency_ms, 1),
        estimated_cost_usd=cost,
    )


# ── OpenAI-compatible endpoint ─────────────────────────────────


@app.post("/v1/chat/completions")
async def openai_chat_completions(
    request: OpenAIChatRequest,
    role: str = Depends(get_user_role),
) -> OpenAIChatResponse:
    """OpenAI-compatible chat completion endpoint.

    Translates an OpenAI-format request into RouteWeave's internal
    format, routes it, and returns an OpenAI-compatible response.

    Args:
        request: OpenAI-format chat completion request.
        role: The resolved user role (from Depends).

    Returns:
        OpenAI-compatible chat completion response.
    """
    # Extract the last user message as the prompt
    user_messages = [m for m in request.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(
            status_code=422,
            detail={"error": "no_user_message", "message": "No user message found in request"},
        )

    prompt = user_messages[-1].content

    # Build conversation history from prior messages
    conversation_history = [
        {"role": m.role, "content": m.content}
        for m in request.messages[:-1]  # all except the last user message
    ]

    # Create internal request
    internal_request = PromptRequest(
        prompt=prompt,
        user_role=request.user or role,
        conversation_history=conversation_history,
    )

    # Route through the standard pipeline
    # Step 1 — Classify
    try:
        classifier_output = await classify_prompt(internal_request)
    except ClassifierError as e:
        raise HTTPException(
            status_code=422,
            detail={"error": "classifier_error", "message": str(e)},
        )

    # Step 2 — Select tier
    budget_state: dict[str, float] = {}
    for tier in app.state.tiers:
        if tier.cost_limit.max_usd_per_day is not None:
            spend = await budget_tracker.get_daily_spend(tier.id)
            budget_state[tier.id] = spend

    try:
        selected_tier = select_tier(
            classifier_output=classifier_output,
            tiers=app.state.tiers,
            user_role=internal_request.user_role,
            budget_state=budget_state,
        )
    except NoTierMatchedError as e:
        raise HTTPException(status_code=422, detail={"error": "no_tier_matched", "message": str(e)})
    except BudgetExceededError as e:
        raise HTTPException(status_code=429, detail={"error": "budget_exceeded", "message": str(e)})

    # Step 3 — Dispatch
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    max_tokens = request.max_tokens or selected_tier.cost_limit.max_tokens_per_request

    try:
        response_text, latency_ms, cost = await dispatch(
            tier=selected_tier,
            messages=messages,
            max_tokens=max_tokens,
        )
    except DispatchError as e:
        raise HTTPException(status_code=502, detail={"error": "dispatch_error", "message": str(e)})

    # Record spend
    if cost > 0:
        await budget_tracker.add_spend(selected_tier.id, cost)

    # Build OpenAI-compatible response
    import uuid

    return OpenAIChatResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
        created=int(time.time()),
        model=selected_tier.model,
        choices=[
            OpenAIChoice(
                index=0,
                message=OpenAIMessage(role="assistant", content=response_text),
                finish_reason="stop",
            )
        ],
        usage=OpenAIUsage(
            prompt_tokens=classifier_output.estimated_tokens,
            completion_tokens=max_tokens,
            total_tokens=classifier_output.estimated_tokens + max_tokens,
        ),
    )


# ── GET /v1/models ─────────────────────────────────────────────


@app.get("/v1/models")
async def list_models() -> dict:
    """List available models in OpenAI-compatible format.

    Returns:
        Dict with model list data.
    """
    models = []
    for tier in app.state.tiers:
        models.append({
            "id": tier.model,
            "object": "model",
            "created": 0,
            "owned_by": tier.provider,
        })

    # Also add the meta "prompt-router" model
    models.append({
        "id": "prompt-router",
        "object": "model",
        "created": 0,
        "owned_by": "routeweave",
    })

    return {"object": "list", "data": models}


# ── GET /tiers ─────────────────────────────────────────────────


@app.get("/tiers")
async def get_tiers() -> dict:
    """List all configured tiers.

    Returns:
        Dict with list of tier configurations.
    """
    return {"tiers": [tier.model_dump() for tier in app.state.tiers]}


# ── POST /tiers ────────────────────────────────────────────────


@app.post("/tiers", status_code=201)
async def create_tier(tier: TierConfig) -> dict:
    """Create a new tier.

    Validates the tier, checks for duplicate IDs and ambiguous
    conditions, then appends to the tier list and persists to disk.

    Args:
        tier: The new tier configuration.

    Returns:
        The created tier configuration.
    """
    # Check duplicate ID
    for existing in app.state.tiers:
        if existing.id == tier.id:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "duplicate_tier_id",
                    "message": f"Tier id '{tier.id}' already exists",
                },
            )

    # Check ambiguous conditions
    new_key = (
        tuple(sorted(tier.conditions.complexity)),
        tuple(sorted(tier.conditions.category)),
    )
    for existing in app.state.tiers:
        existing_key = (
            tuple(sorted(existing.conditions.complexity)),
            tuple(sorted(existing.conditions.category)),
        )
        if new_key == existing_key:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "ambiguous_conditions",
                    "message": f"Tier '{tier.id}' has identical conditions to tier '{existing.id}'",
                },
            )

    # Append and persist
    app.state.tiers.append(tier)
    persist_tiers(app.state.tiers, app.state.config_path)

    logger.info("Created tier '%s'", tier.id)
    return tier.model_dump()


# ── PUT /tiers/{tier_id} ──────────────────────────────────────


@app.put("/tiers/{tier_id}")
async def update_tier(tier_id: str, tier: TierConfig) -> dict:
    """Update an existing tier.

    Args:
        tier_id: The ID of the tier to update.
        tier: The updated tier configuration.

    Returns:
        The updated tier configuration.
    """
    for i, existing in enumerate(app.state.tiers):
        if existing.id == tier_id:
            app.state.tiers[i] = tier
            persist_tiers(app.state.tiers, app.state.config_path)
            logger.info("Updated tier '%s'", tier_id)
            return tier.model_dump()

    raise HTTPException(
        status_code=404,
        detail={"error": "tier_not_found", "message": f"Tier '{tier_id}' not found"},
    )


# ── DELETE /tiers/{tier_id} ───────────────────────────────────


@app.delete("/tiers/{tier_id}")
async def delete_tier(tier_id: str) -> dict:
    """Delete an existing tier.

    Args:
        tier_id: The ID of the tier to delete.

    Returns:
        Confirmation with deleted tier ID.
    """
    for i, existing in enumerate(app.state.tiers):
        if existing.id == tier_id:
            app.state.tiers.pop(i)
            persist_tiers(app.state.tiers, app.state.config_path)
            logger.info("Deleted tier '%s'", tier_id)
            return {"status": "deleted", "tier_id": tier_id}

    raise HTTPException(
        status_code=404,
        detail={"error": "tier_not_found", "message": f"Tier '{tier_id}' not found"},
    )


# ── POST /reload ──────────────────────────────────────────────


@app.post("/reload")
async def reload_tiers() -> dict:
    """Hot-reload tier configuration from disk.

    Returns:
        Status with tier count and any warnings.
    """
    import io
    import logging as _logging

    # Capture warnings during reload
    warnings: list[str] = []
    handler = _logging.StreamHandler(io.StringIO())
    handler.setLevel(_logging.WARNING)
    config_logger = _logging.getLogger("router.config_loader")
    config_logger.addHandler(handler)

    try:
        tiers = load_tiers(app.state.config_path)
        app.state.tiers = tiers
        logger.info("Reloaded %d tiers from %s", len(tiers), app.state.config_path)

        # Extract warnings from captured output
        stream = handler.stream
        stream.seek(0)
        for line in stream.readlines():
            line = line.strip()
            if line:
                warnings.append(line)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "reload_failed", "message": str(e)},
        )
    finally:
        config_logger.removeHandler(handler)

    return {
        "status": "reloaded",
        "tier_count": len(app.state.tiers),
        "warnings": warnings,
    }


# ── GET /budget ───────────────────────────────────────────────


@app.get("/budget")
async def get_budget() -> dict:
    """Get daily budget spend overview.

    Returns:
        Dict with date and per-tier spend data.
    """
    from datetime import datetime

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    tier_spend = await budget_tracker.get_all_today()

    return {
        "date": today,
        "tiers": tier_spend,
    }


# ── GET /health ───────────────────────────────────────────────


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint.

    Returns:
        Status with tier count, classifier model, and Redis status.
    """
    redis_ok = await budget_tracker.ping()

    return {
        "status": "ok",
        "tier_count": len(app.state.tiers),
        "classifier_model": CLASSIFIER_MODEL,
        "classifier_backend": "llama.cpp",
        "redis_connected": redis_ok,
    }


# ── Static files (dashboard) ─────────────────────────────────

# Mount dashboard if the directory has files
_dashboard_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard")
if os.path.isdir(_dashboard_dir):
    app.mount("/dashboard", StaticFiles(directory=_dashboard_dir, html=True), name="dashboard")
