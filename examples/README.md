# Examples

Runnable examples showing how to use RouteWeave in different scenarios.

## Prerequisites

All examples require a running RouteWeave router:

```bash
docker compose up
```

## Examples

### [`basic_usage.py`](basic_usage.py)
The simplest possible integration — route a prompt and print the result.

```bash
python examples/basic_usage.py
```

### [`custom_tiers.yaml`](custom_tiers.yaml)
A 5-tier config covering all complexity × category combinations with a local → cloud → premium cost progression. Use it as a starting point for your own tier setup:

```bash
# Point the router at this config
TIER_CONFIG_PATH=examples/custom_tiers.yaml uvicorn router.main:app --reload
```

### [`fastapi_integration.py`](fastapi_integration.py)
Embed RouteWeave into an existing FastAPI application using a shared SDK client as a FastAPI dependency.

```bash
uvicorn examples.fastapi_integration:app --port 9000
# Then: curl -X POST http://localhost:9000/ask -H "Content-Type: application/json" \
#            -d '{"question": "explain binary search"}'
```
