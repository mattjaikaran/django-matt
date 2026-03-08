# Django Matt - Development Commands
# ===================================
# Run `make` or `make help` to see all available commands
#
# Commands with arguments:
#   make startapp NAME=myapp        - Create a new Django app
#   make startproject NAME=myproj   - Create a new Django Matt project
#   make crud MODEL=myapp.MyModel   - Generate CRUD for a model
#   make test FILE=test_auth.py     - Run specific test file
#   make migrate APP=myapp          - Migrate specific app
#
# Consolidated commands (accept multiple args):
#   make run                        - Start dev server (default)
#   make run MODE=shell             - Open Django shell
#   make run MODE=test              - Run tests
#   make run PORT=8080              - Start dev server on port 8080
#
#   make db                         - Run migrations (default)
#   make db OP=make                 - Create migrations
#   make db OP=show                 - Show migration status
#   make db OP=reset                - Reset database
#   make db APP=myapp               - Migrate specific app
#
#   make gen TYPE=crud MODEL=...    - Generate CRUD
#   make gen TYPE=types             - Generate TypeScript types
#   make gen TYPE=swift             - Generate Swift types
#   make gen TYPE=zod               - Generate Zod schemas
#
#   make quality                    - Run all checks (lint + typecheck + test)
#   make quality OP=fix             - Auto-fix issues
#   make quality OP=lint            - Just lint
#   make quality OP=format          - Just format

.PHONY: help install dev test lint format check clean docs serve build \
        shell routes models migrate makemigrations crud admin \
        docker-build docker-up docker-down docker-logs \
        release version startapp startproject startapi \
        run db gen quality setup

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
	@uv run python manage.py matt routes

models: ## List all models
	@echo "$(CYAN)Models:$(RESET)"
	@uv run python manage.py matt models

info: ## Show project info
	@uv run python manage.py matt info

doctor: ## Check project health
	@uv run python manage.py matt doctor

# ============================================================================
## Database
# ============================================================================

migrate: ## Run migrations (usage: make migrate [APP=myapp])
	@echo "$(CYAN)Running migrations...$(RESET)"
	@if [ -n "$(APP)" ]; then \
		uv run python manage.py migrate $(APP); \
	else \
		uv run python manage.py migrate; \
	fi
	@echo "$(GREEN)Done!$(RESET)"

makemigrations: ## Create migrations (usage: make makemigrations [APP=myapp])
	@echo "$(CYAN)Creating migrations...$(RESET)"
	@if [ -n "$(APP)" ]; then \
		uv run python manage.py makemigrations $(APP); \
	else \
		uv run python manage.py makemigrations; \
	fi
	@echo "$(GREEN)Done!$(RESET)"

migrations: makemigrations migrate ## Create and run migrations

showmigrations: ## Show migration status
	@echo "$(CYAN)Migration status:$(RESET)"
	uv run python manage.py showmigrations

resetdb: ## Reset database (WARNING: destroys data)
	@echo "$(RED)$(BOLD)WARNING: This will destroy all data!$(RESET)"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	uv run python manage.py flush --no-input
	@echo "$(GREEN)Database reset!$(RESET)"

superuser: ## Create a superuser (usage: make superuser [EMAIL=admin@example.com])
	@echo "$(CYAN)Creating superuser...$(RESET)"
	@if [ -n "$(EMAIL)" ]; then \
		uv run python manage.py createsuperuser --email $(EMAIL); \
	else \
		uv run python manage.py createsuperuser; \
	fi

seed: ## Seed database with sample data
	@echo "$(CYAN)Seeding database...$(RESET)"
	@uv run python manage.py seed 2>/dev/null || echo "$(YELLOW)Seed command not configured$(RESET)"

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

test: ## Run tests (usage: make test [FILE=test_auth.py] [ARGS="-k test_login"])
	@echo "$(CYAN)Running tests...$(RESET)"
	@if [ -n "$(FILE)" ]; then \
		uv run pytest tests/$(FILE) -v $(ARGS); \
	else \
		uv run pytest tests/ -v $(ARGS); \
	fi
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

