# RouteWeave Python SDK

A thin, typed Python client for the [RouteWeave](https://github.com/Varun-Bhogayta/RouteWeave) router API.

## Installation

```bash
pip install routeweave          # once published to PyPI
# or directly from source:
pip install -e ".[dev]"
```

## Quick Start

```python
from sdk.client import RouterClient

client = RouterClient("http://localhost:8000", api_key="devkey456")

result = client.route("Fix the off-by-one error in my binary search")
print(result.tier_id)               # "local-fast"
print(result.model)                 # "phi3:mini"
print(result.classifier.complexity) # "low"
print(result.response)              # model's answer
print(f"{result.latency_ms:.0f}ms") # "342ms"
print(f"${result.estimated_cost_usd:.6f}")  # "$0.000000"
```

## Usage as a Context Manager

```python
with RouterClient("http://localhost:8000") as client:
    result = client.route("Generate a SQL query to find top 10 customers")
    print(result.tier_id)  # "mid-cloud"
```

## All Methods

### `route(prompt, *, user_role, conversation_history, budget_state) → RouteResult`

Route a prompt to the best available LLM tier.

```python
result = client.route(
    "Design a distributed caching system",
    user_role="developer",
    conversation_history=[
        {"role": "user", "content": "I need help with system design"},
        {"role": "assistant", "content": "Sure, what are the requirements?"},
    ],
)
```

**RouteResult fields:**

| Field | Type | Description |
|-------|------|-------------|
| `tier_id` | `str` | Selected tier slug (e.g. `"premium-cloud"`) |
| `model` | `str` | Model used (e.g. `"claude-sonnet-4-5"`) |
| `provider` | `str` | Provider (e.g. `"anthropic"`) |
| `classifier` | `ClassifierResult` | Classifier output that drove routing |
| `response` | `str` | LLM's text response |
| `latency_ms` | `float` | End-to-end latency in ms |
| `estimated_cost_usd` | `float` | Cost in USD (0.0 for local models) |

**ClassifierResult fields:**

| Field | Type | Description |
|-------|------|-------------|
| `task_category` | `str` | `code` / `reasoning` / `data` / `general` |
| `complexity` | `str` | `low` / `medium` / `high` |
| `subtask` | `str \| None` | Short subtask label (e.g. `"bug_fix"`) |
| `estimated_tokens` | `int` | Estimated response token count |
| `confidence` | `float` | Classifier confidence (0.0–1.0) |

---

### `get_tiers() → list[dict]`

Fetch all configured routing tiers.

```python
tiers = client.get_tiers()
for tier in tiers:
    print(tier["id"], tier["provider"], tier["model"])
```

### `create_tier(tier: dict) → dict`

Add a new tier (validates schema, checks for duplicates).

```python
new_tier = client.create_tier({
    "id": "groq-fast",
    "label": "Groq Fast (Mixtral)",
    "model": "mixtral-8x7b-32768",
    "provider": "groq",
    "conditions": {"complexity": ["low", "medium"], "category": ["general"]},
    "cost_limit": {"max_tokens_per_request": 4000, "max_usd_per_day": 2.00},
    "fallback": None,
})
```

### `update_tier(tier_id: str, tier: dict) → dict`

Replace an existing tier by ID.

### `delete_tier(tier_id: str) → dict`

Delete a tier by ID.

### `reload() → dict`

Hot-reload tier config from disk without restarting the server.

### `get_budget() → dict`

Get today's spend per tier.

```python
budget = client.get_budget()
print(budget["date"])                     # "2026-06-29"
print(budget["tiers"]["premium-cloud"])   # 4.23
```

### `get_health() → dict`

Check server health.

```python
health = client.get_health()
print(health["status"])           # "ok"
print(health["redis_connected"])  # True
print(health["tier_count"])       # 3
```

---

## Error Handling

```python
from sdk.client import RouterClient, RouterClientError

client = RouterClient("http://localhost:8000")

try:
    result = client.route("...")
except RouterClientError as e:
    print(e.status_code)   # 429
    print(e.error_key)     # "budget_exceeded"
    print(e.detail)        # full error body dict
    print(str(e))          # human-readable message
```

**Error keys:**

| `error_key` | HTTP | Meaning |
|-------------|------|---------|
| `classifier_error` | 422 | Classifier LLM failed to parse prompt |
| `no_tier_matched` | 422 | No tier covers this complexity+category |
| `budget_exceeded` | 429 | Tier hit its daily USD cap |
| `dispatch_error` | 502 | LLM provider returned an error |
