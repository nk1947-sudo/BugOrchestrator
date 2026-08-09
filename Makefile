.PHONY: help up down logs build \
	api-install api-dev api-test api-migrate \
	orchestrator-install orchestrator-dev orchestrator-test \
	worker-build worker-run worker-test \
	dashboard-install dashboard-dev dashboard-build \
	test lint

help:
	@echo "Aegis Mesh - common targets"
	@echo "  make up                  - docker compose up --build (full stack)"
	@echo "  make down                - docker compose down"
	@echo "  make logs                - tail all service logs"
	@echo "  make api-dev             - run API locally with reload"
	@echo "  make api-migrate         - apply alembic migrations"
	@echo "  make orchestrator-dev    - run orchestrator loop locally"
	@echo "  make worker-run          - run Go scan-worker locally"
	@echo "  make dashboard-dev       - run Next.js dashboard locally"
	@echo "  make test                - run all test suites"

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

# ---- API (Python / FastAPI) ----
api-install:
	cd services/api && pip install -e ".[dev]"

api-dev:
	cd services/api && uvicorn api.main:app --reload --port 8000 --app-dir src

api-test:
	cd services/api && python -m pytest tests -v

api-migrate:
	cd services/api && alembic upgrade head

# ---- Orchestrator (Python) ----
orchestrator-install:
	cd services/orchestrator && pip install -e ".[dev]"

orchestrator-dev:
	cd services/orchestrator && python -m orchestrator.main

orchestrator-test:
	cd services/orchestrator && python -m pytest tests -v

# ---- Scan worker (Go) ----
worker-build:
	cd services/scan-worker && go build -o bin/scan-worker ./cmd/worker

worker-run:
	cd services/scan-worker && go run ./cmd/worker

worker-test:
	cd services/scan-worker && go test ./...

# ---- Dashboard (Next.js) ----
dashboard-install:
	cd apps/dashboard && npm install

dashboard-dev:
	cd apps/dashboard && npm run dev

dashboard-build:
	cd apps/dashboard && npm run build

test: api-test orchestrator-test worker-test