test-file: ## Run a specific test file (usage: make test-file FILE=test_auth.py)
	@if [ -z "$(FILE)" ]; then \
		echo "$(RED)Error: FILE is required$(RESET)"; \
		echo "Usage: make test-file FILE=test_auth.py"; \
		exit 1; \
	fi
	@echo "$(CYAN)Running tests in $(FILE)...$(RESET)"
	uv run pytest tests/$(FILE) -v

# ============================================================================
## Scaffolding
# ============================================================================

startapp: ## Create a new Django app (usage: make startapp NAME=myapp [MODELS="Post Comment"])
	@if [ -z "$(NAME)" ]; then \
		echo "$(RED)Error: NAME is required$(RESET)"; \
		echo "Usage: make startapp NAME=myapp"; \
		echo "Usage: make startapp NAME=blog MODELS=\"Post Comment\""; \
		exit 1; \
	fi
	@echo "$(CYAN)Creating app '$(NAME)'...$(RESET)"
	@uv run python manage.py startapp $(NAME) $(if $(MODELS),--models $(MODELS),)
	@echo "$(GREEN)App '$(NAME)' created!$(RESET)"

startproject: ## Create a new Django Matt project (usage: make startproject NAME=myproject)
	@if [ -z "$(NAME)" ]; then \
		echo "$(RED)Error: NAME is required$(RESET)"; \
		echo "Usage: make startproject NAME=myproject"; \
		exit 1; \
	fi
	@echo "$(CYAN)Creating project '$(NAME)'...$(RESET)"
	@uv run python manage.py startapi $(NAME) $(if $(TEMPLATE),--template $(TEMPLATE),)
	@echo "$(GREEN)Project '$(NAME)' created!$(RESET)"

startapi: startproject ## Alias for startproject

newapp: startapp ## Alias for startapp

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

types: ## Generate TypeScript types (usage: make types [OUTPUT=frontend/src/types])
	@echo "$(CYAN)Generating TypeScript types...$(RESET)"
	uv run python manage.py sync_types --target typescript --output $(or $(OUTPUT),frontend/src/types)
	@echo "$(GREEN)Done!$(RESET)"

types-swift: ## Generate Swift types (usage: make types-swift [OUTPUT=ios/Models])
	@echo "$(CYAN)Generating Swift types...$(RESET)"
	uv run python manage.py sync_types --target swift --output $(or $(OUTPUT),ios/Models)
	@echo "$(GREEN)Done!$(RESET)"

types-zod: ## Generate Zod schemas (usage: make types-zod [OUTPUT=frontend/src/schemas])
	@echo "$(CYAN)Generating Zod schemas...$(RESET)"
	uv run python manage.py sync_types --target typescript --zod --output $(or $(OUTPUT),frontend/src/schemas)
	@echo "$(GREEN)Done!$(RESET)"

types-watch: ## Watch and generate TypeScript types
	@echo "$(CYAN)Watching for type changes...$(RESET)"
	uv run python manage.py sync_types --target typescript --output $(or $(OUTPUT),frontend/src/types) --watch

schema: ## Generate model schema (usage: make schema MODEL=myapp.MyModel)
	@if [ -z "$(MODEL)" ]; then \
		echo "$(RED)Error: MODEL is required$(RESET)"; \
		echo "Usage: make schema MODEL=myapp.MyModel"; \
		exit 1; \
	fi
	@echo "$(CYAN)Generating schema for $(MODEL)...$(RESET)"
	uv run python -c "from django_matt.core.schema import create_schema_from_model; from $(shell echo $(MODEL) | cut -d. -f1).models import $(shell echo $(MODEL) | cut -d. -f2); print(create_schema_from_model($(shell echo $(MODEL) | cut -d. -f2)).schema_json(indent=2))"

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

# ============================================================================
## Consolidated Commands (Multi-purpose with arguments)
# ============================================================================

