.PHONY: help install dev run migrate makemigrations seed shell test lint format docker-up docker-down docker-build celery beat stripe-listen clean

# Default target
help:
	@echo "E-Commerce API - Available commands:"
	@echo ""
	@echo "Development:"
	@echo "  make install      - Install dependencies with uv"
	@echo "  make dev          - Run development server"
	@echo "  make run          - Run production server"
	@echo "  make shell        - Open Django shell"
	@echo "  make test         - Run tests"
	@echo ""
	@echo "Database:"
	@echo "  make migrate      - Run migrations"
	@echo "  make makemigrations - Create migrations"
	@echo "  make seed         - Seed database with sample data"
	@echo "  make seed-clear   - Clear and reseed database"
	@echo ""
	@echo "Background tasks:"
	@echo "  make celery       - Start Celery worker"
	@echo "  make beat         - Start Celery beat scheduler"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up    - Start all services"
	@echo "  make docker-down  - Stop all services"
	@echo "  make docker-build - Build Docker images"
	@echo "  make docker-logs  - View logs"
	@echo ""
	@echo "Stripe:"
	@echo "  make stripe-listen - Start Stripe webhook listener"
	@echo ""
	@echo "Code quality:"
	@echo "  make lint         - Run linter"
	@echo "  make format       - Format code"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean        - Clean up generated files"

# Install dependencies using uv
install:
	uv sync

# Development server
dev:
	uv run python manage.py runserver 0.0.0.0:8000

# Production server
run:
	uv run uvicorn config.asgi:application --host 0.0.0.0 --port 8000

# Migrations
migrate:
	uv run python manage.py migrate

makemigrations:
	uv run python manage.py makemigrations

# Seed data
seed:
	uv run python manage.py seed_data

seed-clear:
	uv run python manage.py seed_data --clear

# Shell
shell:
	uv run python manage.py shell_plus

# Tests
test:
	uv run pytest tests/ -v

test-cov:
	uv run pytest tests/ --cov=ecommerce --cov-report=html

# Linting
lint:
	uv run ruff check .

format:
	uv run ruff format .
	uv run ruff check --fix .

# Docker commands
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-build:
	docker-compose build

docker-logs:
	docker-compose logs -f

docker-shell:
	docker-compose exec web bash

# Celery
celery:
	uv run celery -A config worker -l INFO

beat:
	uv run celery -A config beat -l INFO

# Stripe webhook listener (requires Stripe CLI)
stripe-listen:
	stripe listen --forward-to localhost:8000/api/payments/webhooks/stripe/

# Superuser
superuser:
	uv run python manage.py createsuperuser

# Static files
collectstatic:
	uv run python manage.py collectstatic --noinput

# Clean up
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage 2>/dev/null || true
	rm -rf staticfiles 2>/dev/null || true
	rm -rf .venv 2>/dev/null || true

# Initial setup
setup: install migrate seed
	@echo "Setup complete! Run 'make dev' to start the server."

# Full Docker setup
docker-setup: docker-build docker-up
	docker-compose exec web uv run python manage.py migrate
	docker-compose exec web uv run python manage.py seed_data
	@echo "Docker setup complete!"
