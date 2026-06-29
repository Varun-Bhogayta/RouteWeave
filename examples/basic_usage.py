"""
basic_usage.py — minimal RouteWeave example.

Requires a running RouteWeave router at http://localhost:8000.
Start it with: docker compose up
"""

from sdk.client import RouterClient, RouterClientError

# 1. Create a client (no api_key → uses "default" role)
client = RouterClient("http://localhost:8000")

# 2. Route a prompt
try:
    result = client.route("Fix the off-by-one error in my binary search function")

    print(f"Tier:      {result.tier_id}")               # "local-fast"
    print(f"Model:     {result.model}")                 # "phi3:mini"
    print(f"Category:  {result.classifier.task_category}")  # "code"
    print(f"Complexity:{result.classifier.complexity}") # "low"
    print(f"Latency:   {result.latency_ms:.0f}ms")
    print(f"Cost:      ${result.estimated_cost_usd:.6f}")
    print()
    print("Response:")
    print(result.response)

except RouterClientError as e:
    print(f"Error [{e.error_key}]: {e}")
finally:
    client.close()