# Unified run command: make run [MODE=dev|shell|dbshell|test] [PORT=8000] [ARGS=...]
run: ## Unified run command (MODE=dev|shell|dbshell|test, PORT=8000)
	@if [ "$(MODE)" = "shell" ]; then \
		echo "$(CYAN)Opening Django shell...$(RESET)"; \
		uv run python manage.py shell $(ARGS); \
	elif [ "$(MODE)" = "dbshell" ]; then \
		echo "$(CYAN)Opening database shell...$(RESET)"; \
		uv run python manage.py dbshell; \
	elif [ "$(MODE)" = "test" ]; then \
		echo "$(CYAN)Running tests...$(RESET)"; \
		if [ -n "$(FILE)" ]; then \
			uv run pytest tests/$(FILE) -v $(ARGS); \
		else \
			uv run pytest tests/ -v $(ARGS); \
		fi; \
	elif [ "$(MODE)" = "docs" ]; then \
		echo "$(CYAN)Serving documentation...$(RESET)"; \
		uv run mkdocs serve -a localhost:$(or $(PORT),8001); \
	else \
		echo "$(CYAN)Starting development server on port $(or $(PORT),8000)...$(RESET)"; \
		if [ "$(HOT)" = "false" ]; then \
			uv run python manage.py runserver $(or $(PORT),8000) --no-hot $(ARGS); \
		else \
			uv run python manage.py runserver $(or $(PORT),8000) $(ARGS); \
		fi; \
	fi

# Unified database command: make db [OP=migrate|make|show|reset|seed|super] [APP=myapp]
db: ## Unified database command (OP=migrate|make|show|reset|seed|super)
	@if [ "$(OP)" = "make" ]; then \
		echo "$(CYAN)Creating migrations...$(RESET)"; \
		if [ -n "$(APP)" ]; then \
			uv run python manage.py makemigrations $(APP) $(ARGS); \
		else \
			uv run python manage.py makemigrations $(ARGS); \
		fi; \
	elif [ "$(OP)" = "show" ]; then \
		echo "$(CYAN)Migration status:$(RESET)"; \
		uv run python manage.py showmigrations $(APP); \
	elif [ "$(OP)" = "reset" ]; then \
		echo "$(RED)$(BOLD)WARNING: This will destroy all data!$(RESET)"; \
		read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1; \
		uv run python manage.py flush --no-input; \
		echo "$(GREEN)Database reset!$(RESET)"; \
	elif [ "$(OP)" = "seed" ]; then \
		echo "$(CYAN)Seeding database...$(RESET)"; \
		uv run python manage.py seed $(ARGS) 2>/dev/null || echo "$(YELLOW)Seed command not configured$(RESET)"; \
	elif [ "$(OP)" = "super" ]; then \
		echo "$(CYAN)Creating superuser...$(RESET)"; \
		if [ -n "$(EMAIL)" ]; then \
			uv run python manage.py createsuperuser --email $(EMAIL); \
		else \
			uv run python manage.py createsuperuser; \
		fi; \
	elif [ "$(OP)" = "all" ]; then \
		echo "$(CYAN)Creating and running migrations...$(RESET)"; \
		if [ -n "$(APP)" ]; then \
			uv run python manage.py makemigrations $(APP) && uv run python manage.py migrate $(APP); \
		else \
			uv run python manage.py makemigrations && uv run python manage.py migrate; \
		fi; \
		echo "$(GREEN)Done!$(RESET)"; \
	else \
		echo "$(CYAN)Running migrations...$(RESET)"; \
		if [ -n "$(APP)" ]; then \
			uv run python manage.py migrate $(APP) $(ARGS); \
		else \
			uv run python manage.py migrate $(ARGS); \
		fi; \
		echo "$(GREEN)Done!$(RESET)"; \
	fi

