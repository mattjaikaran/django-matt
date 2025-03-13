"""
Example demonstrating Django Matt's advanced performance features.

This example shows how to use the advanced performance features of Django Matt
including MessagePack serialization, caching, and streaming responses.

To run this example:
1. Install Django and Django Matt
2. Install optional dependencies: pip install msgpack redis
3. Run this script with Python

"""

import os
import random
import sys
import time

import django
from django.conf import settings
from django.core.cache import cache
from django.core.wsgi import get_wsgi_application
from django.http import HttpResponse, JsonResponse
from django.urls import path

# Add the parent directory to the path so we can import django_matt
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Configure Django settings
if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY="django-matt-example",
        ROOT_URLCONF=__name__,
        MIDDLEWARE=[
            "django.middleware.common.CommonMiddleware",
            "django_matt.utils.performance.BenchmarkMiddleware",
        ],
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
        ],
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "APP_DIRS": True,
            }
        ],
        DJANGO_MATT_BENCHMARK_ENABLED=True,
        DJANGO_MATT_CACHE_ENABLED=True,
        DJANGO_MATT_CACHE_TIMEOUT=60,  # 1 minute
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            }
        },
    )
    django.setup()

# Import Django Matt components
from django_matt import (
    APIRouter,
    FastJsonResponse,
    MessagePackResponse,
    StreamingJsonResponse,
    benchmark,
    cache_manager,
    stream_json_list,
)
from django_matt.utils.performance import HAS_MSGPACK, HAS_ORJSON, HAS_UJSON

# Create a router
router = APIRouter()


# Generate a large dataset for testing
def generate_large_dataset(size=10000):
    """Generate a large dataset for testing."""
    return [
        {
            "id": i,
            "name": f"Item {i}",
            "description": f"This is item {i} with a somewhat longer description to make the JSON larger.",
            "tags": [f"tag{j}" for j in range(1, 6)],
            "metadata": {
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-02T00:00:00Z",
                "status": random.choice(["active", "inactive", "pending"]),
                "score": random.random() * 100,
                "attributes": {
                    "color": random.choice(["red", "green", "blue", "yellow"]),
                    "size": random.choice(["small", "medium", "large"]),
                    "weight": random.random() * 10,
                },
            },
        }
        for i in range(1, size + 1)
    ]


# Create a large dataset
LARGE_DATASET = generate_large_dataset()


# Example endpoint using standard JsonResponse
@router.get("api/standard-json/")
@benchmark.measure("standard_json")
async def standard_json(request):
    """Return a large dataset using standard JsonResponse."""
    return JsonResponse(
        {
            "data": LARGE_DATASET[:1000],  # Limit to 1000 items for standard JSON
            "count": 1000,
        }
    )


# Example endpoint using FastJsonResponse
@router.get("api/fast-json/")
@benchmark.measure("fast_json")
async def fast_json(request):
    """Return a large dataset using FastJsonResponse."""
    return FastJsonResponse(
        {
            "data": LARGE_DATASET[:1000],  # Limit to 1000 items for comparison
            "count": 1000,
        }
    )


# Example endpoint using MessagePackResponse
@router.get("api/msgpack/")
@benchmark.measure("msgpack")
async def msgpack_response(request):
    """Return a large dataset using MessagePackResponse."""
    if not HAS_MSGPACK:
        return JsonResponse(
            {
                "error": 'MessagePack is not installed. Install it with "pip install msgpack".'
            },
            status=500,
        )

    return MessagePackResponse(
        {
            "data": LARGE_DATASET,
            "count": len(LARGE_DATASET),
        }
    )


# Example endpoint using StreamingJsonResponse
@router.get("api/streaming-json/")
@benchmark.measure("streaming_json")
async def streaming_json(request):
    """Return a large dataset using StreamingJsonResponse."""

    # Create a generator that yields items from the dataset
    def items_generator():
        for item in LARGE_DATASET:
            yield item

    # Create a streaming response
    return StreamingJsonResponse(streaming_content=stream_json_list(items_generator()))


