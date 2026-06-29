.PHONY: test up down build lint

# ── Run tests inside Docker (no local Python needed) ──────────
test:
	docker compose -f docker-compose.test.yml run --rm --build test

# ── Run tests and keep container logs visible ─────────────────
test-watch:
	docker compose -f docker-compose.test.yml up --build --abort-on-container-exit

# ── Start the full production stack ───────────────────────────
up:
	docker compose up --build

# ── Stop all services ─────────────────────────────────────────
down:
	docker compose down -v

# ── Build production image only ───────────────────────────────
build:
	docker build --target production -t routeweave:latest .

# ── Lint (runs inside Docker too, no local ruff needed) ───────
lint:
	docker compose -f docker-compose.test.yml run --rm test ruff check router/ models/