# Unified generation command: make gen TYPE=crud|types|swift|zod|schema|admin [MODEL=...] [OUTPUT=...]
gen: ## Unified code generation (TYPE=crud|types|swift|zod|schema|admin)
	@if [ "$(TYPE)" = "crud" ]; then \
		if [ -z "$(MODEL)" ]; then \
			echo "$(RED)Error: MODEL is required for crud generation$(RESET)"; \
			echo "Usage: make gen TYPE=crud MODEL=myapp.MyModel"; \
			exit 1; \
		fi; \
		echo "$(CYAN)Generating CRUD for $(MODEL)...$(RESET)"; \
		if [ "$(FULL)" = "true" ]; then \
			uv run python manage.py generate_crud $(MODEL) --full $(ARGS); \
		else \
			uv run python manage.py generate_crud $(MODEL) $(ARGS); \
		fi; \
	elif [ "$(TYPE)" = "types" ] || [ "$(TYPE)" = "ts" ] || [ "$(TYPE)" = "typescript" ]; then \
		echo "$(CYAN)Generating TypeScript types...$(RESET)"; \
		if [ "$(WATCH)" = "true" ]; then \
			uv run python manage.py sync_types --target typescript --output $(or $(OUTPUT),frontend/src/types) --watch; \
		else \
			uv run python manage.py sync_types --target typescript --output $(or $(OUTPUT),frontend/src/types) $(ARGS); \
		fi; \
	elif [ "$(TYPE)" = "swift" ]; then \
		echo "$(CYAN)Generating Swift types...$(RESET)"; \
		uv run python manage.py sync_types --target swift --output $(or $(OUTPUT),ios/Models) $(ARGS); \
	elif [ "$(TYPE)" = "zod" ]; then \
		echo "$(CYAN)Generating Zod schemas...$(RESET)"; \
		uv run python manage.py sync_types --target typescript --zod --output $(or $(OUTPUT),frontend/src/schemas) $(ARGS); \
	elif [ "$(TYPE)" = "schema" ]; then \
		if [ -z "$(MODEL)" ]; then \
			echo "$(RED)Error: MODEL is required for schema generation$(RESET)"; \
			echo "Usage: make gen TYPE=schema MODEL=myapp.MyModel"; \
			exit 1; \
		fi; \
		echo "$(CYAN)Generating schema for $(MODEL)...$(RESET)"; \
		uv run python -c "from django_matt.core.schema import create_schema_from_model; from $(shell echo $(MODEL) | cut -d. -f1).models import $(shell echo $(MODEL) | cut -d. -f2); print(create_schema_from_model($(shell echo $(MODEL) | cut -d. -f2)).schema_json(indent=2))"; \
	elif [ "$(TYPE)" = "admin" ]; then \
		if [ -z "$(MODEL)" ]; then \
			echo "$(RED)Error: MODEL is required for admin generation$(RESET)"; \
			echo "Usage: make gen TYPE=admin MODEL=myapp.MyModel"; \
			exit 1; \
		fi; \
		echo "$(CYAN)Generating admin for $(MODEL)...$(RESET)"; \
		uv run python manage.py generate_crud $(MODEL) --no-service --with-admin $(ARGS); \
	else \
		echo "$(RED)Error: Unknown TYPE '$(TYPE)'$(RESET)"; \
		echo "Available: crud, types, swift, zod, schema, admin"; \
		exit 1; \
	fi
	@echo "$(GREEN)Done!$(RESET)"

# Unified quality command: make quality [OP=all|lint|format|typecheck|fix|test]
quality: ## Unified code quality (OP=all|lint|format|typecheck|fix|test)
	@if [ "$(OP)" = "lint" ]; then \
		echo "$(CYAN)Running linter...$(RESET)"; \
		uv run ruff check . $(ARGS); \
	elif [ "$(OP)" = "format" ]; then \
		echo "$(CYAN)Formatting code...$(RESET)"; \
		uv run ruff format . $(ARGS); \
	elif [ "$(OP)" = "typecheck" ]; then \
		echo "$(CYAN)Running type checker...$(RESET)"; \
		uv run pyright django_matt $(ARGS); \
	elif [ "$(OP)" = "fix" ]; then \
		echo "$(CYAN)Fixing issues...$(RESET)"; \
		uv run ruff check . --fix; \
		uv run ruff format .; \
		echo "$(GREEN)$(BOLD)All fixes applied!$(RESET)"; \
	elif [ "$(OP)" = "test" ]; then \
		echo "$(CYAN)Running tests...$(RESET)"; \
		if [ -n "$(FILE)" ]; then \
			uv run pytest tests/$(FILE) -v $(ARGS); \
		else \
			uv run pytest tests/ -v $(ARGS); \
		fi; \
	else \
		echo "$(CYAN)Running all quality checks...$(RESET)"; \
		uv run ruff check .; \
		uv run pyright django_matt; \
		uv run pytest tests/ -v; \
		echo "$(GREEN)$(BOLD)All checks passed!$(RESET)"; \
	fi

