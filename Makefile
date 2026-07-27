# =============================================================================
# IntelliProcess AI - Project Commands
# =============================================================================

.PHONY: help install dev test lint build deploy clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --------------- Setup ---------------

install: ## Install all dependencies (backend + frontend)
	cd backend && pip install -r requirements.txt -r requirements-dev.txt
	cd frontend && npm install

# --------------- Development ---------------

dev-backend: ## Run backend locally
	cd backend && uvicorn app.main:app --reload --port 8000

dev-frontend: ## Run frontend locally
	cd frontend && npm run dev

# --------------- Testing ---------------

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests
	cd backend && pytest tests/ -v --cov=app

test-frontend: ## Run frontend tests
	cd frontend && npm run test

# --------------- Linting ---------------

lint: lint-backend lint-frontend ## Run all linters

lint-backend: ## Lint backend
	cd backend && ruff check . && ruff format --check .

lint-frontend: ## Lint frontend
	cd frontend && npm run lint

# --------------- Build ---------------

build-backend: ## Build backend for deployment
	cd backend && pip install -r requirements.txt -t .build/

build-frontend: ## Build frontend for deployment
	cd frontend && npm run build

build: build-backend build-frontend ## Build all

# --------------- Infrastructure ---------------

deploy: ## Deploy infrastructure via SAM
	cd infrastructure && sam build && sam deploy

deploy-guided: ## Deploy infrastructure (first time, guided)
	cd infrastructure && sam build && sam deploy --guided

# --------------- Data ---------------

seed: ## Seed sample data
	cd backend && python -m scripts.seed_data

sync-kb: ## Trigger Knowledge Base sync
	cd backend && python -m scripts.sync_knowledge_base

create-users: ## Create Cognito test users
	cd backend && python -m scripts.create_users

# --------------- Cleanup ---------------

clean: ## Remove build artifacts
	rm -rf backend/.build
	rm -rf backend/.pytest_cache
	rm -rf backend/__pycache__
	rm -rf frontend/dist
	rm -rf infrastructure/.aws-sam
