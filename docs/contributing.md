# Contributing to RouteWeave

Thank you for your interest in contributing! This document covers how to set up your dev environment, run tests, and submit a pull request.

---

## Ways to Contribute

- 🐛 **Report bugs** — open a [Bug Report issue](https://github.com/Varun-Bhogayta/RouteWeave/issues/new?template=bug_report.md)
- ✨ **Request features** — open a [Feature Request issue](https://github.com/Varun-Bhogayta/RouteWeave/issues/new?template=feature_request.md)
- 📖 **Improve docs** — fix typos, clarify explanations, add examples
- 🔌 **Add a provider** — see the guide below
- 🧪 **Add tests** — coverage for edge cases is always welcome

---

## Local Dev Setup

```bash
git clone https://github.com/Varun-Bhogayta/RouteWeave.git
cd RouteWeave

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows

# Install in editable mode with dev extras
pip install -e ".[dev]"

# Copy env file and configure
cp .env.example .env
```

Start supporting services:

```bash
docker compose up redis ollama -d
ollama pull phi3:mini              # pull the default classifier model
```

Run the router locally:

```bash
uvicorn router.main:app --reload --port 8000
```

---

## Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage report
pytest tests/ -v --cov=router --cov=models --cov-report=term-missing

# Single file
pytest tests/test_routing_engine.py -v
```

All 23 tests run with mocked external dependencies (Ollama + LiteLLM) — **no live services needed**.

---

## Linting

```bash
ruff check router/ models/ sdk/        # check only
ruff check router/ models/ sdk/ --fix  # auto-fix safe issues
```

---

## Pre-commit Hooks (recommended)

```bash
pip install pre-commit
pre-commit install
```

This runs `ruff` and file hygiene checks automatically on every `git commit`.

---

## Before Submitting a PR

- [ ] All tests pass: `pytest tests/ -v`
- [ ] No lint errors: `ruff check router/ models/ sdk/`
- [ ] New behavior has a corresponding test
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] Docs updated if you changed config schema or API behavior

---

## Adding a New Provider

1. Add the provider name to `VALID_PROVIDERS` in [`models/schemas.py`](../models/schemas.py).
2. Add the API key variable to `.env.example` with a comment.
3. Add a row to the providers table in [`docs/providers.md`](providers.md).
4. Write a tier in `config/tiers.yaml` that uses the provider and verify it routes correctly.
5. Submit a PR — no other code changes needed.

---

## Code Style

- **Python 3.12+** with full type hints on every function signature.
- **Pydantic v2** only — no v1 syntax.
- **async/await throughout** — no sync blocking I/O in any router code.
- **`logger = logging.getLogger(__name__)`** in every module — no `print()`.
- **Docstrings** on every public function: one-line summary + Args + Returns + Raises.

See [CODING STANDARDS](../llm-router.plan) in the plan for the full ruleset.
