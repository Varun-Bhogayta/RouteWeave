# Architecture

RouteWeave sits between your application and a pool of LLM providers. It classifies every prompt using a local model, then routes it to the cheapest tier capable of handling it.

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Your Application                         │
└───────────────────────────────┬─────────────────────────────────┘
                                │  POST /route
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         RouteWeave                              │
│                                                                 │
│  ┌──────────────────┐                                           │
│  │ Context Assembler│  Injects last 3 conversation turns        │
│  └────────┬─────────┘                                           │
│           │                                                     │
│           ▼                                                     │
│  ┌──────────────────┐                                           │
│  │  Classifier LLM  │  Local Ollama model → structured JSON     │
│  │  (phi3:mini)     │  { task_category, complexity, ... }       │
│  └────────┬─────────┘                                           │
│           │                                                     │
│           ▼                                                     │
│  ┌──────────────────┐                                           │
│  │  Routing Engine  │  Filter tiers → rank by specificity       │
│  └────────┬─────────┘                                           │
│           │                                                     │
│           ▼                                                     │
│  ┌──────────────────┐                                           │
│  │  Budget Tracker  │  Redis: daily spend vs per-tier cap       │
│  │  (Redis)         │  Graceful degrade if Redis is down        │
│  └────────┬─────────┘                                           │
│           │                                                     │
│           ▼                                                     │
│  ┌──────────────────┐                                           │
│  │   Dispatcher     │  LiteLLM → selected provider              │
│  │   (LiteLLM)      │  Returns (text, latency_ms, cost_usd)     │
│  └────────┬─────────┘                                           │
│           │                                                     │
└───────────┼─────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                RouterResponse (JSON)                            │
│  tier_id · model · provider · classifier_output                 │
│  response · latency_ms · estimated_cost_usd                     │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### Context Assembler
Builds the classifier input by combining the current prompt with up to the last 3 turns of `conversation_history`. Each turn is formatted as `ROLE: content\n`.

### Classifier LLM (`router/classifier.py`)
A local Ollama model (`phi3:mini` by default) classifies every prompt into a structured JSON object:

```json
{
  "task_category": "code",
  "complexity": "low",
  "subtask": "bug_fix",
  "estimated_tokens": 350,
  "confidence": 0.94
}
```

- Uses `httpx.AsyncClient` with a 15-second timeout.
- Logs a WARNING if `confidence < 0.6`.
- Raises `ClassifierError` on parse failure or timeout.

### Routing Engine (`router/routing_engine.py`)
Pure function — no I/O. Implements a two-step algorithm:

1. **Filter** — keep tiers whose `complexity` and `category` both contain the classifier output values.
2. **Rank** — if multiple tiers match, prefer the most specific one (lowest `len(complexity) + len(category)` score).

Raises `NoTierMatchedError` (→ HTTP 422) if no tier matches.

### Budget Tracker (`router/budget_tracker.py`)
Redis-based daily spend tracking. Key pattern: `budget:{tier_id}:{YYYY-MM-DD}`.

- Keys automatically expire after 48 hours.
- **Never raises** — all functions catch `redis.RedisError` and return safe defaults so a Redis outage never crashes a request.

### Dispatcher (`router/dispatcher.py`)
Wraps `litellm.acompletion`. Builds the model string (`ollama/phi3:mini` or `anthropic/claude-sonnet-4-5`) and records latency. Extracts cost from LiteLLM's cost estimation or defaults to 0.0.

### Middleware (`router/middleware.py`)
Reads the `ROLE_MAP` env var (`key1:role1,key2:role2`) and maps Bearer tokens to role strings. Unknown tokens → `"default"`.

## Design Principles

| Principle | Implementation |
|-----------|---------------|
| Zero hardcoded tiers | All tiers defined in `config/tiers.yaml` |
| Fail fast | No fallback chaining — `NoTierMatchedError` on no match |
| Degrade gracefully | Redis down → skip budget check, log warning |
| Hot-reloadable config | `POST /reload` re-reads YAML without restart |
| Async throughout | `httpx.AsyncClient`, `litellm.acompletion`, `redis.asyncio` |
