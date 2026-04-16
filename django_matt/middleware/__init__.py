"""
Django Matt Production Middleware Stack.

Provides security headers, CORS, request IDs, structured logging, and timing.
Configure via settings.DJANGO_MATT["MIDDLEWARE_STACK"] or use the preset stacks.
"""

from django_matt.errors.middleware import ErrorEnhancementMiddleware
from django_matt.middleware.builtins import (
    ScopedAuthMiddleware,
    ScopedCacheMiddleware,
    ScopedCorsMiddleware,
    ScopedRateLimitMiddleware,
)
from django_matt.middleware.chaining import (
    APIExceptionMiddleware,
    DjangoMattMiddleware,
    JSONResponseMiddleware,
)
from django_matt.middleware.cors import CORSMiddleware
from django_matt.middleware.logging import RequestLoggingMiddleware
from django_matt.middleware.request_id import RequestIDMiddleware
from django_matt.middleware.scoped import (
    MiddlewareStack,
    RouteMiddleware,
    skip_middleware,
    use_middleware,
)
from django_matt.middleware.security import SecurityHeadersMiddleware
from django_matt.middleware.timing import TimingMiddleware

# ErrorEnhancementMiddleware is first (outermost) so it catches exceptions
# raised by every downstream middleware and view. Without it, Django falls
# back to the bare "Server Error (500)" template with no detail.
PRODUCTION_STACK = [
    ErrorEnhancementMiddleware,
    SecurityHeadersMiddleware,
    RequestIDMiddleware,
    CORSMiddleware,
    RequestLoggingMiddleware,
    TimingMiddleware,
]

DEVELOPMENT_STACK = [
    ErrorEnhancementMiddleware,
    RequestIDMiddleware,
    CORSMiddleware,
    RequestLoggingMiddleware,
    TimingMiddleware,
]

__all__ = [
    "DjangoMattMiddleware",
    "APIExceptionMiddleware",
    "JSONResponseMiddleware",
    "ErrorEnhancementMiddleware",
    "SecurityHeadersMiddleware",
    "RequestIDMiddleware",
    "CORSMiddleware",
    "RequestLoggingMiddleware",
    "TimingMiddleware",
    "PRODUCTION_STACK",
    "DEVELOPMENT_STACK",
    "RouteMiddleware",
    "MiddlewareStack",
    "use_middleware",
    "skip_middleware",
    "ScopedCorsMiddleware",
    "ScopedRateLimitMiddleware",
    "ScopedCacheMiddleware",
    "ScopedAuthMiddleware",
]
