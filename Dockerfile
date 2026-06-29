# ── Stage 1: base ─────────────────────────────────────────────
FROM python:3.12-slim AS base
WORKDIR /app

# Install build dependencies
COPY pyproject.toml .

# Copy source code
COPY router/ ./router/
COPY models/ ./models/
COPY config/ ./config/
COPY dashboard/ ./dashboard/

# ── Stage 2: test ─────────────────────────────────────────────
# Run the full pytest suite inside this stage.
# llama.cpp and Redis are mocked in tests — no real services needed.
FROM base AS test

# Install all dependencies including dev extras (pytest, ruff, etc.)
RUN pip install --no-cache-dir -e ".[dev]"

# Copy tests
COPY tests/ ./tests/

# Run tests with verbose output and coverage report
CMD ["pytest", "tests/", "-v", "--tb=short", "--cov=router", "--cov=models", "--cov-report=term-missing"]

# ── Stage 3: production ────────────────────────────────────────
FROM base AS production

# Install only production dependencies
RUN pip install --no-cache-dir -e .

EXPOSE 8000
CMD ["uvicorn", "router.main:app", "--host", "0.0.0.0", "--port", "8000"]
