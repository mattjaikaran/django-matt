"""
Django settings for e-commerce API.

Production-quality configuration with django-matt.
"""

import os
import re
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-dev-key-change-me")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")


# Application definition

INSTALLED_APPS = [
    # Django Unfold admin (must be before django.contrib.admin)
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # Third-party
    "mptt",
    # django-matt
    "django_matt",
    # Local apps
    "ecommerce.catalog",
    "ecommerce.cart",
    "ecommerce.orders",
    "ecommerce.payments",
    "ecommerce.users",
    "ecommerce.reviews",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # django-matt middleware
    "django_matt.negotiation.ContentNegotiationMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgres://ecommerce:ecommerce_secret@localhost:5432/ecommerce"
)

# Parse DATABASE_URL
db_match = re.match(r"postgres://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", DATABASE_URL)
if db_match:
    DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME = db_match.groups()
else:
    DB_USER = "ecommerce"
    DB_PASSWORD = "ecommerce_secret"
    DB_HOST = "localhost"
    DB_PORT = "5432"
    DB_NAME = "ecommerce"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": DB_NAME,
        "USER": DB_USER,
        "PASSWORD": DB_PASSWORD,
        "HOST": DB_HOST,
        "PORT": DB_PORT,
        "CONN_MAX_AGE": 60,
        "OPTIONS": {
            "connect_timeout": 10,
        },
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"


# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Custom User Model
AUTH_USER_MODEL = "users.User"


# Redis Cache
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "ecommerce",
    }
}


# Celery Configuration
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True


# Stripe Configuration
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")


# JWT Configuration (django-matt)
MATT_JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", SECRET_KEY)
MATT_JWT_ACCESS_TOKEN_LIFETIME = int(
    os.environ.get("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", 60)
)  # minutes
MATT_JWT_REFRESH_TOKEN_LIFETIME = (
    int(os.environ.get("JWT_REFRESH_TOKEN_LIFETIME_DAYS", 7)) * 24 * 60
)  # days to minutes


# Email Configuration
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@example.com")


# Application Settings
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# Tax Configuration
TAX_RATE_DEFAULT = float(os.environ.get("TAX_RATE_DEFAULT", 0.0875))

# Shipping Configuration
SHIPPING_FLAT_RATE = float(os.environ.get("SHIPPING_FLAT_RATE", 5.99))
FREE_SHIPPING_THRESHOLD = float(os.environ.get("FREE_SHIPPING_THRESHOLD", 50.00))


# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "ecommerce": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
    },
}


# Django Unfold Admin Configuration
UNFOLD = {
    "SITE_TITLE": "E-Commerce Admin",
    "SITE_HEADER": "E-Commerce API",
    "SITE_SYMBOL": "shopping_cart",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "COLORS": {
        "primary": {
            "50": "250 245 255",
            "100": "243 232 255",
            "200": "233 213 255",
            "300": "216 180 254",
            "400": "192 132 252",
            "500": "168 85 247",
            "600": "147 51 234",
            "700": "126 34 206",
            "800": "107 33 168",
            "900": "88 28 135",
            "950": "59 7 100",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": "Dashboard",
                "separator": True,
                "items": [
                    {
                        "title": "Dashboard",
                        "icon": "dashboard",
                        "link": "/admin/",
                    },
                ],
            },
            {
                "title": "Catalog",
                "separator": True,
                "items": [
                    {
                        "title": "Products",
                        "icon": "inventory_2",
                        "link": "/admin/catalog/product/",
                    },
                    {
                        "title": "Categories",
                        "icon": "category",
                        "link": "/admin/catalog/category/",
                    },
                    {
                        "title": "Inventory",
                        "icon": "warehouse",
                        "link": "/admin/catalog/inventory/",
                    },
                ],
            },
            {
                "title": "Sales",
                "separator": True,
                "items": [
                    {
                        "title": "Orders",
                        "icon": "receipt_long",
                        "link": "/admin/orders/order/",
                    },
                    {
                        "title": "Payments",
                        "icon": "payments",
                        "link": "/admin/payments/payment/",
                    },
                    {
                        "title": "Coupons",
                        "icon": "confirmation_number",
                        "link": "/admin/orders/coupon/",
                    },
                ],
            },
            {
                "title": "Customers",
                "separator": True,
                "items": [
                    {
                        "title": "Users",
                        "icon": "people",
                        "link": "/admin/users/user/",
                    },
                    {
                        "title": "Reviews",
                        "icon": "rate_review",
                        "link": "/admin/reviews/review/",
                    },
                ],
            },
        ],
    },
}
