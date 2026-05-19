.PHONY: help install dev run migrate makemigrations superuser seed shell test lint format docker-up docker-down clean

help:
	@echo "Blog API — Available commands:"
	@echo ""
	@echo "Development:"
	@echo "  make install        Install dependencies with uv"
	@echo "  make dev            Run development server (localhost:8000)"
	@echo "  make shell          Open Django shell"
	@echo "  make superuser      Create superuser"
	@echo ""
	@echo "Database:"
	@echo "  make migrate        Run migrations"
	@echo "  make makemigrations Create new migrations"
	@echo "  make seed           Seed sample data"
	@echo ""
	@echo "Testing:"
	@echo "  make test           Run test suite"
	@echo "  make test-cov       Run tests with coverage report"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up      Start PostgreSQL + web"
	@echo "  make docker-down    Stop all containers"
	@echo ""
	@echo "Code quality:"
	@echo "  make lint           Run ruff"
	@echo "  make format         Auto-format with ruff"

install:
	uv sync

dev:
	uv run python manage.py runserver 0.0.0.0:8000

run:
	uv run uvicorn config.asgi:application --host 0.0.0.0 --port 8000

migrate:
	uv run python manage.py migrate

makemigrations:
	uv run python manage.py makemigrations

superuser:
	uv run python manage.py createsuperuser

seed:
	uv run python manage.py seed_blog

shell:
	uv run python manage.py shell

test:
	uv run pytest tests/ -v

test-cov:
	uv run pytest tests/ --cov=blog --cov-report=html --cov-report=term

lint:
	uv run ruff check .

format:
	uv run ruff format .
	uv run ruff check --fix .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-build:
	docker-compose build

docker-logs:
	docker-compose logs -f

setup: install migrate seed
	@echo "Setup complete. Run 'make dev' to start the server."

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage staticfiles 2>/dev/null || true