# Example endpoint with caching
@router.get("api/cached-response/")
@cache_manager.cache_response(timeout=30)  # Cache for 30 seconds
@benchmark.measure("cached_response")
async def cached_response(request):
    """Return a cached response."""
    # Simulate a slow operation
    time.sleep(1)

    return FastJsonResponse(
        {
            "message": "This response is cached for 30 seconds.",
            "timestamp": time.time(),
        }
    )


# Example endpoint to invalidate the cache
@router.get("api/invalidate-cache/")
async def invalidate_cache(request):
    """Invalidate the cached response."""
    cache_manager.invalidate("cached_response")

    return FastJsonResponse(
        {
            "message": "Cache invalidated.",
            "timestamp": time.time(),
        }
    )


# Example endpoint with cached database query
@router.get("api/cached-query/")
@benchmark.measure("cached_query")
async def cached_query(request):
    """Simulate a cached database query."""
    # Get the query parameter
    status = request.GET.get("status", "active")

    # Try to get the result from the cache
    cache_key = f"query_result:{status}"
    result = cache.get(cache_key)

    if result is None:
        # Simulate a slow database query
        time.sleep(0.5)

        # Filter the dataset
        result = [
            item for item in LARGE_DATASET if item["metadata"]["status"] == status
        ]

        # Cache the result for 60 seconds
        cache.set(cache_key, result, 60)

    return FastJsonResponse(
        {
            "data": result[:100],  # Return only the first 100 items
            "count": len(result),
            "status": status,
            "cached": result is not None,
        }
    )


# Example endpoint to benchmark different serialization formats
@router.get("api/benchmark-formats/")
async def benchmark_formats(request):
    """Benchmark different serialization formats."""
    data = {
        "data": LARGE_DATASET[:100],  # Use a smaller dataset for the benchmark
        "count": 100,
    }

    # Benchmark standard JSON
    start_time = time.time()
    standard_json = JsonResponse(data).content
    standard_json_time = (time.time() - start_time) * 1000

    # Benchmark FastJSON
    start_time = time.time()
    fast_json = FastJsonResponse(data).content
    fast_json_time = (time.time() - start_time) * 1000

    # Benchmark MessagePack if available
    msgpack_time = None
    msgpack_size = None
    if HAS_MSGPACK:
        start_time = time.time()
        msgpack_response = MessagePackResponse(data).content
        msgpack_time = (time.time() - start_time) * 1000
        msgpack_size = len(msgpack_response)

    return FastJsonResponse(
        {
            "benchmark_results": {
                "standard_json": {
                    "time_ms": standard_json_time,
                    "size_bytes": len(standard_json),
                },
                "fast_json": {
                    "time_ms": fast_json_time,
                    "size_bytes": len(fast_json),
                    "library": (
                        "orjson" if HAS_ORJSON else ("ujson" if HAS_UJSON else "json")
                    ),
                },
                "msgpack": (
                    {
                        "time_ms": msgpack_time,
                        "size_bytes": msgpack_size,
                        "available": HAS_MSGPACK,
                    }
                    if HAS_MSGPACK
                    else {
                        "available": False,
                    }
                ),
            }
        }
    )


# Example endpoint to get benchmark results
@router.get("api/benchmark-results/")
async def benchmark_results(request):
    """Return the benchmark results."""
    return FastJsonResponse(benchmark.get_report())


# Create URL patterns
urlpatterns = router.get_urls()


