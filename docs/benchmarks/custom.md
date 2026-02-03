# Creating Custom Benchmarks

Django Matt's benchmarking framework is extensible. You can create custom benchmarks to measure performance of your specific use cases.

## Creating a Single Benchmark

### Basic Benchmark

```python
from django_matt.benchmarks import Benchmark

# Create benchmark
benchmark = Benchmark(
    name="my_operation",
    scenario="custom",
    iterations=1000,
    warmup_iterations=10,
    metadata={"version": "1.0"},
)

# Define function to benchmark
def my_operation(data):
    return process_data(data)

# Run benchmark
result = benchmark.run(my_operation, sample_data)

print(f"Mean: {result.mean_time_ms:.4f}ms")
print(f"Ops/s: {result.ops_per_second:,.0f}")
print(f"Min: {result.min_time_ms:.4f}ms")
print(f"Max: {result.max_time_ms:.4f}ms")
```

### With Setup and Teardown

```python
benchmark = Benchmark(name="db_operation", iterations=100)

# State for setup/teardown
state = {"id": None}

def setup():
    """Called before each iteration."""
    # Create test data
    obj = MyModel.objects.create(name="test")
    state["id"] = obj.id

def teardown():
    """Called after each iteration."""
    # Clean up
    MyModel.objects.filter(id=state["id"]).delete()

def operation():
    return MyModel.objects.get(id=state["id"])

result = benchmark.run(operation, setup=setup, teardown=teardown)
```

### Async Benchmarks

```python
import asyncio
from django_matt.benchmarks import Benchmark

benchmark = Benchmark(name="async_api_call", iterations=500)

async def async_operation():
    async with aiohttp.ClientSession() as session:
        async with session.get("http://api.example.com/data") as response:
            return await response.json()

# Use run_async for async functions
result = benchmark.run_async(async_operation)
```

## Creating a Custom Scenario

### Basic Scenario Structure

```python
from django_matt.benchmarks import BenchmarkScenario, BenchmarkResult

class MyCustomScenario(BenchmarkScenario):
    """Benchmarks for my custom operations."""

    name = "custom"
    description = "Custom operation benchmarks"

    def __init__(self, iterations: int = 1000, warmup: int = 10):
        super().__init__(iterations, warmup)
        # Initialize any scenario-specific state
        self.data = None

    def setup(self):
        """Called once before running all benchmarks."""
        # Prepare test data
        self.data = self._generate_test_data()

    def teardown(self):
        """Called once after all benchmarks complete."""
        # Cleanup
        self.data = None

    def run(self) -> list[BenchmarkResult]:
        """Run all benchmarks in this scenario."""
        results = []

        results.append(self._benchmark_operation_a())
        results.append(self._benchmark_operation_b())

        return results

    def _generate_test_data(self):
        return {"key": "value", "items": list(range(100))}

    def _benchmark_operation_a(self) -> BenchmarkResult:
        """Benchmark operation A."""
        benchmark = self.create_benchmark(
            "Operation A",
            metadata={"type": "a"},
        )
        return benchmark.run(self._do_operation_a)

    def _benchmark_operation_b(self) -> BenchmarkResult:
        """Benchmark operation B."""
        benchmark = self.create_benchmark(
            "Operation B",
            iterations=self.iterations // 10,  # Fewer iterations
            metadata={"type": "b"},
        )
        return benchmark.run(self._do_operation_b)

    def _do_operation_a(self):
        # Implementation
        return process_a(self.data)

    def _do_operation_b(self):
        # Implementation
        return process_b(self.data)
```

### Handling Missing Dependencies

```python
class ExternalServiceScenario(BenchmarkScenario):
    name = "external"
    description = "External service benchmarks"

    def __init__(self, iterations: int = 100, warmup: int = 5):
        super().__init__(iterations, warmup)
        self._available = False

        try:
            import external_client
            self._client = external_client.Client()
            self._available = True
        except ImportError:
            pass

    def run(self) -> list[BenchmarkResult]:
        if not self._available:
            return [self._create_skip_result("external_client not installed")]

        results = []
        results.append(self._benchmark_fetch())
        return results

    def _create_skip_result(self, reason: str) -> BenchmarkResult:
        return BenchmarkResult(
            name=f"external ({reason})",
            scenario=self.name,
            iterations=0,
            total_time_ms=0,
            mean_time_ms=0,
            median_time_ms=0,
            min_time_ms=0,
            max_time_ms=0,
            std_dev_ms=0,
            ops_per_second=0,
            metadata={"skipped": True, "reason": reason},
        )

    def _benchmark_fetch(self) -> BenchmarkResult:
        benchmark = self.create_benchmark("External fetch")
        return benchmark.run(self._client.fetch, "endpoint")
```

