.PHONY: help install dev run test lint format migrate seed docker-up docker-down

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	uv pip install -e .

dev: ## Install with dev dependencies
	uv pip install -e ".[dev]"

run: ## Start development server
	uv run python manage.py runserver

test: ## Run tests
	uv run pytest tests/ --cov=apps -q

lint: ## Run linter
	uv run ruff check .

format: ## Format code
	uv run ruff format . && uv run ruff check --fix .

migrate: ## Run migrations
	uv run python manage.py makemigrations && uv run python manage.py migrate

seed: ## Seed sample data
	uv run python manage.py seed_data

docker-up: ## Start database services
	docker compose up -d db redis

docker-down: ## Stop all services
	docker compose down

docker-up-all: ## Start all services including API
	docker compose up -d