# Unified setup command: make setup [PROFILE=minimal|dev|full|docker]
setup: ## Project setup (PROFILE=minimal|dev|full|docker)
	@if [ "$(PROFILE)" = "minimal" ]; then \
		echo "$(CYAN)Minimal setup...$(RESET)"; \
		uv sync; \
	elif [ "$(PROFILE)" = "docker" ]; then \
		echo "$(CYAN)Docker setup...$(RESET)"; \
		docker compose build; \
		docker compose up -d; \
		echo "$(GREEN)Docker environment ready!$(RESET)"; \
	elif [ "$(PROFILE)" = "full" ]; then \
		echo "$(CYAN)Full setup (deps + migrations + superuser)...$(RESET)"; \
		uv sync --all-extras --dev; \
		uv run python manage.py migrate; \
		echo "$(YELLOW)Create superuser:$(RESET)"; \
		uv run python manage.py createsuperuser; \
		echo "$(GREEN)$(BOLD)Full setup complete!$(RESET)"; \
	else \
		echo "$(CYAN)Development setup...$(RESET)"; \
		uv sync --all-extras --dev; \
		uv run python manage.py migrate; \
		echo "$(GREEN)$(BOLD)Dev setup complete!$(RESET)"; \
	fi

# Unified docker command: make dk [OP=up|down|build|logs|shell|restart]
dk: ## Docker operations (OP=up|down|build|logs|shell|restart)
	@if [ "$(OP)" = "build" ]; then \
		echo "$(CYAN)Building Docker images...$(RESET)"; \
		docker compose build $(ARGS); \
	elif [ "$(OP)" = "down" ]; then \
		echo "$(CYAN)Stopping containers...$(RESET)"; \
		docker compose down $(ARGS); \
	elif [ "$(OP)" = "logs" ]; then \
		docker compose logs -f $(SERVICE); \
	elif [ "$(OP)" = "shell" ]; then \
		docker compose exec $(or $(SERVICE),web) bash; \
	elif [ "$(OP)" = "restart" ]; then \
		echo "$(CYAN)Restarting containers...$(RESET)"; \
		docker compose restart $(SERVICE); \
	elif [ "$(OP)" = "ps" ]; then \
		docker compose ps; \
	else \
		echo "$(CYAN)Starting containers...$(RESET)"; \
		docker compose up -d $(ARGS); \
		echo "$(GREEN)Containers started!$(RESET)"; \
	fi

# Quick shortcuts using consolidated commands
s: ## Shortcut: start dev server (alias for run)
	@$(MAKE) run PORT=$(PORT) ARGS="$(ARGS)"

t: ## Shortcut: run tests (alias for run MODE=test)
	@$(MAKE) run MODE=test FILE=$(FILE) ARGS="$(ARGS)"

m: ## Shortcut: run migrations (alias for db)
	@$(MAKE) db APP=$(APP)

mm: ## Shortcut: make migrations (alias for db OP=make)
	@$(MAKE) db OP=make APP=$(APP)

f: ## Shortcut: fix code (alias for quality OP=fix)
	@$(MAKE) quality OP=fix

# ============================================================================
## AI & Context Generation
# ============================================================================

ai-context: ## Generate AI IDE context files (CLAUDE.md, .cursorrules)
	@echo "$(CYAN)Generating AI context files...$(RESET)"
	@uv run python manage.py generate_ai_context 2>/dev/null || echo "$(YELLOW)Command not yet implemented$(RESET)"
	@echo "$(GREEN)Done!$(RESET)"

ai-context-all: ## Generate all AI context formats
	@echo "$(CYAN)Generating all AI context files...$(RESET)"
	@uv run python manage.py generate_ai_context --format all 2>/dev/null || echo "$(YELLOW)Command not yet implemented$(RESET)"
	@echo "$(GREEN)Done!$(RESET)"

# ============================================================================
## Performance & Benchmarking
# ============================================================================

