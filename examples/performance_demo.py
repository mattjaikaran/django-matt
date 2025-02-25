"""
Example demonstrating Django Matt's performance utilities.

This example shows how to use the performance utilities of Django Matt
to benchmark API endpoints and use faster JSON rendering.

To run this example:
1. Install Django and Django Matt
2. Install orjson or ujson for faster JSON rendering: pip install orjson
3. Run this script with Python

"""

import os
import random
import sys
import time

import django
from django.conf import settings
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
    )
    django.setup()

# Import Django Matt components
from django_matt import APIRouter, FastJsonResponse, benchmark
from django_matt.utils.performance import HAS_ORJSON, HAS_UJSON

# Create a router
router = APIRouter()


# Generate a large dataset for testing
def generate_large_dataset(size=1000):
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
            "data": LARGE_DATASET,
            "count": len(LARGE_DATASET),
        }
    )


# Example endpoint using FastJsonResponse
@router.get("api/fast-json/")
@benchmark.measure("fast_json")
async def fast_json(request):
    """Return a large dataset using FastJsonResponse."""
    return FastJsonResponse(
        {
            "data": LARGE_DATASET,
            "count": len(LARGE_DATASET),
        }
    )


# Example endpoint with simulated database query
@router.get("api/simulated-query/")
@benchmark.measure("simulated_query")
async def simulated_query(request):
    """Simulate a database query and return the results."""
    # Simulate a database query
    time.sleep(0.1)  # Simulate a 100ms database query

    # Filter the dataset based on a query parameter
    status = request.GET.get("status", "active")
    filtered_data = [item for item in LARGE_DATASET if item["metadata"]["status"] == status]

    return FastJsonResponse(
        {
            "data": filtered_data,
            "count": len(filtered_data),
            "status": status,
        }
    )


# Example endpoint with CPU-intensive operation
@router.get("api/cpu-intensive/")
@benchmark.measure("cpu_intensive")
async def cpu_intensive(request):
    """Perform a CPU-intensive operation and return the results."""
    # Simulate a CPU-intensive operation
    result = 0
    for i in range(1000000):
        result += i

    return FastJsonResponse(
        {
            "result": result,
        }
    )


# Example endpoint to get benchmark results
@router.get("api/benchmark-results/")
async def benchmark_results(request):
    """Return the benchmark results."""
    return FastJsonResponse(benchmark.get_report())


# Create URL patterns
urlpatterns = router.get_urls()


# Add a simple HTML page to demonstrate the performance utilities
def index_view(request):
    """Simple HTML page to demonstrate the performance utilities."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Django Matt Performance Demo</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            h1 { color: #333; }
            .card { background: #f5f5f5; padding: 20px; margin-bottom: 20px; border-radius: 5px; }
            button { background: #4CAF50; color: white; border: none; padding: 10px 15px; cursor: pointer; margin-right: 10px; }
            pre { background: #f9f9f9; padding: 10px; overflow: auto; }
            #results { margin-top: 20px; }
            .benchmark-info { background: #e3f2fd; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #f2f2f2; }
        </style>
    </head>
    <body>
        <h1>Django Matt Performance Demo</h1>
        
        <div class="benchmark-info">
            <h3>JSON Library Information:</h3>
            <p>orjson available: <strong id="orjson-status"></strong></p>
            <p>ujson available: <strong id="ujson-status"></strong></p>
        </div>
        
        <div class="card">
            <h2>API Endpoints:</h2>
            <button onclick="testStandardJson()">Standard JSON</button>
            <button onclick="testFastJson()">Fast JSON</button>
            <button onclick="testSimulatedQuery()">Simulated Query</button>
            <button onclick="testCpuIntensive()">CPU Intensive</button>
            <button onclick="getBenchmarkResults()">Get Benchmark Results</button>
            
            <div id="results">
                <h3>Response Time:</h3>
                <p id="response-time"></p>
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
            // Set JSON library status
            fetch('/api/benchmark-results/')
                .then(response => {
                    // Check response headers for JSON library info
                    document.getElementById('orjson-status').textContent = '%s';
                    document.getElementById('ujson-status').textContent = '%s';
                })
                .catch(error => {
                    console.error('Error fetching benchmark results:', error);
                });
            
            async function testStandardJson() {
                await fetchEndpoint('/api/standard-json/');
            }
            
            async function testFastJson() {
                await fetchEndpoint('/api/fast-json/');
            }
            
            async function testSimulatedQuery() {
                await fetchEndpoint('/api/simulated-query/');
            }
            
            async function testCpuIntensive() {
                await fetchEndpoint('/api/cpu-intensive/');
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
                document.getElementById('response-time').textContent = '';
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
                    
                    // Display the response time
                    document.getElementById('response-time').textContent = `Server: ${serverTime}, Client: ${clientTime}ms`;
                    
                    // Display the response (truncated for large responses)
                    const data = await response.json();
                    let responseText = JSON.stringify(data, null, 2);
                    
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
    """ % ("Yes" if HAS_ORJSON else "No", "Yes" if HAS_UJSON else "No")

    return HttpResponse(html)


urlpatterns.append(path("", index_view))

# Run the application
if __name__ == "__main__":
    print("\n=== Django Matt Performance Demo ===")
    print("Open your browser at http://localhost:8000")
    print("JSON Libraries:")
    print(f"  - orjson: {'Available' if HAS_ORJSON else 'Not available'}")
    print(f"  - ujson: {'Available' if HAS_UJSON else 'Not available'}")
    print("===================================\n")

    from django.core.management import execute_from_command_line

    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])
else:
    # For WSGI servers
    application = get_wsgi_application()
