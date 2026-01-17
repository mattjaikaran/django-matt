"""
API Key utilities for generation, hashing, and validation.
"""

import hashlib
import secrets
from typing import TYPE_CHECKING

from django.conf import settings
from django.http import HttpRequest

if TYPE_CHECKING:
    from .models import APIKey


class APIKeyConfig:
    """
    Configuration for API keys.

    Configure in settings.py:
        DJANGO_MATT_API_KEYS = {
            "PREFIX_LIVE": "sk_live_",
            "PREFIX_TEST": "sk_test_",
            "KEY_LENGTH": 32,
            "HASH_ALGORITHM": "sha256",
            "HEADER_NAME": "X-API-Key",
            "TRACK_USAGE": True,
            "RATE_LIMITING": True,
        }
    """

    def __init__(self):
        self._config = getattr(settings, "DJANGO_MATT_API_KEYS", {})

    @property
    def prefix_live(self) -> str:
        """Prefix for live/production keys."""
        return self._config.get("PREFIX_LIVE", "sk_live_")

    @property
    def prefix_test(self) -> str:
        """Prefix for test/development keys."""
        return self._config.get("PREFIX_TEST", "sk_test_")

    @property
    def key_length(self) -> int:
        """Length of the random part of the key (in bytes)."""
        return self._config.get("KEY_LENGTH", 32)

    @property
    def hash_algorithm(self) -> str:
        """Hash algorithm for storing keys."""
        return self._config.get("HASH_ALGORITHM", "sha256")

    @property
    def header_name(self) -> str:
        """HTTP header name for API key."""
        return self._config.get("HEADER_NAME", "X-API-Key")

    @property
    def query_param(self) -> str:
        """Query parameter name for API key (less secure, for webhooks)."""
        return self._config.get("QUERY_PARAM", "api_key")

    @property
    def track_usage(self) -> bool:
        """Whether to track usage statistics."""
        return self._config.get("TRACK_USAGE", False)

    @property
    def rate_limiting(self) -> bool:
        """Whether to enable rate limiting."""
        return self._config.get("RATE_LIMITING", True)

    @property
    def allow_query_param(self) -> bool:
        """Whether to allow API key in query parameter."""
        return self._config.get("ALLOW_QUERY_PARAM", False)


# Global config instance
api_key_config = APIKeyConfig()


def generate_api_key(is_test: bool = False) -> str:
    """
    Generate a new API key.

    Args:
        is_test: If True, generate a test key with test prefix

    Returns:
        Full API key string (e.g., "sk_live_abc123...")
    """
    prefix = api_key_config.prefix_test if is_test else api_key_config.prefix_live
    random_part = secrets.token_urlsafe(api_key_config.key_length)
    return f"{prefix}{random_part}"


def hash_api_key(key: str) -> str:
    """
    Hash an API key for secure storage.

    Args:
        key: Full API key string

    Returns:
        Hashed key string
    """
    algorithm = api_key_config.hash_algorithm
    return hashlib.new(algorithm, key.encode()).hexdigest()


def get_key_prefix(key: str, length: int = 12) -> str:
    """
    Extract the prefix from an API key for display.

    Args:
        key: Full API key string
        length: Number of characters to include in prefix

    Returns:
        Key prefix (e.g., "sk_live_abc1")
    """
    return key[:length] if len(key) > length else key


def mask_api_key(key: str) -> str:
    """
    Mask an API key for safe display.

    Args:
        key: Full API key string

    Returns:
        Masked key (e.g., "sk_live_abc1...xyz9")
    """
    if len(key) <= 16:
        return key[:4] + "..." + key[-4:]
    return key[:12] + "..." + key[-4:]


def get_api_key_from_request(request: HttpRequest) -> str | None:
    """
    Extract API key from request.

    Checks in order:
    1. X-API-Key header (default)
    2. Authorization header with "Bearer" or "ApiKey" scheme
    3. Query parameter (if enabled in config)

    Args:
        request: Django HTTP request

    Returns:
        API key string or None if not found
    """
    # 1. Check custom header (X-API-Key)
    header_name = api_key_config.header_name
    key = request.headers.get(header_name)
    if key:
        return key

    # Also check META format for older Django versions
    meta_key = f"HTTP_{header_name.upper().replace('-', '_')}"
    key = request.META.get(meta_key)
    if key:
        return key

    # 2. Check Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")

    if auth_header:
        # Support "Bearer <key>" format
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()
        # Support "ApiKey <key>" format
        if auth_header.startswith("ApiKey "):
            return auth_header[7:].strip()

    # 3. Check query parameter (if allowed)
    if api_key_config.allow_query_param:
        key = request.GET.get(api_key_config.query_param)
        if key:
            return key

    return None


