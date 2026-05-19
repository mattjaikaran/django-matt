# React Vite Boilerplate Makefile
# Requires Bun to be installed

.PHONY: help install dev build preview test test-ui test-coverage lint lint-fix format format-check type-check clean setup docker-build docker-run docker-stop \
	shadcn-common shadcn-forms shadcn-data shadcn-navigation shadcn-feedback shadcn-layout shadcn-all shadcn-list shadcn-update \
	django-prep django-build django-types django-urls django-settings django-all api-schema api-types api-client cors-setup \
	dev-open dev-debug storybook-init storybook storybook-build component hook security-audit performance-test \
	update-all reset-project git-setup git-hooks env-dev env-prod env-all help-shadcn help-django help-utils help-all

# Default target
help: ## Show this help message
	@echo "React Vite Boilerplate - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Development Commands
install: ## Install dependencies
	@echo "Installing dependencies with Bun..."
	bun install

dev: ## Start development server
	@echo "Starting development server..."
	bun dev

build: ## Build for production
	@echo "Building for production..."
	bun run build

preview: ## Preview production build
	@echo "Starting preview server..."
	bun run preview

# Testing Commands
test: ## Run tests
	@echo "Running tests..."
	bun run test

test-ui: ## Run tests with UI
	@echo "Running tests with UI..."
	bun run test:ui

test-coverage: ## Run tests with coverage
	@echo "Running tests with coverage..."
	bun run test:coverage

# Code Quality Commands
lint: ## Run ESLint
	@echo "Running ESLint..."
	bun run lint

lint-fix: ## Fix ESLint issues
	@echo "Fixing ESLint issues..."
	bun run lint:fix

format: ## Format code with Prettier
	@echo "Formatting code..."
	bun run format

format-check: ## Check code formatting
	@echo "Checking code formatting..."
	bun run format:check

type-check: ## Run TypeScript type checking
	@echo "Running TypeScript type checking..."
	bun run type-check

# Setup Commands
setup: install ## Full project setup
	@echo "Setting up project..."
	@echo "Installing dependencies..."
	bun install
	@echo "Setting up Shadcn/ui..."
	bunx shadcn@latest init -y
	@echo "Setup complete!"

setup-shadcn: ## Setup Shadcn/ui components
	@echo "Setting up Shadcn/ui..."
	bunx shadcn@latest init -y

add-shadcn-component: ## Add a Shadcn/ui component (usage: make add-shadcn-component COMPONENT=button)
	@if [ -z "$(COMPONENT)" ]; then \
		echo "Usage: make add-shadcn-component COMPONENT=component-name"; \
		echo "Example: make add-shadcn-component COMPONENT=button"; \
		exit 1; \
	fi
	@echo "Adding Shadcn/ui component: $(COMPONENT)"
	bunx shadcn@latest add $(COMPONENT) -y

# Shadcn/ui Bulk Component Installation
shadcn-common: ## Install common shadcn/ui components (button, input, card, badge, avatar)
	@echo "Installing common shadcn/ui components..."
	bunx shadcn@latest add button input card badge avatar -y
	@echo "Common components installed!"

shadcn-forms: ## Install form-related shadcn/ui components
	@echo "Installing form-related shadcn/ui components..."
	bunx shadcn@latest add form input textarea select checkbox radio-group switch label -y
	@echo "Form components installed!"

shadcn-data: ## Install data display shadcn/ui components
	@echo "Installing data display shadcn/ui components..."
	bunx shadcn@latest add table data-table pagination badge progress separator -y
	@echo "Data display components installed!"

shadcn-navigation: ## Install navigation shadcn/ui components
	@echo "Installing navigation shadcn/ui components..."
	bunx shadcn@latest add navigation-menu breadcrumb tabs command menubar -y
	@echo "Navigation components installed!"

shadcn-feedback: ## Install feedback shadcn/ui components
	@echo "Installing feedback shadcn/ui components..."
	bunx shadcn@latest add alert alert-dialog toast dialog sheet popover tooltip -y
	@echo "Feedback components installed!"

