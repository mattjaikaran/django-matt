"""
Example settings.py file using the Django Matt configuration system.

This file demonstrates how to use the Django Matt configuration system
to create a clean and organized settings.py file.
"""

import os
from pathlib import Path

# Import the Django Matt configuration system
from django_matt.config import configure

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Determine the environment
ENVIRONMENT = os.environ.get("DJANGO_ENV", "development")

# Configure the application
settings = configure(
    # Specify the environment (development, staging, production)
    environment=ENVIRONMENT,
    # Specify the components to load
    components=[
        "database",
        "cache",
        "security",
        "performance",
    ],
    # Specify additional settings
    extra_settings={
        # Project-specific settings
        "ROOT_URLCONF": "myproject.urls",
        "WSGI_APPLICATION": "myproject.wsgi.application",
        # Add your project's apps
        "INSTALLED_APPS": [
            "myproject.apps.core",
            "myproject.apps.users",
            "myproject.apps.api",
        ],
        # Add your project's middleware
        "MIDDLEWARE": [
            "myproject.middleware.custom_middleware",
        ],
        # Add your project's templates
        "TEMPLATES": [
            {
                "DIRS": [
                    os.path.join(BASE_DIR, "myproject", "templates"),
                ],
            },
        ],
        # Add your project's static files
        "STATICFILES_DIRS": [
            os.path.join(BASE_DIR, "myproject", "static"),
        ],
        # Add your project's media files
        "MEDIA_ROOT": os.path.join(BASE_DIR, "myproject", "media"),
    },
    # Apply the settings to Django's settings module
    apply_to_django=True,
)

# You can access the settings directly if needed
DEBUG = settings["DEBUG"]
SECRET_KEY = settings["SECRET_KEY"]

# You can also add additional settings after configuration
SOME_CUSTOM_SETTING = "custom value"

# For demonstration purposes, print the environment
print(f"Running in {ENVIRONMENT} environment")