## Registering Custom Scenarios

### With BenchmarkSuite

```python
from django_matt.benchmarks import BenchmarkSuite, BenchmarkRunner

# Create suite (includes default scenarios)
suite = BenchmarkSuite()

# Register custom scenario
suite.register(MyCustomScenario())

# Run all including custom
runner = BenchmarkRunner(suite)
results = runner.run()
```

### Creating a Custom Suite

```python
from django_matt.benchmarks import BenchmarkSuite

class MyBenchmarkSuite(BenchmarkSuite):
    """Custom benchmark suite for my application."""

    def _register_default_scenarios(self):
        """Override to register only custom scenarios."""
        # Skip default scenarios
        # super()._register_default_scenarios()

        # Register only custom scenarios
        self.register(MyCustomScenario())
        self.register(AnotherScenario())
```

### Running Custom Scenarios

```python
# CLI - run custom scenarios by name
python manage.py benchmark --scenario custom

# Programmatic
runner = BenchmarkRunner(suite)
results = runner.run(scenarios=["custom"])
```

## Real-World Examples

### API Endpoint Benchmark

```python
class EndpointBenchmarkScenario(BenchmarkScenario):
    """Benchmark actual API endpoints."""

    name = "endpoints"
    description = "API endpoint response time benchmarks"

    def __init__(self, iterations: int = 100, warmup: int = 5):
        super().__init__(iterations, warmup)
        self.client = None

    def setup(self):
        from django.test import Client
        self.client = Client()

        # Create test data
        from myapp.models import User
        User.objects.create(username="benchmark", email="bench@test.com")

    def teardown(self):
        from myapp.models import User
        User.objects.filter(username="benchmark").delete()

    def run(self) -> list[BenchmarkResult]:
        results = []
        results.append(self._benchmark_list_endpoint())
        results.append(self._benchmark_detail_endpoint())
        results.append(self._benchmark_create_endpoint())
        return results

    def _benchmark_list_endpoint(self) -> BenchmarkResult:
        benchmark = self.create_benchmark("GET /api/users/")
        return benchmark.run(
            self.client.get,
            "/api/users/",
            content_type="application/json",
        )

    def _benchmark_detail_endpoint(self) -> BenchmarkResult:
        benchmark = self.create_benchmark("GET /api/users/1/")
        return benchmark.run(
            self.client.get,
            "/api/users/1/",
            content_type="application/json",
        )

    def _benchmark_create_endpoint(self) -> BenchmarkResult:
        counter = [0]

        def create_user():
            counter[0] += 1
            return self.client.post(
                "/api/users/",
                {"username": f"user_{counter[0]}", "email": f"u{counter[0]}@test.com"},
                content_type="application/json",
            )

        benchmark = self.create_benchmark("POST /api/users/")
        return benchmark.run(create_user)
```

### Algorithm Comparison

```python
class AlgorithmScenario(BenchmarkScenario):
    """Compare different algorithm implementations."""

    name = "algorithms"
    description = "Algorithm implementation comparison"

    def __init__(self, iterations: int = 5000, warmup: int = 50):
        super().__init__(iterations, warmup)
        self.data = list(range(10000))

    def run(self) -> list[BenchmarkResult]:
        results = []

        # Compare sorting algorithms
        results.append(self._benchmark_builtin_sort())
        results.append(self._benchmark_quicksort())
        results.append(self._benchmark_mergesort())

        return results

    def _benchmark_builtin_sort(self) -> BenchmarkResult:
        def sort_data():
            data = self.data.copy()
            return sorted(data)

        benchmark = self.create_benchmark(
            "sorted() builtin",
            metadata={"algorithm": "timsort"},
        )
        return benchmark.run(sort_data)

    def _benchmark_quicksort(self) -> BenchmarkResult:
        def quicksort(arr):
            if len(arr) <= 1:
                return arr
            pivot = arr[len(arr) // 2]
            left = [x for x in arr if x < pivot]
            middle = [x for x in arr if x == pivot]
            right = [x for x in arr if x > pivot]
            return quicksort(left) + middle + quicksort(right)

        def sort_data():
            return quicksort(self.data.copy())

        benchmark = self.create_benchmark(
            "quicksort",
            metadata={"algorithm": "quicksort"},
        )
        return benchmark.run(sort_data)

    def _benchmark_mergesort(self) -> BenchmarkResult:
        def mergesort(arr):
            if len(arr) <= 1:
                return arr
            mid = len(arr) // 2
            left = mergesort(arr[:mid])
            right = mergesort(arr[mid:])
            return merge(left, right)

        def merge(left, right):
            result = []
            i = j = 0
            while i < len(left) and j < len(right):
                if left[i] <= right[j]:
                    result.append(left[i])
                    i += 1
                else:
                    result.append(right[j])
                    j += 1
            result.extend(left[i:])
            result.extend(right[j:])
            return result

        def sort_data():
            return mergesort(self.data.copy())

        benchmark = self.create_benchmark(
            "mergesort",
            metadata={"algorithm": "mergesort"},
        )
        return benchmark.run(sort_data)
```

