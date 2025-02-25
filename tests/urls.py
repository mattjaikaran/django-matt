"""
URL patterns for testing Django Matt.
"""

from django_matt import (
    APIRouter,
    FastJsonResponse,
    MessagePackResponse,
    StreamingJsonResponse,
    benchmark,
    cache_manager,
    stream_json_list,
)

# Create a router
router = APIRouter()


# Test views
@router.get("api/json/")
def json_view(request):
    """Test view that returns a JSON response."""
    return FastJsonResponse({"message": "Hello, World!"})


@router.get("api/msgpack/")
def msgpack_view(request):
    """Test view that returns a MessagePack response."""
    return MessagePackResponse({"message": "Hello, World!"})


@router.get("api/streaming/")
def streaming_view(request):
    """Test view that returns a streaming response."""

    def items_generator():
        for i in range(5):
            yield {"id": i, "name": f"Item {i}"}

    return StreamingJsonResponse(streaming_content=stream_json_list(items_generator()))


@router.get("api/cached/")
@cache_manager.cache_response(timeout=60)
@benchmark.measure("cached_view")
def cached_view(request):
    """Test view that returns a cached response."""
    import time

    time.sleep(0.01)  # Simulate a slow operation
    return FastJsonResponse({"message": "This response is cached."})


# Create URL patterns
urlpatterns = router.get_urls()
