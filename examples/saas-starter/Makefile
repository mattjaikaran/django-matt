# =============================================================================
# SaaS Starter - Makefile with uv
# =============================================================================
#
# This Makefile provides commands for development, testing, and deployment
# using uv as the Python package manager.
#
# Usage:
#   make help          - Show available commands
#   make install       - Install dependencies with uv
#   make dev           - Start development server
#   make test          - Run tests
#
# =============================================================================

.PHONY: help install install-dev sync update dev run shell migrate \
        test test-cov lint format check clean docker-build docker-up \
        docker-down docker-logs celery celery-beat seed db-reset \
        migrations types openapi

# Default target
.DEFAULT_GOAL := help

# Colors for terminal output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# =============================================================================
# Help
# =============================================================================

help: ## Show this help message
	@echo ""
	@echo "$(BLUE)SaaS Starter - Available Commands$(NC)"
	@echo ""
	@echo "$(GREEN)Setup:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(install|sync|update)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-18s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Development:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(dev|run|shell|migrate|migrations)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-18s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Testing & Quality:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(test|lint|format|check)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-18s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Docker:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(docker)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-18s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Background Tasks:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(celery)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-18s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Database:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(db-|seed)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-18s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Utilities:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(types|openapi|clean)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-18s$(NC) %s\n", $$1, $$2}'
	@echo ""

# =============================================================================
# Setup & Dependencies (using uv)
# =============================================================================

install: ## Install dependencies with uv
	@echo "$(BLUE)Installing dependencies with uv...$(NC)"
	uv sync

install-dev: ## Install all dependencies including dev
	@echo "$(BLUE)Installing all dependencies with uv...$(NC)"
	uv sync --all-extras

sync: ## Sync dependencies from lockfile
	@echo "$(BLUE)Syncing dependencies...$(NC)"
	uv sync

update: ## Update all dependencies
	@echo "$(BLUE)Updating dependencies...$(NC)"
	uv lock --upgrade
	uv sync

add: ## Add a dependency (usage: make add pkg=package-name)
	@echo "$(BLUE)Adding $(pkg)...$(NC)"
	uv add $(pkg)

add-dev: ## Add a dev dependency (usage: make add-dev pkg=package-name)
	@echo "$(BLUE)Adding dev dependency $(pkg)...$(NC)"
	uv add --dev $(pkg)

remove: ## Remove a dependency (usage: make remove pkg=package-name)
	@echo "$(BLUE)Removing $(pkg)...$(NC)"
	uv remove $(pkg)

# =============================================================================
# Development
# =============================================================================

dev: ## Start development server with hot reload
	@echo "$(BLUE)Starting development server...$(NC)"
	uv run python manage.py runserver 0.0.0.0:8000

run: ## Start production-like server with uvicorn
	@echo "$(BLUE)Starting uvicorn server...$(NC)"
	uv run uvicorn saas_project.asgi:application --host 0.0.0.0 --port 8000 --reload

run-daphne: ## Start ASGI server with Daphne (WebSocket support)
	@echo "$(BLUE)Starting Daphne server...$(NC)"
	uv run daphne -b 0.0.0.0 -p 8000 saas_project.asgi:application

shell: ## Open Django shell with IPython
	@echo "$(BLUE)Opening Django shell...$(NC)"
	uv run python manage.py shell

shell-plus: ## Open Django shell_plus (if django-extensions installed)
	@echo "$(BLUE)Opening Django shell_plus...$(NC)"
	uv run python manage.py shell_plus

dbshell: ## Open database shell
	@echo "$(BLUE)Opening database shell...$(NC)"
	uv run python manage.py dbshell

# =============================================================================
# Database
# =============================================================================

migrate: ## Run database migrations
	@echo "$(BLUE)Running migrations...$(NC)"
	uv run python manage.py migrate

migrations: ## Create new migrations
	@echo "$(BLUE)Creating migrations...$(NC)"
	uv run python manage.py makemigrations $(app)

migrations-dry: ## Show migrations that would be created
	@echo "$(BLUE)Showing pending migrations...$(NC)"
	uv run python manage.py makemigrations --dry-run

showmigrations: ## Show all migrations and their status
	@echo "$(BLUE)Showing migrations...$(NC)"
	uv run python manage.py showmigrations

seed: ## Seed database with sample data
	@echo "$(BLUE)Seeding database...$(NC)"
	uv run python manage.py seed_data

seed-full: ## Seed database with full sample data
	@echo "$(BLUE)Seeding database with full data...$(NC)"
	uv run python manage.py seed_data --full