### Serializer Comparison

```python
class SerializerScenario(BenchmarkScenario):
    """Compare different serialization approaches."""

    name = "serializers"
    description = "Serialization method comparison"

    def __init__(self, iterations: int = 2000, warmup: int = 20):
        super().__init__(iterations, warmup)
        self.users = None

    def setup(self):
        # Create test data
        from myapp.models import User
        self.users = list(User.objects.all()[:100])

    def run(self) -> list[BenchmarkResult]:
        results = []

        results.append(self._benchmark_values_list())
        results.append(self._benchmark_model_to_dict())
        results.append(self._benchmark_pydantic_schema())
        results.append(self._benchmark_drf_serializer())

        return results

    def _benchmark_values_list(self) -> BenchmarkResult:
        def serialize():
            return list(User.objects.values("id", "username", "email")[:100])

        benchmark = self.create_benchmark(
            "QuerySet.values()",
            metadata={"method": "values"},
        )
        return benchmark.run(serialize)

    def _benchmark_model_to_dict(self) -> BenchmarkResult:
        from django.forms.models import model_to_dict

        def serialize():
            return [model_to_dict(u, fields=["id", "username", "email"])
                    for u in self.users]

        benchmark = self.create_benchmark(
            "model_to_dict()",
            metadata={"method": "model_to_dict"},
        )
        return benchmark.run(serialize)

    def _benchmark_pydantic_schema(self) -> BenchmarkResult:
        from pydantic import BaseModel

        class UserSchema(BaseModel):
            id: int
            username: str
            email: str

            class Config:
                from_attributes = True

        def serialize():
            return [UserSchema.model_validate(u).model_dump() for u in self.users]

        benchmark = self.create_benchmark(
            "Pydantic Schema",
            metadata={"method": "pydantic"},
        )
        return benchmark.run(serialize)

    def _benchmark_drf_serializer(self) -> BenchmarkResult:
        try:
            from rest_framework import serializers
        except ImportError:
            return self._create_skip_result("DRF not installed")

        class UserSerializer(serializers.Serializer):
            id = serializers.IntegerField()
            username = serializers.CharField()
            email = serializers.EmailField()

        def serialize():
            return UserSerializer(self.users, many=True).data

        benchmark = self.create_benchmark(
            "DRF Serializer",
            metadata={"method": "drf"},
        )
        return benchmark.run(serialize)
```

## Best Practices

### 1. Realistic Data

Use production-like data volumes:

```python
def setup(self):
    # Bad: trivial data
    self.data = [1, 2, 3]

    # Good: realistic volume
    self.data = [generate_realistic_item() for _ in range(1000)]
```

### 2. Isolate Measurements

Measure only what you intend to benchmark:

```python
def _benchmark_processing(self) -> BenchmarkResult:
    # Bad: includes data generation in timing
    def operation():
        data = generate_data()  # Don't include this
        return process(data)

    # Good: prepare data in setup
    data = self._generate_data()

    def operation():
        return process(data)

    benchmark = self.create_benchmark("Processing")
    return benchmark.run(operation)
```

### 3. Document Assumptions

```python
class MyScenario(BenchmarkScenario):
    """
    Benchmarks for payment processing.

    Assumptions:
    - Uses mock payment gateway (no network latency)
    - Database has ~1000 existing transactions
    - Cache is pre-warmed

    To run with real gateway:
        PAYMENT_GATEWAY=real python manage.py benchmark --scenario payments
    """
```

### 4. Handle Variance

For benchmarks with high variance, increase iterations:

```python
def _benchmark_network_call(self) -> BenchmarkResult:
    benchmark = self.create_benchmark(
        "External API call",
        iterations=100,  # Fewer iterations
        metadata={
            "note": "High variance expected due to network",
            "acceptable_std_dev_percent": 50,
        },
    )
    return benchmark.run(self._call_api)
```

### 5. Add Context with Metadata

```python
benchmark = self.create_benchmark(
    "Process items",
    metadata={
        "item_count": len(self.items),
        "item_avg_size_bytes": self._avg_size(),
        "algorithm": "parallel_v2",
        "workers": 4,
    },
)
```
