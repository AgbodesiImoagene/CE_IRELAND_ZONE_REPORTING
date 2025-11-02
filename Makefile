# Makefile for Zonal Reporting Platform
# Docker Compose file location
COMPOSE_FILE := infra/docker-compose.yml

# Service names
API_SERVICE := api

.PHONY: help build build-no-cache build-no-cache-pull up down restart \
	logs logs-api logs-all migrate seed test test-verbose api-shell \
	clean clean-volumes rebuild rebuild-api ps worker worker-shell \
	format format-docker format-check format-check-docker

# Default target
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'

# Build targets
build: ## Build the application container (quick build)
	docker compose -f $(COMPOSE_FILE) build $(API_SERVICE)

build-no-cache: ## Build the application container without cache
	docker compose -f $(COMPOSE_FILE) build --no-cache $(API_SERVICE)

build-no-cache-pull: ## Build with no cache and pull base images from registry
	docker compose -f $(COMPOSE_FILE) build --no-cache --pull $(API_SERVICE)

# Container management
up: build ## Start all services (builds API container first)
	docker compose -f $(COMPOSE_FILE) up -d
	@echo "Starting background worker..."
	@$(MAKE) worker

down: ## Stop and remove all containers
	docker compose -f $(COMPOSE_FILE) down

restart: ## Restart all services
	docker compose -f $(COMPOSE_FILE) restart

ps: ## Show running containers
	docker compose -f $(COMPOSE_FILE) ps

# Logging
logs: ## Follow API service logs
	docker compose -f $(COMPOSE_FILE) logs -f $(API_SERVICE)

logs-api: logs ## Alias for logs (API service)

logs-all: ## Follow all services logs
	docker compose -f $(COMPOSE_FILE) logs -f

# Database operations
migrate: ## Run database migrations
	docker compose -f $(COMPOSE_FILE) exec $(API_SERVICE) alembic upgrade head

seed: ## Seed roles and permissions
	docker compose -f $(COMPOSE_FILE) exec $(API_SERVICE) python -m app.scripts.seed_permissions

# Testing
test: up ## Run tests with SQLite (starts services first)
	@echo "Waiting for services to be ready..."
	@sleep 2
	docker compose -f $(COMPOSE_FILE) exec $(API_SERVICE) pytest -q

test-verbose: up ## Run tests with SQLite (verbose output)
	@echo "Waiting for services to be ready..."
	@sleep 2
	docker compose -f $(COMPOSE_FILE) exec $(API_SERVICE) pytest -v

test-pg: up ## Run tests with PostgreSQL (for RLS testing)
	@echo "Waiting for services to be ready..."
	@sleep 2
	@echo "Creating test database if it doesn't exist..."
	@docker compose -f $(COMPOSE_FILE) exec -T db psql -U app -d postgres -c "CREATE DATABASE test_app;" 2>/dev/null || true
	@echo "Running tests with PostgreSQL (RLS enabled)..."
	@docker compose -f $(COMPOSE_FILE) exec -e USE_POSTGRES=true -e POSTGRES_TEST_URL=postgresql+psycopg://app:app@db:5432/test_app $(API_SERVICE) pytest -q

test-pg-verbose: up ## Run tests with PostgreSQL (verbose output)
	@echo "Waiting for services to be ready..."
	@sleep 2
	@echo "Creating test database if it doesn't exist..."
	@docker compose -f $(COMPOSE_FILE) exec -T db psql -U app -d postgres -c "CREATE DATABASE test_app;" 2>/dev/null || true
	@echo "Running tests with PostgreSQL (RLS enabled)..."
	@docker compose -f $(COMPOSE_FILE) exec -e USE_POSTGRES=true -e POSTGRES_TEST_URL=postgresql+psycopg://app:app@db:5432/test_app $(API_SERVICE) pytest -v

# Development
api-shell: ## Open a shell in the API container
	docker compose -f $(COMPOSE_FILE) exec $(API_SERVICE) bash

worker: ## Start background job worker
	docker compose -f $(COMPOSE_FILE) up -d worker

worker-shell: ## Open a shell in the worker container
	docker compose -f $(COMPOSE_FILE) exec worker bash

# Code formatting
format: ## Format code with black (run locally, requires black installed)
	black apps/api

format-docker: ## Format code with black (in Docker container)
	docker compose -f $(COMPOSE_FILE) exec $(API_SERVICE) pip install black --quiet || true
	docker compose -f $(COMPOSE_FILE) exec $(API_SERVICE) black app/

format-check: ## Check code formatting with black (no changes, run locally)
	black --check apps/api

format-check-docker: ## Check code formatting with black (in Docker container)
	docker compose -f $(COMPOSE_FILE) exec $(API_SERVICE) pip install black --quiet || true
	docker compose -f $(COMPOSE_FILE) exec $(API_SERVICE) black --check app/

# Cleanup
clean: ## Remove stopped containers and unused images
	docker compose -f $(COMPOSE_FILE) down
	docker system prune -f

clean-volumes: ## Remove all volumes (WARNING: deletes data)
	docker compose -f $(COMPOSE_FILE) down -v

# Rebuild targets (kept for backward compatibility)
rebuild: build-no-cache ## Alias for build-no-cache
rebuild-api: build-no-cache ## Alias for build-no-cache
