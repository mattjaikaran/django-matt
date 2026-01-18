"""
Throttling and rate limiting for django-matt.

Provides rate limiting capabilities for API endpoints:
- AnonRateThrottle: Rate limit anonymous users by IP
- UserRateThrottle: Rate limit authenticated users
- ScopedRateThrottle: Different limits per endpoint scope

Example usage:
    from django_matt.throttling import throttle, AnonRateThrottle, UserRateThrottle

    @api.get("/public")
    @throttle(rate="100/hour")
    def public_endpoint(request):
        return {"message": "Hello"}

    @api.get("/user")
    @throttle(UserRateThrottle, rate="1000/day")
    def user_endpoint(request):
        return {"message": "Hello user"}
"""

from django_matt.throttling.backends import (
    BaseBackend,
    InMemoryBackend,
    RedisBackend,
)
from django_matt.throttling.base import BaseThrottle
from django_matt.throttling.decorators import throttle
from django_matt.throttling.middleware import ThrottleMiddleware
from django_matt.throttling.throttles import (
    AnonRateThrottle,
    ScopedRateThrottle,
    UserRateThrottle,
)

__all__ = [
    # Base
    "BaseThrottle",
    # Throttle classes
    "AnonRateThrottle",
    "UserRateThrottle",
    "ScopedRateThrottle",
    # Decorators
    "throttle",
    # Backends
    "BaseBackend",
    "InMemoryBackend",
    "RedisBackend",
    # Middleware
    "ThrottleMiddleware",
]
