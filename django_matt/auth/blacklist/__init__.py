"""
Token blacklisting for JWT revocation.

Supports three backends:
- NullBlacklistBackend (default): no-op, blacklisting disabled
- CacheBlacklistBackend: uses Django cache framework
- DatabaseBlacklistBackend: uses BlacklistedToken model

Configure via DJANGO_MATT_JWT settings:
    DJANGO_MATT_JWT = {
        "BLACKLIST_BACKEND": "cache",  # or "database" or "null"
        "BLACKLIST_CACHE_PREFIX": "jwt_blacklist:",
        "BLACKLIST_AFTER_ROTATION": True,
    }
"""

from django_matt.auth.blacklist.backends import (
    CacheBlacklistBackend,
    DatabaseBlacklistBackend,
    NullBlacklistBackend,
)
from django_matt.auth.blacklist.config import BlacklistConfig, blacklist_config
from django_matt.auth.blacklist.core import (
    ablacklist_token,
    ais_token_blacklisted,
    aprune_expired_tokens,
    blacklist_token,
    is_token_blacklisted,
    prune_expired_tokens,
    reset_backend,
)
from django_matt.auth.blacklist.models import BlacklistedToken

__all__ = [
    # Public API
    "blacklist_token",
    "ablacklist_token",
    "is_token_blacklisted",
    "ais_token_blacklisted",
    "prune_expired_tokens",
    "aprune_expired_tokens",
    "reset_backend",
    # Config
    "BlacklistConfig",
    "blacklist_config",
    # Backends
    "NullBlacklistBackend",
    "CacheBlacklistBackend",
    "DatabaseBlacklistBackend",
    # Model
    "BlacklistedToken",
]
