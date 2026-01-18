"""
API Key authentication for django-matt.

Provides a complete API key system with:
- Live/test keys (like Stripe's sk_live_ / sk_test_)
- Scoped permissions
- Rate limiting by plan tier
- Usage tracking and analytics
- Key management endpoints

Quick Start:
    # 1. Add middleware (optional - for global auth)
    MIDDLEWARE = [
        ...
        'django_matt.auth.api_keys.APIKeyAuthenticationMiddleware',
        'django_matt.auth.api_keys.APIKeyRateLimitMiddleware',
    ]

    # 2. Register management endpoints
    from django_matt.auth.api_keys import APIKeyController
    api.register_controller(APIKeyController, prefix="/api/keys")

    # 3. Protect your endpoints
    from django_matt.auth.api_keys import api_key_required, requires_scope

    @api.get("/data")
    @api_key_required
    async def get_data(request):
        return {"user": request.user.email}

    @api.post("/posts")
    @api_key_required
    @requires_scope("write:posts")
    async def create_post(request, data: PostSchema):
        ...

Configuration (settings.py):
    DJANGO_MATT_API_KEYS = {
        "PREFIX_LIVE": "sk_live_",      # Prefix for production keys
        "PREFIX_TEST": "sk_test_",      # Prefix for test keys
        "KEY_LENGTH": 32,               # Random bytes in key
        "HEADER_NAME": "X-API-Key",     # HTTP header name
        "TRACK_USAGE": False,           # Enable usage tracking
        "RATE_LIMITING": True,          # Enable rate limiting
        "ALLOW_QUERY_PARAM": False,     # Allow ?api_key= (less secure)
    }
"""

# Config
# Controllers
from .controllers import APIKeyController

# Decorators
from .decorators import (
    api_key_optional,
    api_key_required,
    requires_live_key,
    requires_plan,
    requires_scope,
)

# Middleware
from .middleware import (
    APIKeyAuthenticationMiddleware,
    APIKeyRateLimitMiddleware,
    APIKeyUsageTrackingMiddleware,
)

# Models
from .models import PLAN_RATE_LIMITS, APIKey, APIKeyUsage

# Schemas
from .schemas import (
    APIKeyCreatedResponse,
    APIKeyCreateRequest,
    APIKeyListResponse,
    APIKeyResponse,
    APIKeyUpdateRequest,
    ExportRequest,
    ExportResponse,
    UsageRecord,
    UsageResponse,
    UsageSummary,
)

# Utilities
from .utils import (
    APIKeyConfig,
    acreate_api_key,
    api_key_config,
    arotate_api_key,
    create_api_key,
    generate_api_key,
    generate_webhook_secret,
    get_api_key_from_request,
    get_client_ip,
    get_key_prefix,
    hash_api_key,
    mask_api_key,
    rotate_api_key,
)

__all__ = [
    # Config
    "APIKeyConfig",
    "api_key_config",
    # Models
    "APIKey",
    "APIKeyUsage",
    "PLAN_RATE_LIMITS",
    # Utilities
    "generate_api_key",
    "hash_api_key",
    "get_key_prefix",
    "mask_api_key",
    "get_api_key_from_request",
    "get_client_ip",
    "create_api_key",
    "acreate_api_key",
    "rotate_api_key",
    "arotate_api_key",
    "generate_webhook_secret",
    # Decorators
    "api_key_required",
    "api_key_optional",
    "requires_scope",
    "requires_live_key",
    "requires_plan",
    # Middleware
    "APIKeyAuthenticationMiddleware",
    "APIKeyRateLimitMiddleware",
    "APIKeyUsageTrackingMiddleware",
    # Schemas
    "APIKeyCreateRequest",
    "APIKeyUpdateRequest",
    "APIKeyResponse",
    "APIKeyCreatedResponse",
    "APIKeyListResponse",
    "UsageRecord",
    "UsageSummary",
    "UsageResponse",
    "ExportRequest",
    "ExportResponse",
    # Controllers
    "APIKeyController",
]