benchmark: ## Run performance benchmarks (SUITE=json|schema|database|throughput; default runs framework comparison + all suites)
	# Requires: uv add --dev djangorestframework django-ninja fastapi for full comparison
	@echo "$(CYAN)Running benchmarks...$(RESET)"
	@if [ -n "$(SUITE)" ]; then \
		uv run python benchmarks/bench_$(SUITE).py $(ARGS); \
	else \
		uv run python benchmarks/run_all.py --comparison --rich $(ARGS); \
	fi

benchmark-json: ## Run JSON serialization benchmarks
	@echo "$(CYAN)Running JSON benchmarks...$(RESET)"
	@uv run python benchmarks/bench_json.py $(ARGS)

benchmark-schema: ## Run schema validation benchmarks
	@echo "$(CYAN)Running schema benchmarks...$(RESET)"
	@uv run python benchmarks/bench_schema.py $(ARGS)

benchmark-db: ## Run database benchmarks
	@echo "$(CYAN)Running database benchmarks...$(RESET)"
	@uv run python benchmarks/bench_database.py $(ARGS)

benchmark-throughput: ## Run throughput benchmarks
	@echo "$(CYAN)Running throughput benchmarks...$(RESET)"
	@uv run python benchmarks/bench_throughput.py $(ARGS)

benchmark-compare: ## Compare with other frameworks
	@echo "$(CYAN)Running framework comparison...$(RESET)"
	@uv run python benchmarks/bench_comparison.py $(ARGS)

benchmark-save: ## Run benchmarks and save results
	@echo "$(CYAN)Running benchmarks and saving...$(RESET)"
	@uv run python benchmarks/run_all.py --save $(ARGS)

benchmark-diff: ## Compare current benchmarks with baseline
	@echo "$(CYAN)Comparing with baseline...$(RESET)"
	@uv run python benchmarks/run_all.py --compare $(ARGS)

profile: ## Profile the application
	@echo "$(CYAN)Starting profiler...$(RESET)"
	@uv run python -m cProfile -o profile.pstats manage.py runserver --noreload &
	@echo "$(YELLOW)Use 'snakeviz profile.pstats' to view results$(RESET)"

# ============================================================================
## Advanced Development
# ============================================================================

tunnel: ## Start dev server with ngrok tunnel
	@echo "$(CYAN)Starting server with tunnel...$(RESET)"
	@which ngrok > /dev/null || (echo "$(RED)ngrok not installed. Install from https://ngrok.com$(RESET)" && exit 1)
	@uv run python manage.py runserver 8000 &
	@sleep 2 && ngrok http 8000

serve-https: ## Start dev server with HTTPS (requires mkcert)
	@echo "$(CYAN)Starting HTTPS server...$(RESET)"
	@which mkcert > /dev/null || (echo "$(RED)mkcert not installed. Run: brew install mkcert$(RESET)" && exit 1)
	@mkdir -p .certs
	@test -f .certs/localhost.pem || mkcert -cert-file .certs/localhost.pem -key-file .certs/localhost-key.pem localhost 127.0.0.1
	@uv run python manage.py runserver_plus --cert-file .certs/localhost.pem --key-file .certs/localhost-key.pem 2>/dev/null || \
		echo "$(YELLOW)runserver_plus not available. Install django-extensions.$(RESET)"

request: ## Make an authenticated API request (URL=... [METHOD=GET] [DATA=...])
	@if [ -z "$(URL)" ]; then \
		echo "$(RED)Error: URL is required$(RESET)"; \
		echo "Usage: make request URL=/api/users METHOD=GET"; \
		exit 1; \
	fi
	@echo "$(CYAN)Making $(or $(METHOD),GET) request to $(URL)...$(RESET)"
	@uv run python -c "from django_matt.testing import APITestClient; c = APITestClient(); print(c.$(shell echo $(or $(METHOD),get) | tr '[:upper:]' '[:lower:]')('$(URL)').json())" 2>/dev/null || \
		curl -s "http://localhost:8000$(URL)"

# ============================================================================
## Maintenance & Cleanup
# ============================================================================

