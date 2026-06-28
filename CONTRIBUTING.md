# Contributing to RouteWeave

Thank you for considering contributing to RouteWeave! This document provides guidelines and instructions for contributing.

## Ways to Contribute

- **Report Bugs** — Open a [GitHub Issue](https://github.com/Varun-Bhogayta/RouteWeave/issues) with steps to reproduce
- **Suggest Features** — Submit a feature request via GitHub Issues
- **Improve Documentation** — Fix typos, add examples, clarify explanations
- **Add Provider Support** — Integrate new LLM providers (see below)
- **Write Examples** — Create usage examples for common scenarios
- **Fix Bugs** — Submit a pull request with a fix

## Local Development Setup

### Prerequisites

- Python 3.12+
- Docker and Docker Compose
- Git

### Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/Varun-Bhogayta/RouteWeave
   cd prompt-router
   ```

2. **Set up environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys as needed
   ```

3. **Start development services**
   ```bash
   docker compose -f docker-compose.dev.yml up
   ```

4. **Install dependencies (optional, for local development)**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # or .venv\Scripts\activate  # Windows
   pip install -e ".[dev]"
   ```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=router --cov-report=term-missing

# Run specific test file
pytest tests/test_config_loader.py -v
```

## Code Style

### Python

- **Version:** Python 3.12+
- **Type Hints:** Required on all function signatures and return types
- **Async:** Use async/await throughout — no sync blocking I/O
- **Pydantic:** v2 only (no v1 syntax)
- **No print() statements** — use logging module only
- **Docstrings:** Required on all public functions and classes

### Logging

```python
import logging
logger = logging.getLogger(__name__)

# Use logger.info(), logger.warning(), logger.error()
# Never use print()
```

### Error Handling

- Define custom exception classes for domain-specific errors
- Log before re-raising or converting exceptions
- Never swallow exceptions silently

## Pull Request Process

### Before Submitting

- [ ] Tests pass locally (`pytest tests/ -v`)
- [ ] New behavior has corresponding tests
- [ ] Code follows style guidelines
- [ ] Documentation updated (if applicable)
- [ ] CHANGELOG.md updated (if applicable)

### PR Description

Include:
1. What this PR does
2. Why the change is needed
3. How to test the changes
4. Any breaking changes

### Review Process

1. Maintainers will review your PR within 7 days
2. Address any feedback or requested changes
3. Once approved, a maintainer will merge your PR

## Adding a New Provider

To add support for a new LLM provider:

### 1. Update Schemas

In `models/schemas.py`, add your provider to `VALID_PROVIDERS`:

```python
VALID_PROVIDERS = Literal["ollama", "openai", "anthropic", "google", "groq", "mistral", "your_provider"]
```

### 2. Update Dispatcher

In `router/dispatcher.py`, add model string formatting for your provider:

```python
# In the dispatch() function
if tier.provider == "your_provider":
    model_str = f"your_provider/{tier.model}"
```

### 3. Add Environment Variable

In `.env.example`, add your provider's API key:

```
YOUR_PROVIDER_API_KEY=
```

### 4. Document It

Add a row to `docs/providers.md`:

```markdown
| Provider | API Key Env Var | Model Format | Notes |
|----------|-----------------|--------------|-------|
| YourProvider | YOUR_PROVIDER_API_KEY | your_provider/model-name | Additional notes |
```

### 5. Test It

Create a tier config using your provider and verify it works end-to-end.

## Reporting Security Vulnerabilities

**Do NOT open a public GitHub issue for security vulnerabilities.**

If you discover a security vulnerability, please report it responsibly:

1. Email: security@yourdomain.com (replace with actual email)
2. Include: Description of the vulnerability, steps to reproduce, potential impact
3. Response time: Within 48 hours
4. We will work with you to understand and address the issue before any public disclosure

## Code of Conduct

Please be respectful and constructive in all interactions. We are committed to providing a welcoming and inclusive experience for everyone.

## Questions?

If you have questions about contributing, feel free to open a GitHub Issue with the "question" label.
