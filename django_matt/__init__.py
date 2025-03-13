"""
Django Matt - A modern Django API framework

Django Matt is a custom Django API framework that combines the best features of
Django Rest Framework, Django Ninja, Django Ninja Extra, and other modern frameworks
while adding custom DX tools and performance optimizations.
"""

__version__ = "0.1.0"

# Import core components for easy access
from django_matt.core.controller import APIController, Controller, CRUDController
from django_matt.core.router import APIRouter, delete, get, patch, post, put
from django_matt.core.schema import Schema

# Import utility components
from django_matt.utils.errors import ErrorHandler, ErrorMiddleware, error_handler
from django_matt.utils.hot_reload import (
    HotReloadMiddleware,
    start_hot_reloading,
    stop_hot_reloading,
)
from django_matt.utils.performance import (
    BenchmarkMiddleware,
    FastJsonResponse,
    MessagePackResponse,
    StreamingJsonResponse,
    benchmark,
    cache_manager,
    stream_json_list,
)

# Create a default router instance
api = APIRouter()

# Export commonly used components
__all__ = [
    # Core components
    "APIRouter",
    "Controller",
    "APIController",
    "CRUDController",
    "Schema",
    "api",
    "get",
    "post",
    "put",
    "patch",
    "delete",
    # Error handling
    "ErrorHandler",
    "ErrorMiddleware",
    "error_handler",
    # Hot reloading
    "HotReloadMiddleware",
    "start_hot_reloading",
    "stop_hot_reloading",
    # Performance
    "FastJsonResponse",
    "MessagePackResponse",
    "StreamingJsonResponse",
    "benchmark",
    "cache_manager",
    "BenchmarkMiddleware",
    "stream_json_list",
]
