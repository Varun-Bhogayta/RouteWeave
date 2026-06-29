"""
fastapi_integration.py — embed RouteWeave into an existing FastAPI application.

This example shows how to use the SDK client as a FastAPI dependency,
so your existing app can route prompts without duplicating HTTP boilerplate.

Run: uvicorn fastapi_integration:app --port 9000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, AsyncGenerator

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from sdk.client import RouterClient, RouterClientError


# ── App state ──────────────────────────────────────────────────


_router_client: RouterClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create the SDK client once at startup and close it on shutdown."""
    global _router_client
    _router_client = RouterClient(
        base_url="http://localhost:8000",
        api_key="devkey456",   # set to None if no auth configured
    )
    yield
    if _router_client:
        _router_client.close()


app = FastAPI(title="My App (with RouteWeave)", lifespan=lifespan)


# ── Dependency ─────────────────────────────────────────────────


def get_router_client() -> RouterClient:
    """FastAPI dependency that provides the shared SDK client."""
    assert _router_client is not None, "RouterClient not initialised"
    return _router_client


RouterClientDep = Annotated[RouterClient, Depends(get_router_client)]


# ── Request / Response models ───────────────────────────────────


class AskRequest(BaseModel):
    question: str
    user_role: str = "default"


class AskResponse(BaseModel):
    answer: str
    tier_used: str
    latency_ms: float
    cost_usd: float


# ── Routes ─────────────────────────────────────────────────────


@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, client: RouterClientDep) -> AskResponse:
    """Route a question through RouteWeave and return the answer."""
    try:
        result = client.route(body.question, user_role=body.user_role)
        return AskResponse(
            answer=result.response,
            tier_used=result.tier_id,
            latency_ms=result.latency_ms,
            cost_usd=result.estimated_cost_usd,
        )
    except RouterClientError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=exc.status_code or 500, detail=str(exc)) from exc


@app.get("/health")
def health(client: RouterClientDep) -> dict:
    """Proxy the RouteWeave health check."""
    return client.get_health()
