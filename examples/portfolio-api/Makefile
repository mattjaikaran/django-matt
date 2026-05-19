.PHONY: help install dev run test lint format migrate seed docker-up docker-down shell

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	uv sync

dev: ## Install with dev dependencies
	uv sync --extra dev

run: ## Start development server
	uv run python manage.py runserver 0.0.0.0:8000

test: ## Run tests
	uv run pytest tests/ -x -q

lint: ## Run linter
	uv run ruff check apps/

format: ## Format code
	uv run ruff format apps/ && uv run ruff check --fix apps/

migrate: ## Make and run migrations
	uv run python manage.py makemigrations && uv run python manage.py migrate

seed: ## Seed sample data
	uv run python scripts/seed.py

docker-up: ## Start database service
	docker compose up -d db

docker-down: ## Stop all services
	docker compose down

docker-up-all: ## Start all services including API
	docker compose up -d

shell: ## Open Django shell
	uv run python manage.py shell
