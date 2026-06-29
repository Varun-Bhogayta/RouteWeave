# Supported Providers

RouteWeave routes to any provider supported by [LiteLLM](https://docs.litellm.ai). The table below covers the six providers in the default schema.

---

## Provider Reference

| Provider | `provider` value | Model string format | Required env var |
|----------|-----------------|---------------------|-----------------|
| Ollama (local) | `ollama` | `phi3:mini`, `llama3:8b`, etc. | _(none — runs locally)_ |
| OpenAI | `openai` | `gpt-4o`, `gpt-4o-mini`, `o1-mini` | `OPENAI_API_KEY` |
| Anthropic | `anthropic` | `claude-sonnet-4-5`, `claude-haiku-3-5` | `ANTHROPIC_API_KEY` |
| Google | `google` | `gemini-1.5-flash`, `gemini-1.5-pro` | `GOOGLE_API_KEY` |
| Groq | `groq` | `mixtral-8x7b-32768`, `llama3-70b-8192` | `GROQ_API_KEY` |
| Mistral | `mistral` | `mistral-small-latest`, `mistral-large-latest` | `MISTRAL_API_KEY` |

---

## How Model Strings Are Built

The dispatcher (`router/dispatcher.py`) constructs the LiteLLM model string automatically:

```
ollama   → "ollama/{model}"           e.g. "ollama/phi3:mini"
others   → "{provider}/{model}"       e.g. "anthropic/claude-sonnet-4-5"
```

You never need to format this yourself — just set `model` and `provider` in the tier config.

---

## Provider Notes

### Ollama (local)
- No API key required. Requires [Ollama](https://ollama.ai) running locally or via Docker.
- Cost is always `$0.00` — local inference.
- Pull a model before first use: `ollama pull phi3:mini`
- Set `OLLAMA_URL` if running on a non-default host/port.

### OpenAI
- Models: `gpt-4o` (best quality), `gpt-4o-mini` (fastest/cheapest), `o1-mini` (reasoning).
- Cost estimation is supported by LiteLLM.

### Anthropic
- Models: `claude-sonnet-4-5` (balanced), `claude-haiku-3-5` (fast).
- Cost estimation is supported by LiteLLM.

### Google
- Models: `gemini-1.5-flash` (fast, cheap), `gemini-1.5-pro` (powerful).
- Use `GOOGLE_API_KEY` from [Google AI Studio](https://aistudio.google.com).

### Groq
- Inference-optimized hardware — extremely low latency.
- Free tier available at [console.groq.com](https://console.groq.com).
- Models: `llama3-70b-8192`, `mixtral-8x7b-32768`, `gemma2-9b-it`.

### Mistral
- Models: `mistral-small-latest`, `mistral-medium-latest`, `mistral-large-latest`.
- API key from [console.mistral.ai](https://console.mistral.ai).

---

## Adding a New Provider

LiteLLM supports 100+ providers. To add one:

1. Add the provider name to `VALID_PROVIDERS` in [`models/schemas.py`](../models/schemas.py):
   ```python
   VALID_PROVIDERS = Literal["ollama", "openai", "anthropic", "google", "groq", "mistral", "your_provider"]
   ```
2. Add the API key to `.env.example`:
   ```
   YOUR_PROVIDER_API_KEY=
   ```
3. Create a tier using the new provider in `config/tiers.yaml`.
4. Add a row to the table above in this file.
5. Consult [LiteLLM's provider docs](https://docs.litellm.ai/docs/providers) for the correct model string format.