cleanup-tokens: ## Clean up expired tokens and sessions
	@echo "$(CYAN)Cleaning up expired tokens...$(RESET)"
	@uv run python manage.py clearsessions 2>/dev/null || true
	@echo "$(GREEN)Done!$(RESET)"

cleanup-logs: ## Clean up old audit logs (DAYS=30)
	@echo "$(CYAN)Cleaning up logs older than $(or $(DAYS),30) days...$(RESET)"
	@uv run python -c "from django_matt.audit import cleanup_old_logs; cleanup_old_logs(days=$(or $(DAYS),30))" 2>/dev/null || \
		echo "$(YELLOW)Audit module not configured$(RESET)"

backup-db: ## Create database backup
	@echo "$(CYAN)Creating database backup...$(RESET)"
	@mkdir -p backups
	@uv run python manage.py dumpdata --natural-primary --natural-foreign -o backups/backup_$$(date +%Y%m%d_%H%M%S).json
	@echo "$(GREEN)Backup created in backups/$(RESET)"

restore-db: ## Restore database from backup (FILE=backups/backup.json)
	@if [ -z "$(FILE)" ]; then \
		echo "$(RED)Error: FILE is required$(RESET)"; \
		echo "Usage: make restore-db FILE=backups/backup_20240101.json"; \
		exit 1; \
	fi
	@echo "$(RED)$(BOLD)WARNING: This will overwrite current data!$(RESET)"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	@uv run python manage.py loaddata $(FILE)
	@echo "$(GREEN)Database restored!$(RESET)"

# ============================================================================
## Dependency Management
# ============================================================================

deps-check: ## Check for dependency updates
	@echo "$(CYAN)Checking for updates...$(RESET)"
	@uv pip list --outdated 2>/dev/null || uv run pip list --outdated
	@echo "$(GREEN)Done!$(RESET)"

deps-audit: ## Security audit of dependencies
	@echo "$(CYAN)Running security audit...$(RESET)"
	@uv pip audit 2>/dev/null || uv run pip-audit
	@echo "$(GREEN)Done!$(RESET)"

deps-tree: ## Show dependency tree
	@echo "$(CYAN)Dependency tree:$(RESET)"
	@uv pip tree 2>/dev/null || uv run pipdeptree

# ============================================================================
## Quick Analysis
# ============================================================================

analyze: ## Analyze codebase structure
	@echo "$(CYAN)$(BOLD)Codebase Analysis$(RESET)"
	@echo ""
	@echo "$(YELLOW)Python files:$(RESET)"
	@find django_matt -name "*.py" | wc -l | xargs echo "  Total:"
	@echo ""
	@echo "$(YELLOW)Lines of code:$(RESET)"
	@find django_matt -name "*.py" -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print "  Total: " $$1}'
	@echo ""
	@echo "$(YELLOW)Test files:$(RESET)"
	@find tests -name "test_*.py" | wc -l | xargs echo "  Total:"
	@echo ""
	@echo "$(YELLOW)Test lines:$(RESET)"
	@find tests -name "test_*.py" -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print "  Total: " $$1}'
	@echo ""
	@echo "$(YELLOW)Modules:$(RESET)"
	@ls -d django_matt/*/ 2>/dev/null | wc -l | xargs echo "  Total:"

endpoints: ## List all API endpoints (requires running server or introspection)
	@echo "$(CYAN)API Endpoints:$(RESET)"
	@uv run python manage.py matt routes 2>/dev/null || \
		uv run python -c "from django.urls import get_resolver; [print(f'  {p.pattern}') for p in get_resolver().url_patterns]" 2>/dev/null || \
		echo "$(YELLOW)Could not introspect endpoints$(RESET)"

schemas-list: ## List all Pydantic schemas
	@echo "$(CYAN)Pydantic Schemas:$(RESET)"
	@grep -r "class.*Schema.*:" django_matt --include="*.py" | grep -v "__pycache__" | head -30 || true

models-list: ## List all Django models
	@echo "$(CYAN)Django Models:$(RESET)"
	@grep -r "class.*models.Model" django_matt --include="*.py" | grep -v "__pycache__" | head -30 || true
