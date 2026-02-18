"""
Django Matt Production Middleware Stack.

Provides security headers, CORS, request IDs, structured logging, and timing.
Configure via settings.DJANGO_MATT["MIDDLEWARE_STACK"] or use the preset stacks.
"""

from django_matt.middleware.chaining import (
    APIExceptionMiddleware,
    DjangoMattMiddleware,
    JSONResponseMiddleware,
)
from django_matt.middleware.cors import CORSMiddleware
from django_matt.middleware.logging import RequestLoggingMiddleware
from django_matt.middleware.request_id import RequestIDMiddleware
from django_matt.middleware.security import SecurityHeadersMiddleware
from django_matt.middleware.timing import TimingMiddleware

PRODUCTION_STACK = [
    SecurityHeadersMiddleware,
    RequestIDMiddleware,
    CORSMiddleware,
    RequestLoggingMiddleware,
    TimingMiddleware,
]

DEVELOPMENT_STACK = [
    RequestIDMiddleware,
    CORSMiddleware,
    RequestLoggingMiddleware,
    TimingMiddleware,
]

__all__ = [
    "DjangoMattMiddleware",
    "APIExceptionMiddleware",
    "JSONResponseMiddleware",
    "SecurityHeadersMiddleware",
    "RequestIDMiddleware",
    "CORSMiddleware",
    "RequestLoggingMiddleware",
    "TimingMiddleware",
    "PRODUCTION_STACK",
    "DEVELOPMENT_STACK",
]