def get_client_ip(request: HttpRequest) -> str:
    """
    Get the client IP address from request.

    Handles proxy headers (X-Forwarded-For, etc.)
    """
    # Check for proxy headers
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        # Take the first IP in the chain
        return x_forwarded_for.split(",")[0].strip()

    x_real_ip = request.META.get("HTTP_X_REAL_IP")
    if x_real_ip:
        return x_real_ip.strip()

    return request.META.get("REMOTE_ADDR", "")


def create_api_key(
    user,
    name: str,
    is_test: bool = False,
    scopes: list[str] | None = None,
    expires_at=None,
    plan: str = "free",
    allowed_ips: list[str] | None = None,
) -> tuple["APIKey", str]:
    """
    Create a new API key for a user.

    Args:
        user: User who owns the key
        name: Friendly name for the key
        is_test: Whether this is a test key
        scopes: List of permission scopes
        expires_at: Optional expiration datetime
        plan: Plan tier for rate limiting
        allowed_ips: Optional list of allowed IP addresses

    Returns:
        Tuple of (APIKey instance, raw key string)

    Example:
        api_key, raw_key = create_api_key(
            user=request.user,
            name="Production API",
            scopes=["read:*", "write:posts"],
        )
        # raw_key is only available now - save it securely!
    """
    from .models import APIKey, PLAN_RATE_LIMITS

    # Generate the key
    raw_key = generate_api_key(is_test=is_test)
    key_hash = hash_api_key(raw_key)
    prefix = get_key_prefix(raw_key)

    # Get rate limits for plan
    rate_limits = PLAN_RATE_LIMITS.get(plan, PLAN_RATE_LIMITS["free"])

    # Create the key
    api_key = APIKey.objects.create(
        user=user,
        name=name,
        prefix=prefix,
        key_hash=key_hash,
        is_test=is_test,
        scopes=scopes or [],
        expires_at=expires_at,
        plan=plan,
        rate_limit=rate_limits["rate_limit"],
        rate_limit_period=rate_limits["rate_limit_period"],
        allowed_ips=allowed_ips or [],
    )

    return api_key, raw_key


async def acreate_api_key(
    user,
    name: str,
    is_test: bool = False,
    scopes: list[str] | None = None,
    expires_at=None,
    plan: str = "free",
    allowed_ips: list[str] | None = None,
) -> tuple["APIKey", str]:
    """Async version of create_api_key."""
    from .models import APIKey, PLAN_RATE_LIMITS

    raw_key = generate_api_key(is_test=is_test)
    key_hash = hash_api_key(raw_key)
    prefix = get_key_prefix(raw_key)

    rate_limits = PLAN_RATE_LIMITS.get(plan, PLAN_RATE_LIMITS["free"])

    api_key = APIKey(
        user=user,
        name=name,
        prefix=prefix,
        key_hash=key_hash,
        is_test=is_test,
        scopes=scopes or [],
        expires_at=expires_at,
        plan=plan,
        rate_limit=rate_limits["rate_limit"],
        rate_limit_period=rate_limits["rate_limit_period"],
        allowed_ips=allowed_ips or [],
    )
    await api_key.asave()

    return api_key, raw_key


def rotate_api_key(api_key: "APIKey") -> tuple["APIKey", str]:
    """
    Rotate an API key (generate new key, keep same settings).

    The old key is revoked and a new one is created with the same settings.

    Args:
        api_key: Existing API key to rotate

    Returns:
        Tuple of (new APIKey instance, new raw key string)
    """
    # Revoke the old key
    api_key.revoke()

    # Create a new key with same settings
    return create_api_key(
        user=api_key.user,
        name=api_key.name,
        is_test=api_key.is_test,
        scopes=api_key.scopes,
        expires_at=api_key.expires_at,
        plan=api_key.plan,
        allowed_ips=api_key.allowed_ips,
    )


async def arotate_api_key(api_key: "APIKey") -> tuple["APIKey", str]:
    """Async version of rotate_api_key."""
    await api_key.arevoke()

    return await acreate_api_key(
        user=api_key.user,
        name=api_key.name,
        is_test=api_key.is_test,
        scopes=api_key.scopes,
        expires_at=api_key.expires_at,
        plan=api_key.plan,
        allowed_ips=api_key.allowed_ips,
    )


def generate_webhook_secret() -> str:
    """Generate a secret for webhook signing."""
    return f"whsec_{secrets.token_urlsafe(32)}"