db-reset: ## Reset database (WARNING: destroys all data)
	@echo "$(RED)Resetting database...$(NC)"
	@read -p "Are you sure? This will destroy all data! [y/N] " confirm && [ "$$confirm" = "y" ]
	uv run python manage.py flush --no-input
	uv run python manage.py migrate
	@echo "$(GREEN)Database reset complete$(NC)"

db-create: ## Create database (PostgreSQL)
	@echo "$(BLUE)Creating database...$(NC)"
	createdb -h localhost -U postgres saas_starter || true

db-drop: ## Drop database (PostgreSQL)
	@echo "$(RED)Dropping database...$(NC)"
	dropdb -h localhost -U postgres saas_starter || true

# =============================================================================
# Testing
# =============================================================================

test: ## Run all tests
	@echo "$(BLUE)Running tests...$(NC)"
	uv run pytest

test-v: ## Run tests with verbose output
	@echo "$(BLUE)Running tests (verbose)...$(NC)"
	uv run pytest -v

test-cov: ## Run tests with coverage report
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	uv run pytest --cov --cov-report=html --cov-report=term

test-fast: ## Run tests in parallel
	@echo "$(BLUE)Running tests in parallel...$(NC)"
	uv run pytest -n auto

test-watch: ## Run tests and watch for changes
	@echo "$(BLUE)Running tests in watch mode...$(NC)"
	uv run ptw -- --testmon

test-file: ## Run specific test file (usage: make test-file file=tests/test_auth.py)
	@echo "$(BLUE)Running tests for $(file)...$(NC)"
	uv run pytest $(file) -v

test-func: ## Run specific test function (usage: make test-func func=test_login)
	@echo "$(BLUE)Running test $(func)...$(NC)"
	uv run pytest -k $(func) -v

# =============================================================================
# Code Quality
# =============================================================================

lint: ## Run linter (ruff)
	@echo "$(BLUE)Running linter...$(NC)"
	uv run ruff check .

lint-fix: ## Run linter and fix issues
	@echo "$(BLUE)Running linter with fixes...$(NC)"
	uv run ruff check --fix .

format: ## Format code with ruff
	@echo "$(BLUE)Formatting code...$(NC)"
	uv run ruff format .

format-check: ## Check code formatting
	@echo "$(BLUE)Checking formatting...$(NC)"
	uv run ruff format --check .

typecheck: ## Run type checker (mypy)
	@echo "$(BLUE)Running type checker...$(NC)"
	uv run mypy .

check: lint format-check typecheck ## Run all code quality checks
	@echo "$(GREEN)All checks passed!$(NC)"

# =============================================================================
# Docker
# =============================================================================

docker-build: ## Build Docker images
	@echo "$(BLUE)Building Docker images...$(NC)"
	docker compose build

docker-up: ## Start all services with Docker Compose
	@echo "$(BLUE)Starting services...$(NC)"
	docker compose up -d

docker-up-build: ## Build and start all services
	@echo "$(BLUE)Building and starting services...$(NC)"
	docker compose up -d --build

docker-down: ## Stop all services
	@echo "$(BLUE)Stopping services...$(NC)"
	docker compose down

docker-down-v: ## Stop all services and remove volumes
	@echo "$(RED)Stopping services and removing volumes...$(NC)"
	docker compose down -v

docker-logs: ## View logs from all services
	@echo "$(BLUE)Showing logs...$(NC)"
	docker compose logs -f

docker-logs-app: ## View logs from app service
	@echo "$(BLUE)Showing app logs...$(NC)"
	docker compose logs -f app

docker-logs-celery: ## View logs from Celery worker
	@echo "$(BLUE)Showing Celery logs...$(NC)"
	docker compose logs -f celery

docker-ps: ## Show running containers
	@echo "$(BLUE)Running containers:$(NC)"
	docker compose ps

docker-exec: ## Execute command in app container (usage: make docker-exec cmd="python manage.py shell")
	@echo "$(BLUE)Executing command...$(NC)"
	docker compose exec app $(cmd)

docker-shell: ## Open shell in app container
	@echo "$(BLUE)Opening shell...$(NC)"
	docker compose exec app /bin/bash

docker-migrate: ## Run migrations in Docker
	@echo "$(BLUE)Running migrations in Docker...$(NC)"
	docker compose exec app uv run python manage.py migrate

