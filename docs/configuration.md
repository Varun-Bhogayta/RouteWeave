# Configuration Reference

RouteWeave is configured entirely through `config/tiers.yaml` and environment variables. No code changes are needed to add or modify routing behavior.

---

## Tier Config (`config/tiers.yaml`)

### Full Schema

```yaml
tiers:
  - id: <slug>                          # required — ^[a-z0-9-]+$
    label: <human-readable name>        # required
    model: <model name>                 # required — e.g. "phi3:mini"
    provider: <provider>                # required — see valid values below
    conditions:
      complexity: [low|medium|high]     # required — at least one
      category: [code|reasoning|data|general]  # required — at least one
    cost_limit:
      max_tokens_per_request: <int>     # required — max tokens per call
      max_usd_per_day: <float|null>     # optional — null = unlimited
    fallback: null                      # always null (fail-fast design)
```

### Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `string` | ✅ | URL-safe slug, unique across all tiers. Pattern: `^[a-z0-9-]+$` |
| `label` | `string` | ✅ | Human-readable display name shown in the dashboard |
| `model` | `string` | ✅ | Model identifier as expected by the provider |
| `provider` | `string` | ✅ | One of: `ollama`, `openai`, `anthropic`, `google`, `groq`, `mistral` |
| `conditions.complexity` | `list` | ✅ | Complexity levels this tier handles. At least one of `low`, `medium`, `high` |
| `conditions.category` | `list` | ✅ | Task categories this tier handles. At least one of `code`, `reasoning`, `data`, `general` |
| `cost_limit.max_tokens_per_request` | `int` | ✅ | Hard cap on tokens per single LLM call |
| `cost_limit.max_usd_per_day` | `float\|null` | — | Daily spend cap in USD. `null` means unlimited |
| `fallback` | `null` | — | Always `null`. Fallback chaining is intentionally unsupported |

---

## Complexity Levels

| Level | When the classifier picks it |
|-------|------------------------------|
| `low` | Syntax fix, one-liner, factual lookup, format conversion |
| `medium` | Moderate codegen, summarization, structured analysis, explanation |
| `high` | System design, multi-step reasoning, architecture, complex debugging |

## Task Categories

| Category | What it covers |
|----------|---------------|
| `code` | Writing, fixing, reviewing, or explaining code |
| `reasoning` | Logic, math, planning, decision-making, analysis |
| `data` | SQL, data transformation, CSV/JSON processing, schemas |
| `general` | Everything else |

---

## Ambiguity Rules

The config loader rejects configurations that would cause non-deterministic routing:

- **Duplicate IDs** → `ValueError: Duplicate tier id: 'local-fast'`
- **Ambiguous conditions** → Two tiers with identical `complexity` AND `category` sets → `ValueError` naming both tier IDs

---

## Example Configurations

### Minimal (2 tiers)

```yaml
tiers:
  - id: local
    label: "Local (Phi-3)"
    model: phi3:mini
    provider: ollama
    conditions:
      complexity: [low, medium]
      category: [code, general, data, reasoning]
    cost_limit:
      max_tokens_per_request: 4000
      max_usd_per_day: null
    fallback: null

  - id: cloud
    label: "Cloud (GPT-4o)"
    model: gpt-4o
    provider: openai
    conditions:
      complexity: [high]
      category: [code, general, data, reasoning]
    cost_limit:
      max_tokens_per_request: 16000
      max_usd_per_day: 10.00
    fallback: null
```

### Full (3-tier default)

See [`config/tiers.yaml`](../config/tiers.yaml) for the shipped default covering `local-fast` → `mid-cloud` → `premium-cloud`.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TIER_CONFIG_PATH` | `config/tiers.yaml` | Path to the tier config file (YAML or JSON) |
| `CLASSIFIER_MODEL` | `phi3:mini` | Ollama model used for prompt classification |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server base URL |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL for budget tracking |
| `ROLE_MAP` | _(empty)_ | Bearer token → role mapping. Format: `key1:role1,key2:role2` |
| `LOG_LEVEL` | `INFO` | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `OPENAI_API_KEY` | _(none)_ | OpenAI API key |
| `ANTHROPIC_API_KEY` | _(none)_ | Anthropic API key |
| `GOOGLE_API_KEY` | _(none)_ | Google AI API key |
| `GROQ_API_KEY` | _(none)_ | Groq API key |
| `MISTRAL_API_KEY` | _(none)_ | Mistral API key |

Copy `.env.example` to `.env` and fill in only the providers you use.

---

## Hot Reload

Tier config can be reloaded at runtime without restarting:

```bash
curl -X POST http://localhost:8000/reload
# {"status": "reloaded", "tier_count": 3, "warnings": []}
```

This re-reads `TIER_CONFIG_PATH` from disk, re-validates all tiers, and atomically replaces the in-memory list.
