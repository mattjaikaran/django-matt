"""
Django Matt configuration management command.

This command provides utilities for managing Django Matt configuration files.
"""

from pathlib import Path

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Manage Django Matt configuration files"

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to run")

        # init subcommand
        init_parser = subparsers.add_parser(
            "init", help="Initialize configuration files"
        )
        init_parser.add_argument(
            "--force", action="store_true", help="Overwrite existing files"
        )
        init_parser.add_argument(
            "--env",
            choices=["development", "staging", "production", "all"],
            default="all",
            help="Environment to initialize",
        )
        init_parser.add_argument(
            "--db",
            choices=["postgres", "mysql", "sqlite"],
            default="postgres",
            help="Default database to use",
        )

        # generate subcommand
        generate_parser = subparsers.add_parser(
            "generate", help="Generate a settings.py file"
        )
        generate_parser.add_argument(
            "--env",
            choices=["development", "staging", "production"],
            default="development",
            help="Environment to generate settings for",
        )
        generate_parser.add_argument(
            "--components",
            nargs="+",
            default=["database", "cache", "security", "performance"],
            help="Components to include in the settings",
        )
        generate_parser.add_argument(
            "--output", default="settings.py", help="Output file path"
        )
        generate_parser.add_argument(
            "--db",
            choices=["postgres", "mysql", "sqlite"],
            default="postgres",
            help="Default database to use",
        )

        # env subcommand
        env_parser = subparsers.add_parser("env", help="Generate a .env file")
        env_parser.add_argument(
            "--env",
            choices=["development", "staging", "production"],
            default="development",
            help="Environment to generate .env file for",
        )
        env_parser.add_argument("--output", default=".env", help="Output file path")
        env_parser.add_argument(
            "--db",
            choices=["postgres", "mysql", "sqlite"],
            default="postgres",
            help="Default database to use",
        )

    def handle(self, *args, **options):
        subcommand = options["subcommand"]
        if not subcommand:
            self.print_help("manage.py", "config")
            return

        if subcommand == "init":
            self.handle_init(options)
        elif subcommand == "generate":
            self.handle_generate(options)
        elif subcommand == "env":
            self.handle_env(options)

    def handle_init(self, options):
        """Initialize configuration files."""
        force = options["force"]
        env = options["env"]
        db = options["db"]

        # Get the project directory
        project_dir = self.get_project_dir()

        # Create the config directory if it doesn't exist
        config_dir = project_dir / "config"
        config_dir.mkdir(exist_ok=True)

        # Create the __init__.py file
        self.create_file(
            config_dir / "__init__.py",
            "from django_matt.config import configure, get_settings\n\n__all__ = ['configure', 'get_settings']\n",
            force,
        )

        # Create the settings.py file
        self.create_settings_file(project_dir, env, force, db=db)

        # Create the .env file
        if env == "all" or env == "development":
            self.create_env_file(project_dir, "development", force, db=db)
        if env == "all" or env == "staging":
            self.create_env_file(project_dir, "staging", force, db=db)
        if env == "all" or env == "production":
            self.create_env_file(project_dir, "production", force, db=db)

        self.stdout.write(
            self.style.SUCCESS("Configuration files initialized successfully")
        )

    def handle_generate(self, options):
        """Generate a settings.py file."""
        env = options["env"]
        components = options["components"]
        output = options["output"]
        db = options["db"]

        # Get the project directory
        project_dir = self.get_project_dir()

        # Create the settings.py file
        self.create_settings_file(project_dir, env, True, output, components, db=db)

        self.stdout.write(
            self.style.SUCCESS(f"Settings file generated successfully at {output}")
        )

    def handle_env(self, options):
        """Generate a .env file."""
        env = options["env"]
        output = options["output"]
        db = options["db"]

        # Get the project directory
        project_dir = self.get_project_dir()

        # Create the .env file
        self.create_env_file(project_dir, env, True, output, db=db)

        self.stdout.write(
            self.style.SUCCESS(f".env file generated successfully at {output}")
        )

    def get_project_dir(self) -> Path:
        """Get the project directory."""
        # Try to get the project directory from the Django settings
        try:
            from django.conf import settings

            return Path(settings.BASE_DIR)
        except (ImportError, AttributeError):
            # If that fails, use the current working directory
            return Path.cwd()

    def create_file(self, path: Path, content: str, force: bool = False) -> None:
        """Create a file with the given content."""
        if path.exists() and not force:
            self.stdout.write(
                self.style.WARNING(f"File {path} already exists, skipping")
            )
            return

        with open(path, "w") as f:
            f.write(content)

        self.stdout.write(self.style.SUCCESS(f"Created {path}"))

    def create_settings_file(
        self,
        project_dir: Path,
        env: str = "all",
        force: bool = False,
        output: str = "settings.py",
        components: list[str] = None,
        db: str = "postgres",
    ) -> None:
        """Create a settings.py file."""
        if components is None:
            components = ["database", "cache", "security", "performance"]

        # Get the project name from the directory name
        project_name = project_dir.name.replace("-", "_").lower()

        # Create the settings content
        if env == "all":
            content = self.get_settings_content(
                project_name, "development", components, db
            )
        else:
            content = self.get_settings_content(project_name, env, components, db)

        # Create the settings.py file
        settings_path = project_dir / output
        self.create_file(settings_path, content, force)

    def create_env_file(
        self,
        project_dir: Path,
        env: str = "development",
        force: bool = False,
        output: str = None,
        db: str = "postgres",
    ) -> None:
        """Create a .env file."""
        # Get the project name from the directory name
        project_name = project_dir.name.replace("-", "_").lower()

        # Create the .env content
        content = self.get_env_content(project_name, env, db)

        # Create the .env file
        if output is None:
            if env == "development":
                env_path = project_dir / ".env"
            else:
                env_path = project_dir / f".env.{env}"
        else:
            env_path = project_dir / output

        self.create_file(env_path, content, force)

        # Create .env.example if it doesn't exist
        if env == "development" and not (project_dir / ".env.example").exists():
            self.create_file(project_dir / ".env.example", content, force)

    def get_settings_content(
        self, project_name: str, env: str, components: list[str], db: str = "postgres"
    ) -> str:
        """Get the content for the settings.py file."""
        return f'''"""
{project_name.replace("_", " ").title()} settings.

Generated by Django Matt config management command.
"""

import os
from pathlib import Path

# Import the Django Matt configuration system
from django_matt.config import configure

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Determine the environment
ENVIRONMENT = os.environ.get("DJANGO_ENV", "{env}")

# Configure the application
settings = configure(
    # Specify the environment (development, staging, production)
    environment=ENVIRONMENT,
    
    # Specify the components to load
    components={components},
    
    # Specify additional settings
    extra_settings={{
        # Project-specific settings
        "ROOT_URLCONF": "{project_name}.urls",
        "WSGI_APPLICATION": "{project_name}.wsgi.application",
        
        # Add your project's apps
        "INSTALLED_APPS": [
            # Django Matt apps
            "django_matt",
            
            # Your project's apps
            "{project_name}.core",
        ],
        
        # Add your project's middleware
        "MIDDLEWARE": [
            # Django Matt middleware
            "django_matt.middleware.BenchmarkMiddleware",
        ],
        
        # Add your project's templates
        "TEMPLATES": [
            {{
                "DIRS": [
                    os.path.join(BASE_DIR, "{project_name}", "templates"),
                ],
            }},
        ],
        
        # Add your project's static files
        "STATICFILES_DIRS": [
            os.path.join(BASE_DIR, "{project_name}", "static"),
        ],
        
        # Add your project's media files
        "MEDIA_ROOT": os.path.join(BASE_DIR, "{project_name}", "media"),
        
        # Database type
        "DB_TYPE": "{db}",
    }},
    
    # Apply the settings to Django's settings module
    apply_to_django=True,
)

# You can access the settings directly if needed
DEBUG = settings["DEBUG"]
SECRET_KEY = settings["SECRET_KEY"]

# You can also add additional settings after configuration
SOME_CUSTOM_SETTING = "custom value"

# For demonstration purposes, print the environment
if DEBUG:
    print(f"Running in {{ENVIRONMENT}} environment")
'''

    def get_env_content(self, project_name: str, env: str, db: str = "postgres") -> str:
        """Get the content for the .env file."""
        import secrets

        db_settings = {
            "postgres": {
                "development": {
                    "ENGINE": "django.db.backends.postgresql",
                    "NAME": f"{project_name}_dev",
                    "USER": "postgres",
                    "PASSWORD": "",
                    "HOST": "localhost",
                    "PORT": "5432",
                },
                "staging": {
                    "ENGINE": "django.db.backends.postgresql",
                    "NAME": f"{project_name}_staging",
                    "USER": project_name,
                    "PASSWORD": "change_me",
                    "HOST": "localhost",
                    "PORT": "5432",
                },
                "production": {
                    "ENGINE": "django.db.backends.postgresql",
                    "NAME": project_name,
                    "USER": project_name,
                    "PASSWORD": "change_me",
                    "HOST": "localhost",
                    "PORT": "5432",
                },
            },
            "mysql": {
                "development": {
                    "ENGINE": "django.db.backends.mysql",
                    "NAME": f"{project_name}_dev",
                    "USER": "root",
                    "PASSWORD": "",
                    "HOST": "localhost",
                    "PORT": "3306",
                },
                "staging": {
                    "ENGINE": "django.db.backends.mysql",
                    "NAME": f"{project_name}_staging",
                    "USER": project_name,
                    "PASSWORD": "change_me",
                    "HOST": "localhost",
                    "PORT": "3306",
                },
                "production": {
                    "ENGINE": "django.db.backends.mysql",
                    "NAME": project_name,
                    "USER": project_name,
                    "PASSWORD": "change_me",
                    "HOST": "localhost",
                    "PORT": "3306",
                },
            },
            "sqlite": {
                "development": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": "db.sqlite3",
                },
                "staging": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": "db_staging.sqlite3",
                },
                "production": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": "db_production.sqlite3",
                },
            },
        }

        db_config = db_settings.get(db, db_settings["postgres"]).get(
            env, db_settings["postgres"]["development"]
        )

        if env == "development":
            return f"""# {project_name.replace("_", " ").title()} development environment variables
DJANGO_ENV=development
DJANGO_SECRET_KEY={secrets.token_hex(32)}
ALLOWED_HOSTS=localhost,127.0.0.1,[::1]

# Database settings
DB_TYPE={db}
DB_ENGINE={db_config["ENGINE"]}
DB_NAME={db_config["NAME"]}
{"DB_USER=" + db_config.get("USER", "") if "USER" in db_config else ""}
{"DB_PASSWORD=" + db_config.get("PASSWORD", "") if "PASSWORD" in db_config else ""}
{"DB_HOST=" + db_config.get("HOST", "") if "HOST" in db_config else ""}
{"DB_PORT=" + db_config.get("PORT", "") if "PORT" in db_config else ""}

# Cache settings
CACHE_BACKEND=django.core.cache.backends.locmem.LocMemCache
CACHE_LOCATION=django_matt
CACHE_TIMEOUT=300

# Django Matt settings
DJANGO_MATT_BENCHMARK_ENABLED=True
DJANGO_MATT_CACHE_ENABLED=True
DJANGO_MATT_CACHE_TIMEOUT=300

# PostgreSQL specific settings
DB_PGVECTOR_ENABLED=False
DB_POOL_ENABLED=False
"""
        elif env == "staging":
            return f"""# {project_name.replace("_", " ").title()} staging environment variables
DJANGO_ENV=staging
DJANGO_SECRET_KEY={secrets.token_hex(32)}
ALLOWED_HOSTS=staging.example.com

# Database settings
DB_TYPE={db}
DB_ENGINE={db_config["ENGINE"]}
DB_NAME={db_config["NAME"]}
{"DB_USER=" + db_config.get("USER", "") if "USER" in db_config else ""}
{"DB_PASSWORD=" + db_config.get("PASSWORD", "") if "PASSWORD" in db_config else ""}
{"DB_HOST=" + db_config.get("HOST", "") if "HOST" in db_config else ""}
{"DB_PORT=" + db_config.get("PORT", "") if "PORT" in db_config else ""}

# Cache settings
CACHE_BACKEND=django.core.cache.backends.redis.RedisCache
CACHE_LOCATION=redis://localhost:6379/1
CACHE_TIMEOUT=300
REDIS_URL=redis://localhost:6379/0

# Django Matt settings
DJANGO_MATT_BENCHMARK_ENABLED=True
DJANGO_MATT_CACHE_ENABLED=True
DJANGO_MATT_CACHE_TIMEOUT=300

# PostgreSQL specific settings
DB_PGVECTOR_ENABLED=False
DB_POOL_ENABLED=False
"""
        elif env == "production":
            return f"""# {project_name.replace("_", " ").title()} production environment variables
DJANGO_ENV=production
DJANGO_SECRET_KEY={secrets.token_hex(32)}
ALLOWED_HOSTS=example.com,www.example.com

# Database settings
DB_TYPE={db}
DB_ENGINE={db_config["ENGINE"]}
DB_NAME={db_config["NAME"]}
{"DB_USER=" + db_config.get("USER", "") if "USER" in db_config else ""}
{"DB_PASSWORD=" + db_config.get("PASSWORD", "") if "PASSWORD" in db_config else ""}
{"DB_HOST=" + db_config.get("HOST", "") if "HOST" in db_config else ""}
{"DB_PORT=" + db_config.get("PORT", "") if "PORT" in db_config else ""}

# Cache settings
CACHE_BACKEND=django.core.cache.backends.redis.RedisCache
CACHE_LOCATION=redis://localhost:6379/1
CACHE_TIMEOUT=3600
REDIS_URL=redis://localhost:6379/0

# Security settings
CSRF_COOKIE_SECURE=True
SESSION_COOKIE_SECURE=True
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True

# Django Matt settings
DJANGO_MATT_BENCHMARK_ENABLED=False
DJANGO_MATT_CACHE_ENABLED=True
DJANGO_MATT_CACHE_TIMEOUT=3600

# PostgreSQL specific settings
DB_PGVECTOR_ENABLED=False
DB_POOL_ENABLED=True
DB_POOL_MAX_CONNS=20
DB_POOL_MIN_CONNS=5
DB_POOL_MAX_IDLE=300

# Email settings
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=user@example.com
EMAIL_HOST_PASSWORD=change_me
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=noreply@example.com
"""
        else:
            return ""