docker-seed: ## Seed database in Docker
	@echo "$(BLUE)Seeding database in Docker...$(NC)"
	docker compose exec app uv run python manage.py seed_data

# =============================================================================
# Background Tasks (Celery)
# =============================================================================

celery: ## Start Celery worker
	@echo "$(BLUE)Starting Celery worker...$(NC)"
	uv run celery -A saas_project worker -l INFO

celery-beat: ## Start Celery beat scheduler
	@echo "$(BLUE)Starting Celery beat...$(NC)"
	uv run celery -A saas_project beat -l INFO

celery-flower: ## Start Flower monitoring (requires flower)
	@echo "$(BLUE)Starting Flower...$(NC)"
	uv run celery -A saas_project flower --port=5555

celery-purge: ## Purge all Celery tasks
	@echo "$(RED)Purging all Celery tasks...$(NC)"
	uv run celery -A saas_project purge -f

# =============================================================================
# Utilities
# =============================================================================

types: ## Generate TypeScript types from schemas
	@echo "$(BLUE)Generating TypeScript types...$(NC)"
	uv run python manage.py sync_types --target typescript --output ./frontend/types

types-swift: ## Generate Swift types from schemas
	@echo "$(BLUE)Generating Swift types...$(NC)"
	uv run python manage.py sync_types --target swift --output ./ios/Types

openapi: ## Generate OpenAPI schema
	@echo "$(BLUE)Generating OpenAPI schema...$(NC)"
	uv run python manage.py generate_openapi --output openapi.json

openapi-yaml: ## Generate OpenAPI schema as YAML
	@echo "$(BLUE)Generating OpenAPI schema (YAML)...$(NC)"
	uv run python manage.py generate_openapi --output openapi.yaml --format yaml

superuser: ## Create superuser
	@echo "$(BLUE)Creating superuser...$(NC)"
	uv run python manage.py createsuperuser

collectstatic: ## Collect static files
	@echo "$(BLUE)Collecting static files...$(NC)"
	uv run python manage.py collectstatic --no-input

clean: ## Clean up generated files
	@echo "$(BLUE)Cleaning up...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	@echo "$(GREEN)Cleanup complete$(NC)"

clean-all: clean ## Clean everything including venv
	@echo "$(BLUE)Removing virtual environment...$(NC)"
	rm -rf .venv

# =============================================================================
# Feature Flags
# =============================================================================

flags-list: ## List all feature flags
	@echo "$(BLUE)Listing feature flags...$(NC)"
	uv run python manage.py list_flags

flags-enable: ## Enable a feature flag (usage: make flags-enable flag=my_feature)
	@echo "$(BLUE)Enabling flag $(flag)...$(NC)"
	uv run python manage.py enable_flag $(flag)

flags-disable: ## Disable a feature flag (usage: make flags-disable flag=my_feature)
	@echo "$(BLUE)Disabling flag $(flag)...$(NC)"
	uv run python manage.py disable_flag $(flag)

# =============================================================================
# Production
# =============================================================================

prod-check: ## Run Django deployment checks
	@echo "$(BLUE)Running deployment checks...$(NC)"
	uv run python manage.py check --deploy

prod-migrate: ## Run migrations in production (with backup)
	@echo "$(BLUE)Running production migrations...$(NC)"
	@read -p "Have you backed up the database? [y/N] " confirm && [ "$$confirm" = "y" ]
	uv run python manage.py migrate --plan
	@read -p "Continue with migration? [y/N] " confirm && [ "$$confirm" = "y" ]
	uv run python manage.py migrate

gunicorn: ## Start production server with Gunicorn
	@echo "$(BLUE)Starting Gunicorn...$(NC)"
	uv run gunicorn saas_project.asgi:application -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --workers 4

# =============================================================================
# Inspector & Debugging
# =============================================================================

routes: ## List all API routes
	@echo "$(BLUE)Listing API routes...$(NC)"
	uv run python manage.py show_urls

sql: ## Show SQL for a migration (usage: make sql app=core migration=0001)
	@echo "$(BLUE)Showing SQL for $(app) $(migration)...$(NC)"
	uv run python manage.py sqlmigrate $(app) $(migration)

# =============================================================================
# Quick Start
# =============================================================================

setup: install migrate seed ## Quick setup: install, migrate, and seed
	@echo "$(GREEN)Setup complete! Run 'make dev' to start the server.$(NC)"

reset: clean db-reset migrate seed ## Reset everything and start fresh
	@echo "$(GREEN)Reset complete! Run 'make dev' to start the server.$(NC)"
