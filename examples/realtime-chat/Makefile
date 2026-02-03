.PHONY: install dev migrate makemigrations test shell createsuperuser collectstatic run-daphne run-uvicorn docker-up docker-down clean

# Package management
install:
	uv sync

# Development server
dev:
	uv run python manage.py runserver

# Run with Daphne (ASGI server, supports WebSockets)
run-daphne:
	uv run daphne -p 8000 config.asgi:application

# Run with Uvicorn (ASGI server, supports WebSockets)
run-uvicorn:
	uv run uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --reload

# Database migrations
migrate:
	uv run python manage.py migrate

makemigrations:
	uv run python manage.py makemigrations

# Testing
test:
	uv run pytest

test-v:
	uv run pytest -v

# Django management
shell:
	uv run python manage.py shell

createsuperuser:
	uv run python manage.py createsuperuser

collectstatic:
	uv run python manage.py collectstatic --noinput

# Docker services (Redis & PostgreSQL)
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

# Clean up
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete

# Setup (run after cloning)
setup: install docker-up migrate
	@echo "Setup complete! Run 'make dev' or 'make run-daphne' to start the server."