shadcn-layout: ## Install layout shadcn/ui components
	@echo "Installing layout shadcn/ui components..."
	bunx shadcn@latest add aspect-ratio resizable scroll-area separator skeleton -y
	@echo "Layout components installed!"

shadcn-all: ## Install all common shadcn/ui component categories
	@echo "Installing all common shadcn/ui components..."
	@make shadcn-common
	@make shadcn-forms
	@make shadcn-data
	@make shadcn-navigation
	@make shadcn-feedback
	@make shadcn-layout
	@echo "All shadcn/ui components installed!"

shadcn-list: ## List all available shadcn/ui components
	@echo "Available shadcn/ui components:"
	bunx shadcn@latest add --help | grep -A 50 "Available components:" || echo "Run 'bunx shadcn@latest add' to see available components"

shadcn-update: ## Update all shadcn/ui components
	@echo "Updating shadcn/ui components..."
	bunx shadcn@latest diff
	@echo "Check the diff above and run 'bunx shadcn@latest add <component> -y' to update specific components"

# Docker Commands
docker-build: ## Build Docker image
	@echo "Building Docker image..."
	docker build -t react-vite-boilerplate .

docker-run: ## Run Docker container
	@echo "Running Docker container..."
	docker run -p 3000:3000 --name react-vite-boilerplate-container react-vite-boilerplate

docker-stop: ## Stop Docker container
	@echo "Stopping Docker container..."
	docker stop react-vite-boilerplate-container || true
	docker rm react-vite-boilerplate-container || true

docker-dev: ## Run development environment with Docker Compose
	@echo "Starting development environment with Docker Compose..."
	docker-compose up --build

# Utility Commands
clean: ## Clean node_modules and build artifacts
	@echo "Cleaning project..."
	rm -rf node_modules
	rm -rf dist
	rm -rf coverage
	rm -rf .turbo

fresh-install: clean install ## Clean install dependencies
	@echo "Fresh install complete!"

check-all: type-check lint test ## Run all checks (type-check, lint, test)
	@echo "All checks passed!"

# Git Hooks Setup
setup-hooks: ## Setup Git hooks
	@echo "Setting up Git hooks..."
	@if [ ! -d ".git" ]; then \
		echo "Not a Git repository. Initializing..."; \
		git init; \
	fi
	@echo "#!/bin/sh" > .git/hooks/pre-commit
	@echo "make check-all" >> .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "Git hooks setup complete!"

# Environment Commands
env-setup: ## Copy environment file
	@if [ ! -f .env ]; then \
		echo "Creating .env file from env.example..."; \
		cp env.example .env; \
		echo ".env file created! Please update it with your configuration."; \
	else \
		echo ".env file already exists."; \
	fi

# Package Management
update-deps: ## Update dependencies
	@echo "Updating dependencies..."
	bun update

outdated: ## Check for outdated dependencies
	@echo "Checking for outdated dependencies..."
	bun outdated

# Production Commands
deploy-prep: clean install build test ## Prepare for deployment
	@echo "Deployment preparation complete!"

# Router Commands (TanStack Router specific)
generate-routes: ## Generate TanStack Router routes
	@echo "Generating TanStack Router routes..."
	bunx @tanstack/router-cli generate

# Development Utilities
dev-https: ## Start development server with HTTPS
	@echo "Starting development server with HTTPS..."
	bun run dev --https

dev-host: ## Start development server accessible from network
	@echo "Starting development server accessible from network..."
	bun run dev --host

# Bundle Analysis
analyze: build ## Analyze bundle size
	@echo "Analyzing bundle size..."
	bunx vite-bundle-analyzer dist

# Development Utilities
dev-open: ## Start dev server and open browser
	@echo "Starting development server and opening browser..."
	bun run dev --open

