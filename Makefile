# Django Matt - Development Commands
# ===================================
# Run `make` or `make help` to see all available commands

.PHONY: help install dev test lint format check clean docs serve build \
        shell routes models migrate makemigrations crud admin \
        docker-build docker-up docker-down docker-logs \
        release version

# Colors for terminal output
BLUE := \033[34m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
CYAN := \033[36m
MAGENTA := \033[35m
BOLD := \033[1m
RESET := \033[0m

# Default target
.DEFAULT_GOAL := help

# ============================================================================
# HELP
# ============================================================================

help: ## Show this help message
	@echo ""
	@echo "$(BOLD)$(MAGENTA)  Django Matt $(RESET)$(BOLD)- Development Commands$(RESET)"
	@echo ""
	@echo "$(CYAN)  Usage:$(RESET) make $(GREEN)<command>$(RESET)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; section=""} \
		/^## / { section=substr($$0, 4); printf "\n$(BOLD)$(YELLOW)  %s$(RESET)\n", section } \
		/^[a-zA-Z_-]+:.*?##/ { printf "    $(GREEN)%-16s$(RESET) %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""

# ============================================================================
## Setup & Installation
# ============================================================================

install: ## Install all dependencies
	@echo "$(CYAN)Installing dependencies...$(RESET)"
	uv sync --all-extras
	@echo "$(GREEN)Done!$(RESET)"

install-dev: ## Install with development dependencies
	@echo "$(CYAN)Installing dev dependencies...$(RESET)"
	uv sync --all-extras --dev
	@echo "$(GREEN)Done!$(RESET)"

upgrade: ## Upgrade all dependencies
	@echo "$(CYAN)Upgrading dependencies...$(RESET)"
	uv lock --upgrade
	uv sync --all-extras
	@echo "$(GREEN)Done!$(RESET)"

# ============================================================================
## Development
# ============================================================================

dev: ## Start development server with hot reload
	@echo "$(CYAN)Starting development server...$(RESET)"
	uv run python manage.py runserver

dev-no-hot: ## Start development server without hot reload
	uv run python manage.py runserver --no-hot

shell: ## Open Django shell with auto-imports
	@echo "$(CYAN)Opening Django shell...$(RESET)"
	uv run python manage.py shell

dbshell: ## Open database shell
	uv run python manage.py dbshell

routes: ## List all API routes
	@echo "$(CYAN)API Routes:$(RESET)"
	@uv run python manage.py matt routes 2>/dev/null || echo "$(YELLOW)Command not yet implemented$(RESET)"

models: ## List all models
	@echo "$(CYAN)Models:$(RESET)"
	@uv run python manage.py matt models 2>/dev/null || echo "$(YELLOW)Command not yet implemented$(RESET)"

info: ## Show project info
	@uv run python manage.py matt info 2>/dev/null || echo "$(YELLOW)Command not yet implemented$(RESET)"

doctor: ## Check project health
	@uv run python manage.py matt doctor 2>/dev/null || echo "$(YELLOW)Command not yet implemented$(RESET)"

# ============================================================================
## Database
# ============================================================================

migrate: ## Run database migrations
	@echo "$(CYAN)Running migrations...$(RESET)"
	uv run python manage.py migrate
	@echo "$(GREEN)Done!$(RESET)"

makemigrations: ## Create new migrations
	@echo "$(CYAN)Creating migrations...$(RESET)"
	uv run python manage.py makemigrations
	@echo "$(GREEN)Done!$(RESET)"

migrations: makemigrations migrate ## Create and run migrations

resetdb: ## Reset database (WARNING: destroys data)
	@echo "$(RED)$(BOLD)WARNING: This will destroy all data!$(RESET)"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	uv run python manage.py flush --no-input
	@echo "$(GREEN)Database reset!$(RESET)"

# ============================================================================
## Code Quality
# ============================================================================

lint: ## Run linter (ruff check)
	@echo "$(CYAN)Running linter...$(RESET)"
	uv run ruff check .
	@echo "$(GREEN)Lint passed!$(RESET)"

lint-fix: ## Run linter with auto-fix
	@echo "$(CYAN)Running linter with fixes...$(RESET)"
	uv run ruff check . --fix
	@echo "$(GREEN)Done!$(RESET)"

format: ## Format code (ruff format)
	@echo "$(CYAN)Formatting code...$(RESET)"
	uv run ruff format .
	@echo "$(GREEN)Done!$(RESET)"

typecheck: ## Run type checker (pyright)
	@echo "$(CYAN)Running type checker...$(RESET)"
	uv run pyright django_matt
	@echo "$(GREEN)Type check passed!$(RESET)"

check: lint typecheck ## Run all code quality checks
	@echo "$(GREEN)$(BOLD)All checks passed!$(RESET)"

fix: lint-fix format ## Fix all auto-fixable issues
	@echo "$(GREEN)$(BOLD)All fixes applied!$(RESET)"

# ============================================================================
## Testing
# ============================================================================

test: ## Run all tests
	@echo "$(CYAN)Running tests...$(RESET)"
	uv run pytest tests/ -v
	@echo "$(GREEN)Tests passed!$(RESET)"

test-fast: ## Run tests without slow tests
	@echo "$(CYAN)Running fast tests...$(RESET)"
	uv run pytest tests/ -v -m "not slow"

test-cov: ## Run tests with coverage
	@echo "$(CYAN)Running tests with coverage...$(RESET)"
	uv run pytest tests/ -v --cov=django_matt --cov-report=html --cov-report=term
	@echo "$(GREEN)Coverage report: htmlcov/index.html$(RESET)"

test-watch: ## Run tests in watch mode
	@echo "$(CYAN)Running tests in watch mode...$(RESET)"
	uv run pytest-watch tests/ -- -v

# ============================================================================
## Code Generation
# ============================================================================

crud: ## Generate CRUD for a model (usage: make crud MODEL=app.Model)
	@if [ -z "$(MODEL)" ]; then \
		echo "$(RED)Error: MODEL is required$(RESET)"; \
		echo "Usage: make crud MODEL=myapp.MyModel"; \
		exit 1; \
	fi
	@echo "$(CYAN)Generating CRUD for $(MODEL)...$(RESET)"
	uv run python manage.py generate_crud $(MODEL)
	@echo "$(GREEN)Done!$(RESET)"

crud-full: ## Generate full CRUD with admin and tests (usage: make crud-full MODEL=app.Model)
	@if [ -z "$(MODEL)" ]; then \
		echo "$(RED)Error: MODEL is required$(RESET)"; \
		echo "Usage: make crud-full MODEL=myapp.MyModel"; \
		exit 1; \
	fi
	@echo "$(CYAN)Generating full CRUD for $(MODEL)...$(RESET)"
	uv run python manage.py generate_crud $(MODEL) --full
	@echo "$(GREEN)Done!$(RESET)"

admin: ## Generate admin for a model (usage: make admin MODEL=app.Model)
	@if [ -z "$(MODEL)" ]; then \
		echo "$(RED)Error: MODEL is required$(RESET)"; \
		echo "Usage: make admin MODEL=myapp.MyModel"; \
		exit 1; \
	fi
	@echo "$(CYAN)Generating admin for $(MODEL)...$(RESET)"
	uv run python manage.py generate_crud $(MODEL) --no-service --with-admin
	@echo "$(GREEN)Done!$(RESET)"

types: ## Generate TypeScript types
	@echo "$(CYAN)Generating TypeScript types...$(RESET)"
	uv run python manage.py sync_types --target typescript --output frontend/src/types
	@echo "$(GREEN)Done!$(RESET)"

types-watch: ## Watch and generate TypeScript types
	@echo "$(CYAN)Watching for type changes...$(RESET)"
	uv run python manage.py sync_types --target typescript --output frontend/src/types --watch

# ============================================================================
## Documentation
# ============================================================================

docs: ## Build documentation
	@echo "$(CYAN)Building documentation...$(RESET)"
	uv run mkdocs build
	@echo "$(GREEN)Done! Output: site/$(RESET)"

docs-serve: ## Serve documentation locally
	@echo "$(CYAN)Serving documentation at http://localhost:8001$(RESET)"
	uv run mkdocs serve -a localhost:8001

docs-deploy: ## Deploy documentation to GitHub Pages
	@echo "$(CYAN)Deploying documentation...$(RESET)"
	uv run mkdocs gh-deploy
	@echo "$(GREEN)Done!$(RESET)"

# ============================================================================
## Docker
# ============================================================================

docker-build: ## Build Docker images
	@echo "$(CYAN)Building Docker images...$(RESET)"
	docker compose build
	@echo "$(GREEN)Done!$(RESET)"

docker-up: ## Start Docker containers
	@echo "$(CYAN)Starting containers...$(RESET)"
	docker compose up -d
	@echo "$(GREEN)Containers started!$(RESET)"

docker-down: ## Stop Docker containers
	@echo "$(CYAN)Stopping containers...$(RESET)"
	docker compose down
	@echo "$(GREEN)Containers stopped!$(RESET)"

docker-logs: ## Show Docker logs
	docker compose logs -f

docker-shell: ## Open shell in web container
	docker compose exec web bash

docker-dev: docker-build docker-up ## Build and start Docker containers
	@echo "$(GREEN)$(BOLD)Docker dev environment ready!$(RESET)"

# ============================================================================
## Release & Publishing
# ============================================================================

version: ## Show current version
	@uv run python -c "import django_matt; print(django_matt.__version__)" 2>/dev/null || echo "0.1.0"

build: ## Build package
	@echo "$(CYAN)Building package...$(RESET)"
	uv build
	@echo "$(GREEN)Done! Output: dist/$(RESET)"

publish-test: build ## Publish to TestPyPI
	@echo "$(CYAN)Publishing to TestPyPI...$(RESET)"
	uv publish --repository testpypi
	@echo "$(GREEN)Done!$(RESET)"

publish: build ## Publish to PyPI
	@echo "$(RED)$(BOLD)Publishing to PyPI...$(RESET)"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	uv publish
	@echo "$(GREEN)Done!$(RESET)"

# ============================================================================
## Cleanup
# ============================================================================

clean: ## Remove build artifacts and caches
	@echo "$(CYAN)Cleaning up...$(RESET)"
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	rm -rf site/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)Cleaned!$(RESET)"

clean-all: clean ## Remove all generated files including .venv
	@echo "$(RED)$(BOLD)Removing virtual environment...$(RESET)"
	rm -rf .venv/
	@echo "$(GREEN)Done!$(RESET)"

# ============================================================================
## CI/CD Helpers
# ============================================================================

ci: install lint typecheck test ## Run full CI pipeline locally
	@echo "$(GREEN)$(BOLD)CI pipeline passed!$(RESET)"

pre-commit: fix test ## Run before committing (fix + test)
	@echo "$(GREEN)$(BOLD)Ready to commit!$(RESET)"
