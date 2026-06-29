# RouteWeave

> Route LLM prompts to the right model automatically — based on task type, complexity, and cost.

[![CI](https://github.com/Varun-Bhogayta/RouteWeave/actions/workflows/ci.yml/badge.svg)](https://github.com/Varun-Bhogayta/RouteWeave/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

## What It Does

RouteWeave sits in front of your LLM calls and automatically sends each request to the cheapest model that can handle it. You define the tiers — it handles the routing.

## Quick Start

```bash
git clone https://github.com/Varun-Bhogayta/RouteWeave
cd RouteWeave
docker compose up
```

## Send Your First Request

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"prompt-router","messages":[{"role":"user","content":"fix the bug in this python function"}]}'
```

## Why Use This?

- **Save costs** — Simple tasks go to cheap models, complex tasks get quality
- **Single endpoint** — One API for OpenAI, Anthropic, Google, Ollama, and more
- **OpenAI-compatible** — Works with VS Code, OpenCode, and any OpenAI SDK

## How It Works

```
Client Request
      ↓
┌─────────────────────────────────────┐
│  /v1/chat/completions               │
│                                     │
│  1. Classify prompt (Ollama)        │
│  2. Route to best tier              │
│  3. Dispatch to model               │
│  4. Return response                 │
└─────────────────────────────────────┘
      ↓
OpenAI-Compatible Response
```

## Supported Providers

- **Ollama** — Local models (phi3, llama, mistral, etc.)
- **OpenAI** — GPT-4o, GPT-4, GPT-3.5
- **Anthropic** — Claude 3.5, Claude 3
- **Google** — Gemini 1.5, Gemini Pro
- **Groq** — Mixtral, Llama
- **Mistral** — Mistral Large, Medium

## Configuration

Define your own tiers in `config/tiers.yaml`:

```yaml
tiers:
  - id: local-fast
    label: "Local Fast (Phi-3)"
    model: phi3:mini
    provider: ollama
    conditions:
      complexity: [low]
      category: [code, general, data]
    cost_limit:
      max_tokens_per_request: 2000
      max_usd_per_day: null
    fallback: null

  - id: premium-cloud
    label: "Premium (Claude Sonnet)"
    model: claude-sonnet-4-5
    provider: anthropic
    conditions:
      complexity: [high]
      category: [code, reasoning, data, general]
    cost_limit:
      max_tokens_per_request: 32000
      max_usd_per_day: 20.00
    fallback: null
```

See [docs/configuration.md](docs/configuration.md) for full details.

## Connecting Your Tools

### VS Code (Continue.dev)

```json
{
  "models": [{
    "title": "RouteWeave",
    "provider": "openai",
    "model": "prompt-router",
    "apiBase": "http://localhost:8000",
    "apiKey": "your-key-here"
  }]
}
```

### OpenCode

```bash
OPENAI_BASE_URL=http://localhost:8000 \
OPENAI_API_KEY=your-key-here \
opencode
```

### Python OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="your-key-here"
)

response = client.chat.completions.create(
    model="prompt-router",
    messages=[{"role": "user", "content": "explain binary search"}]
)

print(response.choices[0].message.content)
```

## Dashboard

Access the web dashboard at: http://localhost:8000/dashboard

- **Tier List** — View and manage configured tiers
- **Budget View** — See daily spend per tier
- **Test Prompt** — Send test requests and see routing decisions

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/chat/completions` | POST | OpenAI-compatible chat endpoint |
| `/v1/models` | GET | List available models |
| `/health` | GET | Health check |
| `/tiers` | GET | List configured tiers |
| `/tiers` | POST | Add new tier |
| `/tiers/{id}` | PUT | Update tier |
| `/tiers/{id}` | DELETE | Delete tier |
| `/reload` | POST | Hot-reload tier config |
| `/budget` | GET | Daily spend overview |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CLASSIFIER_MODEL` | Ollama model for classification | `phi3:mini` |
| `OLLAMA_URL` | Ollama API endpoint | `http://localhost:11434` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `TIER_CONFIG_PATH` | Path to tier config file | `config/tiers.yaml` |
| `ROLE_MAP` | API key to role mapping | - |
| `LOG_LEVEL` | Logging level | `INFO` |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `GOOGLE_API_KEY` | Google API key | - |
| `GROQ_API_KEY` | Groq API key | - |
| `MISTRAL_API_KEY` | Mistral API key | - |

## Python SDK

Use the typed Python client without writing raw HTTP:

```python
from sdk.client import RouterClient

with RouterClient("http://localhost:8000", api_key="devkey456") as client:
    result = client.route("Fix the off-by-one in my binary search")
    print(result.tier_id)        # "local-fast"
    print(result.response)       # model's answer
    print(f"{result.latency_ms:.0f}ms")  # "342ms"
```

See [sdk/README.md](sdk/README.md) for all methods and error handling.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[Apache 2.0](LICENSE)
