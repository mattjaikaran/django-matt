"""
Django Matt API project generator command.

This command generates a new Django project with django-matt API configuration.

Usage:
    # Basic starter project
    python -m django_matt startapi myproject
    
    # B2B project with JWT auth
    python -m django_matt startapi myproject --template b2b --auth jwt
    
    # Full-stack with React frontend
    python -m django_matt startapi myproject --frontend react-vite --docker
    
    # iOS-ready backend
    python -m django_matt startapi myproject --frontend swift --auth jwt
"""

import os
import subprocess
from pathlib import Path
from typing import Optional

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Generate a new Django project with django-matt API configuration"

    def add_arguments(self, parser):
        parser.add_argument(
            "name",
            help="Name of the project to create",
        )
        parser.add_argument(
            "--directory",
            default=None,
            help="Directory to create the project in (default: current directory)",
        )
        parser.add_argument(
            "--api-app",
            default="api",
            help="Name of the API app to create (default: api)",
        )
        parser.add_argument(
            "--db",
            choices=["postgres", "mysql", "sqlite"],
            default="postgres",
            help="Default database to use (default: postgres)",
        )
        parser.add_argument(
            "--template",
            "-t",
            choices=["starter", "b2b", "b2c"],
            default="starter",
            help="Project template type (default: starter)",
        )
        parser.add_argument(
            "--auth",
            "-a",
            choices=["none", "jwt", "magic-link", "oauth", "all"],
            default="jwt",
            help="Authentication method to include (default: jwt)",
        )
        parser.add_argument(
            "--frontend",
            "-f",
            choices=["none", "react-vite", "swift"],
            default="none",
            help="Frontend scaffold to generate (default: none)",
        )
        parser.add_argument(
            "--docker",
            action="store_true",
            help="Generate Docker and docker-compose configuration",
        )
        parser.add_argument(
            "--with-example",
            action="store_true",
            help="Include example models, schemas, and controllers",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing files",
        )

    def handle(self, *args, **options):
        project_name = options["name"]
        directory = options["directory"] or os.getcwd()
        api_app = options["api_app"]
        db = options["db"]
        template = options["template"]
        auth = options["auth"]
        frontend = options["frontend"]
        docker = options["docker"]
        with_example = options["with_example"]
        force = options["force"]

        # Create the project directory
        project_dir = Path(directory)
        if project_dir.exists() and not force:
            if (project_dir / project_name).exists() or (project_dir / "manage.py").exists():
                raise CommandError(f"Project already exists in {project_dir}. Use --force to overwrite.")
        else:
            os.makedirs(project_dir, exist_ok=True)

        # Create the project
        self.stdout.write(f"Creating Django project {project_name}...")
        self.stdout.write(f"  Template: {template}")
        self.stdout.write(f"  Auth: {auth}")
        self.stdout.write(f"  Frontend: {frontend}")
        self.stdout.write(f"  Docker: {'Yes' if docker else 'No'}")
        
        self._create_project(project_name, directory)

        # Change to the project directory
        original_dir = os.getcwd()
        os.chdir(project_dir)

        try:
            # Create the API app
            self.stdout.write(f"Creating API app {api_app}...")
            self._create_api_app(api_app)

            # Configure the project with django-matt
            self.stdout.write("Configuring project with django-matt...")
            self._configure_project(project_name, api_app, db, template, auth)

            # Create example models, schemas, and controllers if requested
            if with_example or template != "starter":
                self.stdout.write("Creating example models, schemas, and controllers...")
                self._create_example(api_app, template, auth)

            # Generate Docker configuration if requested
            if docker:
                self.stdout.write("Generating Docker configuration...")
                self._create_docker_config(project_name, db)

            # Generate Makefile
            self.stdout.write("Generating Makefile...")
            self._create_makefile(project_name, docker, frontend)

            # Generate frontend scaffold if requested
            if frontend != "none":
                self.stdout.write(f"Generating {frontend} frontend scaffold...")
                self._create_frontend(frontend, project_name)

            # Generate README
            self.stdout.write("Generating README...")
            self._create_readme(project_name, template, auth, frontend, docker)

            self.stdout.write(self.style.SUCCESS(f"\nSuccessfully created django-matt API project {project_name}"))
            
            self._print_next_steps(directory, docker, frontend)
            
        finally:
            # Change back to the original directory
            os.chdir(original_dir)

    def _print_next_steps(self, directory: str, docker: bool, frontend: str):
        """Print next steps for the user."""
        cd_path = directory if directory else "."
        
        self.stdout.write("\nNext steps:")
        self.stdout.write(f"  cd {cd_path}")
        
        if docker:
            self.stdout.write("  make up          # Start with Docker")
            self.stdout.write("  make migrate     # Run migrations")
        else:
            self.stdout.write("  python manage.py migrate")
            self.stdout.write("  python manage.py runserver_hot")
        
        if frontend == "react-vite":
            self.stdout.write("\nFor the frontend:")
            self.stdout.write("  cd frontend && bun install && bun dev")
        elif frontend == "swift":
            self.stdout.write("\nFor the iOS app:")
            self.stdout.write("  open ios/App.xcodeproj")

    def _create_project(self, project_name, directory):
        """Create a new Django project."""
        try:
            subprocess.run(
                [
                    "django-admin",
                    "startproject",
                    project_name,
                    directory,
                ],
                check=True,
            )
        except subprocess.CalledProcessError:
            raise CommandError("Failed to create Django project")

    def _create_api_app(self, api_app):
        """Create a new Django app for the API."""
        try:
            manage_py = "./manage.py"
            subprocess.run(
                [
                    "python",
                    manage_py,
                    "startapp",
                    api_app,
                ],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
            raise CommandError("Failed to create API app")

    def _configure_project(self, project_name, api_app, db, template, auth):
        """Configure the project with django-matt."""
        settings_path = Path(f"{project_name}/settings.py")
        if settings_path.exists():
            with open(settings_path) as f:
                settings_content = f.read()

            # Add django_matt and api_app to INSTALLED_APPS
            settings_content = settings_content.replace(
                "INSTALLED_APPS = [",
                f'INSTALLED_APPS = [\n    "django_matt",\n    "{api_app}",',
            )

            # Add auth configuration based on template and auth type
            auth_config = self._get_auth_settings(auth)
            settings_content += f"\n\n# Django Matt Configuration\n{auth_config}"

            # Add template-specific settings
            if template == "b2b":
                settings_content += self._get_b2b_settings()
            elif template == "b2c":
                settings_content += self._get_b2c_settings()

            with open(settings_path, "w") as f:
                f.write(settings_content)

        # Initialize django-matt configuration
        try:
            manage_py = "./manage.py"
            subprocess.run(
                [
                    "python",
                    manage_py,
                    "config",
                    "init",
                    "--db",
                    db,
                ],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            self.stdout.write(self.style.WARNING(f"Config init skipped: {str(e)}"))

        # Update the project's urls.py
        urls_path = Path(f"{project_name}/urls.py")
        if urls_path.exists():
            with open(urls_path) as f:
                urls_content = f.read()

            urls_content = urls_content.replace(
                "from django.urls import path",
                "from django.urls import path, include",
            )

            urls_content = urls_content.replace(
                "urlpatterns = [",
                f'urlpatterns = [\n    path("", include("{api_app}.urls")),',
            )

            with open(urls_path, "w") as f:
                f.write(urls_content)

    def _get_auth_settings(self, auth: str) -> str:
        """Get authentication settings based on auth type."""
        if auth == "none":
            return ""
        
        settings = """
# JWT Configuration
DJANGO_MATT_JWT = {
    "SECRET_KEY": "change-me-in-production",
    "ACCESS_TOKEN_LIFETIME": 60 * 15,  # 15 minutes
    "REFRESH_TOKEN_LIFETIME": 60 * 60 * 24 * 7,  # 7 days
    "ALGORITHM": "HS256",
}
"""
        if auth in ["magic-link", "all"]:
            settings += """
# Magic Link Configuration
DJANGO_MATT_MAGIC_LINK = {
    "TOKEN_LIFETIME": 60 * 15,  # 15 minutes
    "BASE_URL": "http://localhost:3000",  # Frontend URL
}
"""
        
        if auth in ["oauth", "all"]:
            settings += """
# OAuth Configuration (add your provider credentials)
DJANGO_MATT_OAUTH = {
    "GOOGLE": {
        "CLIENT_ID": "",
        "CLIENT_SECRET": "",
    },
    "GITHUB": {
        "CLIENT_ID": "",
        "CLIENT_SECRET": "",
    },
}
"""
        
        return settings

    def _get_b2b_settings(self) -> str:
        """Get B2B template settings."""
        return """
# B2B Multi-Tenant Configuration
DJANGO_MATT_MULTITENANCY = {
    "ENABLED": True,
    "TENANT_HEADER": "X-Organization-ID",
    "TENANT_URL_KWARG": "org_slug",
    "REQUIRE_TENANT": True,
    "EXEMPT_PATHS": ["/auth/", "/health/", "/docs/"],
}

# Invitation settings
INVITATION_EXPIRY_DAYS = 7
"""

    def _get_b2c_settings(self) -> str:
        """Get B2C template settings."""
        return """
# B2C Configuration
DJANGO_MATT_B2C = {
    "REQUIRE_EMAIL_VERIFICATION": True,
    "ALLOW_REGISTRATION": True,
}
"""

    def _create_example(self, api_app: str, template: str, auth: str):
        """Create example models, schemas, controllers based on template."""
        # Create directory structure
        directories = ["models", "schemas", "controllers", "admin", "tests"]
        for directory in directories:
            dir_path = Path(f"{api_app}/{directory}")
            os.makedirs(dir_path, exist_ok=True)
            # Create __init__.py in each directory
            with open(dir_path / "__init__.py", "w") as f:
                if directory == "models":
                    f.write('from .task import Task\n\n__all__ = ["Task"]\n')
                elif directory == "schemas":
                    f.write(
                        'from .task import TaskBase, TaskCreate, TaskUpdate, Task, TaskList\n\n__all__ = ["TaskBase", "TaskCreate", "TaskUpdate", "Task", "TaskList"]\n'
                    )
                elif directory == "controllers":
                    f.write('from .task import TaskController\n\n__all__ = ["TaskController"]\n')
                elif directory == "admin":
                    f.write('from .task import TaskAdmin\n\n__all__ = ["TaskAdmin"]\n')

        # Create models
        with open(Path(f"{api_app}/models/task.py"), "w") as f:
            f.write(self._get_example_model_task())

        # Create schemas
        with open(Path(f"{api_app}/schemas/task.py"), "w") as f:
            f.write(self._get_example_schema_task())

        # Create controllers
        with open(Path(f"{api_app}/controllers/task.py"), "w") as f:
            f.write(self._get_example_controller_task())

        # Create admin
        with open(Path(f"{api_app}/admin/task.py"), "w") as f:
            f.write(self._get_example_admin_task())

        # Create apps.py
        with open(Path(f"{api_app}/apps.py"), "w") as f:
            f.write(self._get_example_apps(api_app))

        # Create urls.py based on template and auth
        with open(Path(f"{api_app}/urls.py"), "w") as f:
            f.write(self._get_example_urls(template, auth))

    def _create_docker_config(self, project_name: str, db: str):
        """Create Docker and docker-compose configuration."""
        # Dockerfile
        dockerfile_content = f'''# Python base image
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    build-essential \\
    libpq-dev \\
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install uv

# Copy dependency files
COPY pyproject.toml ./
COPY requirements.txt ./

# Install dependencies
RUN uv pip install --system -r requirements.txt

# Copy project
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
'''
        with open("Dockerfile", "w") as f:
            f.write(dockerfile_content)

        # docker-compose.yml
        db_config = ""
        if db == "postgres":
            db_config = '''
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-app}
      POSTGRES_USER: ${POSTGRES_USER:-app}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-app}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-app}"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
'''
        elif db == "mysql":
            db_config = '''
  db:
    image: mysql:8
    environment:
      MYSQL_DATABASE: ${MYSQL_DATABASE:-app}
      MYSQL_USER: ${MYSQL_USER:-app}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD:-app}
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:-root}
    volumes:
      - mysql_data:/var/lib/mysql
    ports:
      - "3306:3306"

volumes:
  mysql_data:
'''

        compose_content = f'''services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DEBUG=True
      - DATABASE_URL=${{DATABASE_URL:-postgres://app:app@db:5432/app}}
    volumes:
      - .:/app
    depends_on:
      {"db:" if db != "sqlite" else "[]"}
        {"condition: service_healthy" if db == "postgres" else ""}
    command: python manage.py runserver 0.0.0.0:8000
{db_config}
'''
        with open("docker-compose.yml", "w") as f:
            f.write(compose_content)

        # .env.example
        env_content = '''# Django
DEBUG=True
SECRET_KEY=change-me-in-production
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgres://app:app@db:5432/app
POSTGRES_DB=app
POSTGRES_USER=app
POSTGRES_PASSWORD=app

# JWT
JWT_SECRET_KEY=change-me-in-production
'''
        with open(".env.example", "w") as f:
            f.write(env_content)

        # .dockerignore
        dockerignore_content = '''__pycache__
*.py[cod]
*$py.class
*.so
.Python
.git
.gitignore
.env
.venv
env/
venv/
*.egg-info/
dist/
build/
.coverage
htmlcov/
.pytest_cache/
.mypy_cache/
node_modules/
'''
        with open(".dockerignore", "w") as f:
            f.write(dockerignore_content)

    def _create_makefile(self, project_name: str, docker: bool, frontend: str):
        """Create a Makefile with common commands."""
        if docker:
            makefile_content = f'''# {project_name} Makefile

.PHONY: help up down build logs shell migrate makemigrations test lint format

help:
\t@echo "Available commands:"
\t@echo "  make up          - Start all services"
\t@echo "  make down        - Stop all services"
\t@echo "  make build       - Build Docker images"
\t@echo "  make logs        - View logs"
\t@echo "  make shell       - Open Django shell"
\t@echo "  make migrate     - Run database migrations"
\t@echo "  make test        - Run tests"

up:
\tdocker compose up -d

down:
\tdocker compose down

build:
\tdocker compose build

logs:
\tdocker compose logs -f

shell:
\tdocker compose exec api python manage.py shell

migrate:
\tdocker compose exec api python manage.py migrate

makemigrations:
\tdocker compose exec api python manage.py makemigrations

test:
\tdocker compose exec api python manage.py test

superuser:
\tdocker compose exec api python manage.py createsuperuser
'''
        else:
            makefile_content = f'''# {project_name} Makefile

.PHONY: help run migrate makemigrations test lint format shell

help:
\t@echo "Available commands:"
\t@echo "  make run         - Start development server"
\t@echo "  make migrate     - Run database migrations"
\t@echo "  make test        - Run tests"
\t@echo "  make shell       - Open Django shell"

run:
\tpython manage.py runserver_hot

migrate:
\tpython manage.py migrate

makemigrations:
\tpython manage.py makemigrations

test:
\tpython manage.py test

shell:
\tpython manage.py shell

superuser:
\tpython manage.py createsuperuser

# Type sync
sync-types:
\tpython manage.py sync_types --target typescript --output frontend/src/types/api.ts
'''

        if frontend == "react-vite":
            makefile_content += '''
# Frontend
frontend-install:
\tcd frontend && bun install

frontend-dev:
\tcd frontend && bun dev

frontend-build:
\tcd frontend && bun run build
'''

        with open("Makefile", "w") as f:
            f.write(makefile_content)

    def _create_frontend(self, frontend: str, project_name: str):
        """Create frontend scaffold."""
        if frontend == "react-vite":
            self._create_react_vite_frontend(project_name)
        elif frontend == "swift":
            self._create_swift_frontend(project_name)

    def _create_react_vite_frontend(self, project_name: str):
        """Create React Vite frontend scaffold."""
        frontend_dir = Path("frontend")
        frontend_dir.mkdir(exist_ok=True)

        # package.json
        package_json = f'''{{
  "name": "{project_name}-frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {{
    "dev": "vite",
    "build": "tsc && vite build",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "preview": "vite preview"
  }},
  "dependencies": {{
    "@tanstack/react-query": "^5.0.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.26.0",
    "zod": "^3.23.0"
  }},
  "devDependencies": {{
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@typescript-eslint/eslint-plugin": "^8.0.0",
    "@typescript-eslint/parser": "^8.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.0",
    "eslint": "^9.0.0",
    "eslint-plugin-react-hooks": "^5.0.0",
    "eslint-plugin-react-refresh": "^0.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.5.0",
    "vite": "^5.4.0"
  }}
}}'''
        with open(frontend_dir / "package.json", "w") as f:
            f.write(package_json)

        # Create src directory
        src_dir = frontend_dir / "src"
        src_dir.mkdir(exist_ok=True)

        # Create types directory
        types_dir = src_dir / "types"
        types_dir.mkdir(exist_ok=True)
        with open(types_dir / "api.ts", "w") as f:
            f.write("// Auto-generated types - run `make sync-types` to update\n\n")

        # Create api directory
        api_dir = src_dir / "api"
        api_dir.mkdir(exist_ok=True)
        with open(api_dir / "client.ts", "w") as f:
            f.write(self._get_api_client_ts())

        # Create main App.tsx
        with open(src_dir / "App.tsx", "w") as f:
            f.write('''import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-gray-100">
        <div className="container mx-auto px-4 py-8">
          <h1 className="text-3xl font-bold text-gray-900">Welcome to the App</h1>
          <p className="mt-4 text-gray-600">Your API is ready at /api/</p>
        </div>
      </div>
    </QueryClientProvider>
  )
}

export default App
''')

        # Create main.tsx
        with open(src_dir / "main.tsx", "w") as f:
            f.write('''import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
''')

        # Create index.css
        with open(src_dir / "index.css", "w") as f:
            f.write('''@tailwind base;
@tailwind components;
@tailwind utilities;
''')

        # Create index.html
        with open(frontend_dir / "index.html", "w") as f:
            f.write(f'''<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{project_name}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
''')

        # Create vite.config.ts
        with open(frontend_dir / "vite.config.ts", "w") as f:
            f.write('''import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
''')

        # Create tsconfig.json
        with open(frontend_dir / "tsconfig.json", "w") as f:
            f.write('''{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
''')

        # Create tailwind.config.js
        with open(frontend_dir / "tailwind.config.js", "w") as f:
            f.write('''/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
''')

        # Create postcss.config.js
        with open(frontend_dir / "postcss.config.js", "w") as f:
            f.write('''export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
''')

    def _get_api_client_ts(self) -> str:
        """Get TypeScript API client code."""
        return '''// API Client for making requests to the backend

const API_BASE_URL = '/api';

interface RequestOptions {
  body?: any;
  params?: Record<string, any>;
  headers?: Record<string, string>;
}

class ApiClient {
  private baseUrl: string;
  private headers: Record<string, string> = {};

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  setAuthToken(token: string) {
    this.headers['Authorization'] = `Bearer ${token}`;
  }

  clearAuthToken() {
    delete this.headers['Authorization'];
  }

  async request<T>(
    method: string,
    path: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const url = new URL(path, window.location.origin + this.baseUrl);

    if (options.params) {
      Object.entries(options.params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value));
        }
      });
    }

    const response = await fetch(url.toString(), {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...this.headers,
        ...options.headers,
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  async get<T>(path: string, params?: Record<string, any>): Promise<T> {
    return this.request<T>('GET', path, { params });
  }

  async post<T>(path: string, body?: any): Promise<T> {
    return this.request<T>('POST', path, { body });
  }

  async put<T>(path: string, body?: any): Promise<T> {
    return this.request<T>('PUT', path, { body });
  }

  async delete<T>(path: string): Promise<T> {
    return this.request<T>('DELETE', path);
  }
}

export const api = new ApiClient();
'''

    def _create_swift_frontend(self, project_name: str):
        """Create Swift iOS frontend scaffold."""
        ios_dir = Path("ios")
        ios_dir.mkdir(exist_ok=True)

        # Create Sources directory
        sources_dir = ios_dir / "Sources"
        sources_dir.mkdir(exist_ok=True)

        # Create API directory
        api_dir = sources_dir / "API"
        api_dir.mkdir(exist_ok=True)

        # Create Models.swift placeholder
        with open(api_dir / "Models.swift", "w") as f:
            f.write("// Auto-generated models - run `make sync-types` to update\n\n")
            f.write("import Foundation\n\n")

        # Create APIClient.swift
        with open(api_dir / "APIClient.swift", "w") as f:
            f.write(self._get_swift_api_client())

        # Create Package.swift for Swift Package Manager
        with open(ios_dir / "Package.swift", "w") as f:
            f.write(f'''// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "{project_name}App",
    platforms: [
        .iOS(.v17),
        .macOS(.v14)
    ],
    products: [
        .library(
            name: "{project_name}App",
            targets: ["{project_name}App"]),
    ],
    dependencies: [],
    targets: [
        .target(
            name: "{project_name}App",
            dependencies: [],
            path: "Sources"),
    ]
)
''')

        self.stdout.write(f"  Created iOS scaffold in {ios_dir}")

    def _get_swift_api_client(self) -> str:
        """Get Swift API client code."""
        return '''// Auto-generated Swift API Client
// Do not edit manually - regenerate with sync_types command

import Foundation

/// HTTP method enumeration
public enum HTTPMethod: String {
    case get = "GET"
    case post = "POST"
    case put = "PUT"
    case patch = "PATCH"
    case delete = "DELETE"
}

/// API error types
public enum APIError: Error {
    case invalidURL
    case noData
    case decodingError(Error)
    case networkError(Error)
    case httpError(statusCode: Int, data: Data?)
}

/// API Client for making network requests
public class APIClient {
    private let baseURL: String
    private var headers: [String: String] = [:]
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder
    
    public init(baseURL: String) {
        self.baseURL = baseURL
        
        self.decoder = JSONDecoder()
        self.decoder.dateDecodingStrategy = .iso8601
        self.decoder.keyDecodingStrategy = .convertFromSnakeCase
        
        self.encoder = JSONEncoder()
        self.encoder.dateEncodingStrategy = .iso8601
        self.encoder.keyEncodingStrategy = .convertToSnakeCase
    }
    
    /// Set authorization header
    public func setAuthToken(_ token: String) {
        headers["Authorization"] = "Bearer \\(token)"
    }
    
    /// Clear authorization header
    public func clearAuthToken() {
        headers.removeValue(forKey: "Authorization")
    }
    
    /// Make a request and decode the response
    public func request<T: Codable>(
        _ method: HTTPMethod,
        path: String,
        body: Encodable? = nil,
        queryParams: [String: String]? = nil
    ) async throws -> T {
        guard var urlComponents = URLComponents(string: baseURL + path) else {
            throw APIError.invalidURL
        }
        
        if let params = queryParams {
            urlComponents.queryItems = params.map { URLQueryItem(name: $0.key, value: $0.value) }
        }
        
        guard let url = urlComponents.url else {
            throw APIError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = method.rawValue
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        for (key, value) in headers {
            request.setValue(value, forHTTPHeaderField: key)
        }
        
        if let body = body {
            request.httpBody = try encoder.encode(AnyEncodable(body))
        }
        
        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await URLSession.shared.data(for: request)
        } catch {
            throw APIError.networkError(error)
        }
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.noData
        }
        
        guard 200...299 ~= httpResponse.statusCode else {
            throw APIError.httpError(statusCode: httpResponse.statusCode, data: data)
        }
        
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decodingError(error)
        }
    }
    
    /// GET request
    public func get<T: Codable>(
        _ path: String,
        queryParams: [String: String]? = nil
    ) async throws -> T {
        try await request(.get, path: path, queryParams: queryParams)
    }
    
    /// POST request
    public func post<T: Codable, B: Encodable>(
        _ path: String,
        body: B
    ) async throws -> T {
        try await request(.post, path: path, body: body)
    }
}

/// Type-erased Encodable wrapper
private struct AnyEncodable: Encodable {
    private let _encode: (Encoder) throws -> Void
    
    init<T: Encodable>(_ wrapped: T) {
        _encode = wrapped.encode
    }
    
    func encode(to encoder: Encoder) throws {
        try _encode(encoder)
    }
}
'''

    def _create_readme(self, project_name: str, template: str, auth: str, frontend: str, docker: bool):
        """Create README.md file."""
        readme = f'''# {project_name}

A Django API project built with [django-matt](https://github.com/mattjaikaran/django-matt).

## Features

- **Template**: {template}
- **Authentication**: {auth}
- **Frontend**: {frontend}
- **Docker**: {'Yes' if docker else 'No'}

## Quick Start

'''
        if docker:
            readme += '''```bash
# Start all services
make up

# Run migrations
make migrate

# Create superuser
make superuser
```

The API will be available at http://localhost:8000
'''
        else:
            readme += '''```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start development server
python manage.py runserver_hot
```

The API will be available at http://localhost:8000
'''

        readme += '''
## API Documentation

- Swagger UI: http://localhost:8000/docs/
- ReDoc: http://localhost:8000/redoc/
- OpenAPI Schema: http://localhost:8000/openapi.json

## Project Structure

```
'''
        readme += f'''{project_name}/
├── api/
│   ├── controllers/     # API endpoints
│   ├── models/          # Database models
│   ├── schemas/         # Pydantic schemas
│   └── urls.py          # URL routing
├── {project_name}/
│   ├── settings.py      # Django settings
│   └── urls.py          # Root URL config
'''
        if frontend == "react-vite":
            readme += '''├── frontend/            # React frontend
│   ├── src/
│   │   ├── api/         # API client
│   │   └── types/       # TypeScript types
│   └── package.json
'''
        elif frontend == "swift":
            readme += '''├── ios/                 # iOS frontend
│   ├── Sources/
│   │   └── API/         # API client
│   └── Package.swift
'''
        if docker:
            readme += '''├── Dockerfile
├── docker-compose.yml
'''
        readme += '''├── Makefile
└── manage.py
```

## Type Synchronization

Generate TypeScript/Swift types from your Pydantic schemas:

```bash
# TypeScript
python manage.py sync_types --target typescript --output frontend/src/types/api.ts

# Swift
python manage.py sync_types --target swift --output ios/Sources/API/Models.swift
```
'''

        with open("README.md", "w") as f:
            f.write(readme)

    def _get_example_model_task(self):
        """Get the content for the example task model file."""
        return '''import uuid

from django.db import models


class Task(models.Model):
    """Task model for the example API."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Task"
        verbose_name_plural = "Tasks"
'''

    def _get_example_schema_task(self):
        """Get the content for the example task schema file."""
        return '''import datetime
import uuid
from typing import Optional, List

from pydantic import Field

from django_matt.core.schema import Schema


class TaskBase(Schema):
    """Base schema for Task items."""

    title: str = Field(..., description="The title of the task")
    description: Optional[str] = Field(
        None, description="A detailed description of the task"
    )
    completed: bool = Field(False, description="Whether the task is completed")


class TaskCreate(TaskBase):
    """Schema for creating a new Task."""
    
    class Config:
        from_attributes = True


class TaskUpdate(Schema):
    """Schema for updating an existing Task."""

    title: Optional[str] = Field(None, description="The title of the task")
    description: Optional[str] = Field(
        None, description="A detailed description of the task"
    )
    completed: Optional[bool] = Field(
        None, description="Whether the task is completed"
    )
    
    class Config:
        from_attributes = True


class Task(TaskBase):
    """Schema for a Task with all fields."""

    id: uuid.UUID = Field(..., description="The unique identifier for the task")
    created_at: datetime.datetime = Field(
        ..., description="When the task was created"
    )
    updated_at: Optional[datetime.datetime] = Field(
        None, description="When the task was last updated"
    )

    class Config:
        from_attributes = True


class TaskList(Schema):
    """Schema for a list of Tasks."""

    items: List[Task] = Field(..., description="List of tasks")
    count: int = Field(..., description="Total number of tasks")
    
    class Config:
        from_attributes = True
'''

    def _get_example_controller_task(self):
        """Get the content for the example task controller file."""
        return '''import uuid
from typing import Any, Dict

from django.http import HttpRequest

from django_matt.core.controller import CRUDController
from django_matt.core.router import delete, get, post, put

from ..models import Task
from ..schemas import Task as TaskSchema
from ..schemas import TaskCreate, TaskList, TaskUpdate


class TaskController(CRUDController):
    """Controller for Task items."""

    prefix = "tasks/"
    model = Task
    schema = TaskSchema
    create_schema = TaskCreate
    update_schema = TaskUpdate

    @get("", response_model=TaskList)
    async def get_tasks(self, request: HttpRequest) -> Dict[str, Any]:
        """Get all tasks."""
        result = await self.list(request)
        return result

    @get("{id}", response_model=TaskSchema)
    async def get_task(self, request: HttpRequest, id: str) -> Dict[str, Any]:
        """Get a specific task by ID."""
        task_id = uuid.UUID(id)
        result = await self.retrieve(request, task_id)
        return result

    @post("", response_model=TaskSchema)
    async def create_task(
        self, request: HttpRequest, data: TaskCreate
    ) -> Dict[str, Any]:
        """Create a new task."""
        result = await self.create(request, data)
        return result

    @put("{id}", response_model=TaskSchema)
    async def update_task(
        self, request: HttpRequest, id: str, data: TaskUpdate
    ) -> Dict[str, Any]:
        """Update an existing task."""
        task_id = uuid.UUID(id)
        result = await self.update(request, task_id, data)
        return result

    @delete("{id}")
    async def delete_task(self, request: HttpRequest, id: str) -> Dict[str, Any]:
        """Delete a task."""
        task_id = uuid.UUID(id)
        await self.delete(request, task_id)
        return {}
'''

    def _get_example_admin_task(self):
        """Get the content for the example task admin file."""
        return '''from django.contrib import admin

from ..models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """Admin configuration for Task model."""
    
    list_display = ("title", "completed", "created_at", "updated_at")
    list_filter = ("completed", "created_at", "updated_at")
    search_fields = ("title", "description")
    readonly_fields = ("id", "created_at", "updated_at")
    fieldsets = (
        (None, {
            "fields": ("id", "title", "description", "completed")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
'''

    def _get_example_apps(self, api_app):
        """Get the content for the apps.py file."""
        return f'''from django.apps import AppConfig


class ApiConfig(AppConfig):
    """Configuration for the {api_app} app."""
    
    default_auto_field = "django.db.models.BigAutoField"
    name = "{api_app}"
    
    def ready(self):
        """Perform initialization when the app is ready."""
        pass
'''

    def _get_example_urls(self, template: str, auth: str) -> str:
        """Get the content for the example urls.py file based on template."""
        urls_content = '''from django.urls import path
from django_matt import APIRouter

from .controllers import TaskController
'''
        
        if auth in ["jwt", "magic-link", "all"]:
            urls_content += '''from django_matt.auth import AuthController
'''
        
        urls_content += '''
# Create a router for the API
router = APIRouter(prefix="api/", tags=["tasks"])

# Register controllers
router.register_controller(TaskController)
'''
        
        if auth in ["jwt", "magic-link", "all"]:
            urls_content += '''router.register_controller(AuthController)
'''
        
        urls_content += '''
# Get the URL patterns
urlpatterns = router.get_urls()
'''
        return urls_content