# Add a simple HTML page to demonstrate the advanced performance features
def index_view(request):
    """Simple HTML page to demonstrate the advanced performance features."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Django Matt Advanced Performance Demo</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            h1 { color: #333; }
            .card { background: #f5f5f5; padding: 20px; margin-bottom: 20px; border-radius: 5px; }
            button { background: #4CAF50; color: white; border: none; padding: 10px 15px; cursor: pointer; margin-right: 10px; margin-bottom: 10px; }
            pre { background: #f9f9f9; padding: 10px; overflow: auto; }
            #results { margin-top: 20px; }
            .benchmark-info { background: #e3f2fd; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #f2f2f2; }
            .feature-section { margin-bottom: 30px; }
            .feature-title { color: #2196F3; }
        </style>
    </head>
    <body>
        <h1>Django Matt Advanced Performance Demo</h1>
        
        <div class="benchmark-info">
            <h3>Library Information:</h3>
            <p>orjson available: <strong>%s</strong></p>
            <p>ujson available: <strong>%s</strong></p>
            <p>msgpack available: <strong>%s</strong></p>
        </div>
        
        <div class="card">
            <div class="feature-section">
                <h2 class="feature-title">1. Serialization Formats</h2>
                <p>Compare different serialization formats for performance and size.</p>
                <button onclick="testStandardJson()">Standard JSON</button>
                <button onclick="testFastJson()">Fast JSON</button>
                <button onclick="testMessagePack()">MessagePack</button>
                <button onclick="benchmarkFormats()">Benchmark Formats</button>
            </div>
            
            <div class="feature-section">
                <h2 class="feature-title">2. Streaming Responses</h2>
                <p>Stream large datasets without loading everything into memory.</p>
                <button onclick="testStreamingJson()">Streaming JSON</button>
            </div>
            
            <div class="feature-section">
                <h2 class="feature-title">3. Caching</h2>
                <p>Cache responses and database queries for better performance.</p>
                <button onclick="testCachedResponse()">Cached Response</button>
                <button onclick="invalidateCache()">Invalidate Cache</button>
                <button onclick="testCachedQuery('active')">Cached Query (Active)</button>
                <button onclick="testCachedQuery('inactive')">Cached Query (Inactive)</button>
                <button onclick="testCachedQuery('pending')">Cached Query (Pending)</button>
            </div>
            
            <div class="feature-section">
                <h2 class="feature-title">4. Benchmarking</h2>
                <p>View performance metrics for all endpoints.</p>
                <button onclick="getBenchmarkResults()">Get Benchmark Results</button>
            </div>
            
            <div id="results">
                <h3>Response:</h3>
                <pre id="response"></pre>
            </div>
            
            <div id="benchmark-results" style="display: none;">
                <h3>Benchmark Results:</h3>
                <table id="benchmark-table">
                    <thead>
                        <tr>
                            <th>Endpoint</th>
                            <th>Count</th>
                            <th>Avg Time (ms)</th>
                            <th>Min Time (ms)</th>
                            <th>Max Time (ms)</th>
                        </tr>
                    </thead>
                    <tbody>
                    </tbody>
                </table>
            </div>
        </div>
        
        <script>
            async function testStandardJson() {
                await fetchEndpoint('/api/standard-json/');
            }
            
            async function testFastJson() {
                await fetchEndpoint('/api/fast-json/');
            }
            
            async function testMessagePack() {
                try {
                    const response = await fetch('/api/msgpack/');
                    
                    // Check if the response is MessagePack
                    if (response.headers.get('content-type') === 'application/x-msgpack') {
                        document.getElementById('response').textContent = 'Received MessagePack response. Binary data not displayed.';
                    } else {
                        const data = await response.json();
                        document.getElementById('response').textContent = JSON.stringify(data, null, 2);
                    }
                } catch (error) {
                    document.getElementById('response').textContent = 'Error: ' + error.toString();
                }
            }
            
            async function testStreamingJson() {
                try {
                    const startTime = performance.now();
                    const response = await fetch('/api/streaming-json/');
                    const reader = response.body.getReader();
                    const decoder = new TextDecoder();
                    
                    let receivedLength = 0;
                    let chunks = [];
                    
                    while (true) {
                        const { done, value } = await reader.read();
                        
                        if (done) {
                            break;
                        }
                        
                        chunks.push(decoder.decode(value));
                        receivedLength += value.length;
                        
                        // Update progress
                        document.getElementById('response').textContent = `Received ${receivedLength} bytes...`;
                    }
                    
                    const endTime = performance.now();
                    
                    document.getElementById('response').textContent = `Received streaming response: ${receivedLength} bytes in ${(endTime - startTime).toFixed(2)}ms`;
                } catch (error) {
                    document.getElementById('response').textContent = 'Error: ' + error.toString();
                }
            }
            
            async function testCachedResponse() {
                await fetchEndpoint('/api/cached-response/');
            }
            
            async function invalidateCache() {
                await fetchEndpoint('/api/invalidate-cache/');
            }
            
            async function testCachedQuery(status) {
                await fetchEndpoint(`/api/cached-query/?status=${status}`);
            }
            
            async function benchmarkFormats() {
                await fetchEndpoint('/api/benchmark-formats/');
            }
            
            async function getBenchmarkResults() {
                const response = await fetch('/api/benchmark-results/');
                const data = await response.json();
                
                // Display the benchmark results
                document.getElementById('benchmark-results').style.display = 'block';
                
                // Clear the table
                const tableBody = document.getElementById('benchmark-table').getElementsByTagName('tbody')[0];
                tableBody.innerHTML = '';
                
                // Add rows to the table
                for (const [endpoint, metrics] of Object.entries(data)) {
                    const row = tableBody.insertRow();
                    row.insertCell(0).textContent = endpoint;
                    row.insertCell(1).textContent = metrics.count;
                    row.insertCell(2).textContent = metrics.avg_time.toFixed(2);
                    row.insertCell(3).textContent = metrics.min_time.toFixed(2);
                    row.insertCell(4).textContent = metrics.max_time.toFixed(2);
                }
                
                // Hide the response
                document.getElementById('response').textContent = '';
            }
            
            async function fetchEndpoint(url) {
                try {
                    const startTime = performance.now();
                    const response = await fetch(url);
                    const endTime = performance.now();
                    
                    // Get the response time from headers
                    const serverTime = response.headers.get('X-Django-Matt-Timing') || 'Not available';
                    
                    // Calculate client-side time
                    const clientTime = (endTime - startTime).toFixed(2);
                    
                    // Display the response (truncated for large responses)
                    const data = await response.json();
                    let responseText = JSON.stringify(data, null, 2);
                    
                    // Add timing information
                    responseText = `// Server processing time: ${serverTime}, Client time: ${clientTime}ms\n\n${responseText}`;
                    
                    // Truncate large responses
                    if (responseText.length > 5000) {
                        responseText = responseText.substring(0, 5000) + '... (truncated)';
                    }
                    
                    document.getElementById('response').textContent = responseText;
                    
                    // Hide the benchmark results
                    document.getElementById('benchmark-results').style.display = 'none';
                } catch (error) {
                    document.getElementById('response').textContent = 'Error: ' + error.toString();
                }
            }
        </script>
    </body>
    </html>
    """ % (
        "Yes" if HAS_ORJSON else "No",
        "Yes" if HAS_UJSON else "No",
        "Yes" if HAS_MSGPACK else "No",
    )

    return HttpResponse(html)


urlpatterns.append(path("", index_view))

# Run the application
if __name__ == "__main__":
    print("\n=== Django Matt Advanced Performance Demo ===")
    print("Open your browser at http://localhost:8000")
    print("Libraries:")
    print(f"  - orjson: {'Available' if HAS_ORJSON else 'Not available'}")
    print(f"  - ujson: {'Available' if HAS_UJSON else 'Not available'}")
    print(f"  - msgpack: {'Available' if HAS_MSGPACK else 'Not available'}")
    print("===================================\n")

    from django.core.management import execute_from_command_line

    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])
else:
    # For WSGI servers
    application = get_wsgi_application()
