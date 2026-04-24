"""Typed HTTP client generation for Python and TypeScript from API routes."""

from django_matt.rpc.auth import (
    APIKeyAuth,
    AuthStrategy,
    BasicAuth,
    BearerAuth,
    CompositeAuth,
)
from django_matt.rpc.client import RPCClient, TypedRPCClient
from django_matt.rpc.errors import (
    RPCAuthError,
    RPCConnectionError,
    RPCError,
    RPCNotFoundError,
    RPCTimeoutError,
    RPCValidationError,
)
from django_matt.rpc.generator import generate_python_client, generate_typescript_client
from django_matt.rpc.proxy import RPCProxy

__all__ = [
    "APIKeyAuth",
    "AuthStrategy",
    "BasicAuth",
    "BearerAuth",
    "CompositeAuth",
    "RPCAuthError",
    "RPCClient",
    "RPCConnectionError",
    "RPCError",
    "RPCNotFoundError",
    "RPCProxy",
    "RPCTimeoutError",
    "RPCValidationError",
    "TypedRPCClient",
    "generate_python_client",
    "generate_typescript_client",
]