dev-debug: ## Start dev server with debug mode
	@echo "Starting development server in debug mode..."
	DEBUG=* bun run dev

storybook-init: ## Initialize Storybook
	@echo "Initializing Storybook..."
	bunx storybook@latest init
	@echo "Storybook initialized! Run 'make storybook' to start"

storybook: ## Start Storybook development server
	@echo "Starting Storybook..."
	bun run storybook

storybook-build: ## Build Storybook for production
	@echo "Building Storybook..."
	bun run build-storybook

# Code Generation
component: ## Generate a new React component (usage: make component NAME=MyComponent)
	@if [ -z "$(NAME)" ]; then \
		echo "Usage: make component NAME=ComponentName"; \
		echo "Example: make component NAME=UserCard"; \
		exit 1; \
	fi
	@echo "Creating component: $(NAME)"
	@mkdir -p src/components/$(shell echo $(NAME) | tr '[:upper:]' '[:lower:]')
	@cat > src/components/$(shell echo $(NAME) | tr '[:upper:]' '[:lower:]')/$(NAME).tsx << 'EOF'
import React from 'react';

interface $(NAME)Props {
  // Add your props here
}

export const $(NAME): React.FC<$(NAME)Props> = ({}) => {
  return (
    <div>
      <h2>$(NAME) Component</h2>
    </div>
  );
};

export default $(NAME);
EOF
	@cat > src/components/$(shell echo $(NAME) | tr '[:upper:]' '[:lower:]')/index.ts << 'EOF'
export { $(NAME), default } from './$(NAME)';
export type { $(NAME)Props } from './$(NAME)';
EOF
	@echo "Component $(NAME) created at src/components/$(shell echo $(NAME) | tr '[:upper:]' '[:lower:]')/"

hook: ## Generate a custom React hook (usage: make hook NAME=useMyHook)
	@if [ -z "$(NAME)" ]; then \
		echo "Usage: make hook NAME=hookName"; \
		echo "Example: make hook NAME=useLocalStorage"; \
		exit 1; \
	fi
	@echo "Creating hook: $(NAME)"
	@cat > src/hooks/$(NAME).ts << 'EOF'
import { useState, useEffect } from 'react';

export const $(NAME) = () => {
  // Add your hook logic here
  const [value, setValue] = useState();

  useEffect(() => {
    // Add your effect logic here
  }, []);

  return { value, setValue };
};

export default $(NAME);
EOF
	@echo "Hook $(NAME) created at src/hooks/$(NAME).ts"

# Security & Performance
security-audit: ## Run security audit
	@echo "Running security audit..."
	bun audit

performance-test: ## Run Lighthouse CI performance test
	@echo "Running performance test..."
	@echo "Installing @lhci/cli if not present..."
	@bun add -D @lhci/cli
	@echo "Building for performance test..."
	@make build
	@echo "Running Lighthouse CI..."
	@bunx lhci autorun --upload.target=temporary-public-storage

# Maintenance
update-all: ## Update all dependencies and tools
	@echo "Updating all dependencies and tools..."
	@make update-deps
	@echo "Updating shadcn/ui components..."
	@make shadcn-update
	@echo "All updates complete!"

reset-project: ## Reset project to clean state (removes node_modules, dist, coverage)
	@echo "Resetting project to clean state..."
	@make clean
	@echo "Removing lock files..."
	@rm -f bun.lockb package-lock.json yarn.lock
	@echo "Project reset complete. Run 'make install' to reinstall dependencies."

# Git Utilities
git-setup: ## Setup Git repository with initial commit
	@if [ ! -d ".git" ]; then \
		echo "Initializing Git repository..."; \
		git init; \
		git add .; \
		git commit -m "Initial commit: React Vite boilerplate setup"; \
		echo "Git repository initialized with initial commit"; \
	else \
		echo "Git repository already exists"; \
	fi

git-hooks: setup-hooks ## Alias for setup-hooks

# Environment Management
env-dev: ## Create development environment file
	@echo "Creating development environment file..."
	@cat > .env.development << 'EOF'
# Development Environment Variables
VITE_API_URL=http://localhost:8000/api
VITE_APP_ENV=development
VITE_DEBUG=true
VITE_ENABLE_DEVTOOLS=true
EOF
	@echo "Development environment file created at .env.development"

env-prod: ## Create production environment template
	@echo "Creating production environment template..."
	@cat > .env.production.example << 'EOF'
# Production Environment Variables
VITE_API_URL=https://your-api-domain.com/api
VITE_APP_ENV=production
VITE_DEBUG=false
VITE_ENABLE_DEVTOOLS=false
EOF
	@echo "Production environment template created at .env.production.example"

env-all: env-setup env-dev env-prod ## Create all environment files
	@echo "All environment files created!"

# Django Integration Commands
django-prep: ## Prepare build for Django static files integration
	@echo "Preparing build for Django integration..."
	@echo "Building production assets..."
	@make build
	@echo "Creating Django-compatible static structure..."
	@mkdir -p dist/static/js dist/static/css dist/static/assets
	@if [ -d "dist/assets" ]; then \
		cp -r dist/assets/* dist/static/assets/ 2>/dev/null || true; \
	fi
	@echo "Django static files prepared in dist/static/"

django-build: ## Build and prepare for Django with proper static file structure
	@echo "Building for Django deployment..."
	@make clean
	@make install
	@make build
	@make django-prep
	@echo "Django build complete! Copy dist/static/ to your Django STATIC_ROOT"

django-types: ## Generate TypeScript types from Django API schema
	@echo "Generating TypeScript types from Django API..."
	@if [ -z "$(SCHEMA_URL)" ]; then \
		echo "Usage: make django-types SCHEMA_URL=http://localhost:8000/api/schema/"; \
		echo "Or set DJANGO_SCHEMA_URL environment variable"; \
		exit 1; \
	fi
	@echo "Fetching schema from $(SCHEMA_URL)..."
	@mkdir -p src/types/generated
	@curl -s "$(SCHEMA_URL)" > src/types/generated/schema.json
	@echo "Schema downloaded. Install openapi-typescript for type generation:"
	@echo "bun add -D openapi-typescript"
	@echo "Then run: bunx openapi-typescript src/types/generated/schema.json -o src/types/generated/api.ts"

api-schema: ## Download API schema from Django backend
	@echo "Downloading API schema..."
	@SCHEMA_URL=$${SCHEMA_URL:-$${DJANGO_SCHEMA_URL:-http://localhost:8000/api/schema/}}; \
	echo "Using schema URL: $$SCHEMA_URL"; \
	mkdir -p src/types/generated; \
	curl -s "$$SCHEMA_URL" > src/types/generated/schema.json && \
	echo "Schema downloaded to src/types/generated/schema.json" || \
	echo "Failed to download schema. Make sure your Django server is running and SCHEMA_URL is correct"

cors-setup: ## Generate CORS configuration helper for Django
	@echo "Generating CORS configuration helper..."
	@mkdir -p docs/django-integration
	@cat > docs/django-integration/cors-settings.py << 'EOF'
# Add to your Django settings.py for CORS configuration
# Install: pip install django-cors-headers

INSTALLED_APPS = [
    # ... your other apps
    'corsheaders',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    # ... your other middleware
]

# CORS settings for development
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # Vite dev server
    "http://127.0.0.1:3000",
    "http://localhost:5173",  # Alternative Vite port
]

# For production, be more specific:
# CORS_ALLOWED_ORIGINS = [
#     "https://yourdomain.com",
# ]

# Allow credentials (cookies, authorization headers)
CORS_ALLOW_CREDENTIALS = True

# Allow all headers during development
CORS_ALLOW_ALL_HEADERS = True

# Specific headers for production:
# CORS_ALLOW_HEADERS = [
#     'accept',
#     'accept-encoding',
#     'authorization',
#     'content-type',
#     'dnt',
#     'origin',
#     'user-agent',
#     'x-csrftoken',
#     'x-requested-with',
# ]
EOF
	@echo "CORS configuration created at docs/django-integration/cors-settings.py"

django-urls: ## Generate Django URL configuration helper
	@echo "Generating Django URL configuration helper..."
	@mkdir -p docs/django-integration
	@cat > docs/django-integration/urls-example.py << 'EOF'
# Example Django URLs configuration for serving React app
# Add to your main urls.py

from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('your_api.urls')),  # Your API endpoints

    # Serve React app for all other routes
    re_path(r'^.*', TemplateView.as_view(template_name='index.html')),
]

# Serve static files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
EOF
	@echo "Django URLs example created at docs/django-integration/urls-example.py"

django-settings: ## Generate Django settings helper for React integration
	@echo "Generating Django settings helper..."
	@mkdir -p docs/django-integration
	@cat > docs/django-integration/settings-example.py << 'EOF'
# Django settings for React integration
# Add these to your Django settings.py

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Additional locations of static files
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'frontend/dist/static'),  # React build output
]

# Templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'frontend/dist'),  # React build output
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Security settings for production
# SECURE_BROWSER_XSS_FILTER = True
# SECURE_CONTENT_TYPE_NOSNIFF = True
# X_FRAME_OPTIONS = 'DENY'
EOF
	@echo "Django settings example created at docs/django-integration/settings-example.py"

django-all: cors-setup django-urls django-settings ## Generate all Django integration helpers
	@echo "All Django integration helpers generated in docs/django-integration/"

# API Integration Commands
api-types: ## Generate TypeScript types from OpenAPI schema
	@echo "Generating API types from OpenAPI schema..."
	@if [ ! -f "src/types/generated/schema.json" ]; then \
		echo "No schema found. Run 'make api-schema' first"; \
		exit 1; \
	fi
	@echo "Installing openapi-typescript if not present..."
	@bun add -D openapi-typescript
	@echo "Generating TypeScript types..."
	@bunx openapi-typescript src/types/generated/schema.json -o src/types/generated/api.ts
	@echo "API types generated at src/types/generated/api.ts"

api-client: ## Generate API client from schema
	@echo "Generating API client..."
	@if [ ! -f "src/types/generated/schema.json" ]; then \
		echo "No schema found. Run 'make api-schema' first"; \
		exit 1; \
	fi
	@bun add -D @hey-api/openapi-ts
	@bunx @hey-api/openapi-ts -i src/types/generated/schema.json -o src/api/generated
	@echo "API client generated at src/api/generated/"

# Help for specific categories
help-dev: ## Show development commands
	@echo "Development Commands:"
	@grep -E '^(install|dev|build|preview):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

help-test: ## Show testing commands
	@echo "Testing Commands:"
	@grep -E '^test.*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

help-docker: ## Show Docker commands
	@echo "Docker Commands:"
	@grep -E '^docker.*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

help-shadcn: ## Show shadcn/ui commands
	@echo "Shadcn/ui Commands:"
	@grep -E '^(setup-shadcn|add-shadcn-component|shadcn-).*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

help-django: ## Show Django integration commands
	@echo "Django Integration Commands:"
	@grep -E '^(django-|cors-setup|api-).*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

help-utils: ## Show utility commands
	@echo "Utility Commands:"
	@grep -E '^(component|hook|dev-open|dev-debug|storybook|security-audit|performance-test|update-all|reset-project|git-setup|git-hooks|env-):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

help-all: ## Show all available commands by category
	@echo "=== React Vite Boilerplate - All Commands ==="
	@echo ""
	@make help-dev
	@echo ""
	@make help-test
	@echo ""
	@make help-shadcn
	@echo ""
	@make help-django
	@echo ""
	@make help-docker
	@echo ""
	@make help-utils
	@echo ""
	@echo "Other Commands:"
	@grep -E '^(clean|fresh-install|check-all|setup|env-setup|update-deps|outdated|deploy-prep|generate-routes|analyze):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ==================================
# Optional Features
# ==================================

# SSR (Server-Side Rendering)
setup-ssr: ## Enable Server-Side Rendering
	@echo "Setting up SSR..."
	@./scripts/setup-ssr.sh

disable-ssr: ## Disable Server-Side Rendering
	@echo "Disabling SSR..."
	@./scripts/disable-ssr.sh

# RSC (React Server Components)
setup-rsc: ## Enable React Server Components utilities
	@echo "Setting up RSC..."
	@./scripts/setup-rsc.sh

disable-rsc: ## Disable React Server Components utilities
	@echo "Disabling RSC..."
	@./scripts/disable-rsc.sh

# Combined feature commands
add-feature: ## Add optional feature (usage: make add-feature FEATURE=ssr)
	@if [ -z "$(FEATURE)" ]; then \
		echo "Usage: make add-feature FEATURE=<ssr|rsc|all>"; \
		exit 1; \
	fi
	@./scripts/add-feature.sh $(FEATURE)

remove-feature: ## Remove optional feature (usage: make remove-feature FEATURE=ssr)
	@if [ -z "$(FEATURE)" ]; then \
		echo "Usage: make remove-feature FEATURE=<ssr|rsc|all>"; \
		exit 1; \
	fi
	@./scripts/remove-feature.sh $(FEATURE)

# List available optional features
list-features: ## List available optional features
	@echo "Available Optional Features:"
	@echo ""
	@echo "  \033[36mssr\033[0m  - Server-Side Rendering with Express"
	@echo "        Adds: server.ts, entry files, vite config for SSR"
	@echo "        Use for: SEO, faster initial load, social previews"
	@echo ""
	@echo "  \033[36mrsc\033[0m  - React Server Components utilities"
	@echo "        Adds: isServer, isClient, cache, serverOnly helpers"
	@echo "        Use for: Preparing for Next.js migration"
	@echo ""
	@echo "Commands:"
	@echo "  make add-feature FEATURE=ssr     - Enable SSR"
	@echo "  make add-feature FEATURE=rsc     - Enable RSC"
	@echo "  make add-feature FEATURE=all     - Enable all features"
	@echo "  make remove-feature FEATURE=ssr  - Disable SSR"

help-features: ## Show optional features commands
	@echo "Optional Features Commands:"
	@grep -E '^(setup-ssr|disable-ssr|setup-rsc|disable-rsc|add-feature|remove-feature|list-features):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ==================================
# Monorepo Commands
# ==================================

setup-monorepo: ## Setup frontend for monorepo with Django backend
	@echo "Setting up monorepo configuration..."
	@./scripts/setup-monorepo.sh

dev-monorepo: ## Start frontend in monorepo mode (proxies to Django)
	@echo "Starting frontend in monorepo mode..."
	bun run dev --config vite.config.monorepo.ts

build-monorepo: ## Build frontend for Django integration
	@echo "Building frontend for monorepo deployment..."
	@make clean
	bun run build --config vite.config.monorepo.ts
	@make django-prep
	@echo "Build complete! Copy dist/ to your Django static files"

docker-monorepo: ## Start full monorepo stack with Docker
	@echo "Starting monorepo Docker stack..."
	docker-compose -f docker-compose.monorepo.yml up --build

docker-monorepo-down: ## Stop monorepo Docker stack
	@echo "Stopping monorepo Docker stack..."
	docker-compose -f docker-compose.monorepo.yml down

docker-monorepo-prod: ## Start monorepo stack with nginx reverse proxy
	@echo "Starting production monorepo stack..."
	docker-compose -f docker-compose.monorepo.yml --profile production up --build

help-monorepo: ## Show monorepo commands
	@echo "Monorepo Commands:"
	@grep -E '^(setup-monorepo|dev-monorepo|build-monorepo|docker-monorepo):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
