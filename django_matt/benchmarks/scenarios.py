"""
Standard benchmark scenarios for Django Matt framework.

This module provides realistic benchmark scenarios covering:
- JSON serialization (with/without orjson)
- Schema validation (Pydantic)
- Request routing
- Database CRUD operations
- Caching operations
"""

import json
import random
import string
from datetime import datetime, timedelta
from typing import Any

from django_matt.benchmarks.runner import BenchmarkResult, BenchmarkScenario


def _generate_random_string(length: int = 10) -> str:
    """Generate a random string."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def _generate_sample_data(size: str = "small") -> dict[str, Any]:
    """Generate sample data for serialization benchmarks."""
    if size == "small":
        return {
            "id": 1,
            "name": "Test User",
            "email": "test@example.com",
            "active": True,
        }
    if size == "medium":
        return {
            "id": 1,
            "name": "Test User",
            "email": "test@example.com",
            "active": True,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "profile": {
                "bio": "A test user biography " * 10,
                "website": "https://example.com",
                "location": "New York, NY",
                "social": {
                    "twitter": "@testuser",
                    "github": "testuser",
                    "linkedin": "testuser",
                },
            },
            "tags": ["python", "django", "api", "testing"],
            "settings": {
                "notifications": True,
                "theme": "dark",
                "language": "en",
                "timezone": "America/New_York",
            },
        }
    # large
    return {
        "id": 1,
        "name": "Test User",
        "email": "test@example.com",
        "active": True,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "items": [
            {
                "id": i,
                "title": f"Item {i}",
                "description": f"Description for item {i} " * 20,
                "price": random.uniform(10, 1000),
                "quantity": random.randint(1, 100),
                "categories": [_generate_random_string(8) for _ in range(5)],
                "metadata": {
                    "weight": random.uniform(0.1, 10.0),
                    "dimensions": {
                        "width": random.uniform(1, 100),
                        "height": random.uniform(1, 100),
                        "depth": random.uniform(1, 100),
                    },
                },
            }
            for i in range(100)
        ],
    }


def _generate_list_data(count: int = 100) -> list[dict[str, Any]]:
    """Generate a list of sample objects."""
    return [
        {
            "id": i,
            "name": f"User {i}",
            "email": f"user{i}@example.com",
            "active": random.choice([True, False]),
            "score": random.uniform(0, 100),
            "created_at": (datetime.now() - timedelta(days=random.randint(0, 365))).isoformat(),
        }
        for i in range(count)
    ]


class JSONSerializationScenario(BenchmarkScenario):
    """
    Benchmark JSON serialization performance.

    Compares:
    - Standard library json
    - orjson (if available)
    - ujson (if available)
    """

    name = "json"
    description = "JSON serialization benchmarks"

    def __init__(self, iterations: int = 5000, warmup: int = 50):
        super().__init__(iterations, warmup)
        self.small_data = _generate_sample_data("small")
        self.medium_data = _generate_sample_data("medium")
        self.large_data = _generate_sample_data("large")
        self.list_data = _generate_list_data(100)

        # orjson is a base dependency, always available
        import orjson

        self.has_orjson = True
        self._orjson = orjson

        # ujson is optional (performance extra)
        self.has_ujson = False
        try:
            import ujson

            self.has_ujson = True
            self._ujson = ujson
        except ImportError:
            pass

    def run(self) -> list[BenchmarkResult]:
        """Run JSON serialization benchmarks."""
        results = []

        # Small data benchmarks
        results.append(self._benchmark_json_dumps("small"))
        results.append(self._benchmark_json_loads("small"))

        if self.has_orjson:
            results.append(self._benchmark_orjson_dumps("small"))
            results.append(self._benchmark_orjson_loads("small"))

        if self.has_ujson:
            results.append(self._benchmark_ujson_dumps("small"))
            results.append(self._benchmark_ujson_loads("small"))

        # Medium data benchmarks
        results.append(self._benchmark_json_dumps("medium"))
        if self.has_orjson:
            results.append(self._benchmark_orjson_dumps("medium"))

        # Large data benchmarks
        results.append(self._benchmark_json_dumps("large"))
        if self.has_orjson:
            results.append(self._benchmark_orjson_dumps("large"))

        # List data benchmarks
        results.append(self._benchmark_json_list())
        if self.has_orjson:
            results.append(self._benchmark_orjson_list())

        # FastJSONRenderer benchmark
        results.append(self._benchmark_fast_json_renderer())

        return results

    def _get_data(self, size: str) -> dict[str, Any]:
        """Get sample data by size."""
        if size == "small":
            return self.small_data
        if size == "medium":
            return self.medium_data
        return self.large_data

    def _benchmark_json_dumps(self, size: str) -> BenchmarkResult:
        """Benchmark json.dumps."""
        data = self._get_data(size)
        benchmark = self.create_benchmark(
            f"json.dumps ({size})",
            metadata={"library": "stdlib", "operation": "serialize", "size": size},
        )
        return benchmark.run(json.dumps, data)

    def _benchmark_json_loads(self, size: str) -> BenchmarkResult:
        """Benchmark json.loads."""
        data = self._get_data(size)
        json_str = json.dumps(data)
        benchmark = self.create_benchmark(
            f"json.loads ({size})",
            metadata={"library": "stdlib", "operation": "deserialize", "size": size},
        )
        return benchmark.run(json.loads, json_str)

    def _benchmark_orjson_dumps(self, size: str) -> BenchmarkResult:
        """Benchmark orjson.dumps."""
        data = self._get_data(size)
        benchmark = self.create_benchmark(
            f"orjson.dumps ({size})",
            metadata={"library": "orjson", "operation": "serialize", "size": size},
        )
        return benchmark.run(self._orjson.dumps, data)

    def _benchmark_orjson_loads(self, size: str) -> BenchmarkResult:
        """Benchmark orjson.loads."""
        data = self._get_data(size)
        json_bytes = self._orjson.dumps(data)
        benchmark = self.create_benchmark(
            f"orjson.loads ({size})",
            metadata={"library": "orjson", "operation": "deserialize", "size": size},
        )
        return benchmark.run(self._orjson.loads, json_bytes)

    def _benchmark_ujson_dumps(self, size: str) -> BenchmarkResult:
        """Benchmark ujson.dumps."""
        data = self._get_data(size)
        benchmark = self.create_benchmark(
            f"ujson.dumps ({size})",
            metadata={"library": "ujson", "operation": "serialize", "size": size},
        )
        return benchmark.run(self._ujson.dumps, data)

    def _benchmark_ujson_loads(self, size: str) -> BenchmarkResult:
        """Benchmark ujson.loads."""
        data = self._get_data(size)
        json_str = self._ujson.dumps(data)
        benchmark = self.create_benchmark(
            f"ujson.loads ({size})",
            metadata={"library": "ujson", "operation": "deserialize", "size": size},
        )
        return benchmark.run(self._ujson.loads, json_str)

    def _benchmark_json_list(self) -> BenchmarkResult:
        """Benchmark json.dumps for list data."""
        benchmark = self.create_benchmark(
            "json.dumps (list 100)",
            metadata={"library": "stdlib", "operation": "serialize", "size": "list_100"},
        )
        return benchmark.run(json.dumps, self.list_data)

    def _benchmark_orjson_list(self) -> BenchmarkResult:
        """Benchmark orjson.dumps for list data."""
        benchmark = self.create_benchmark(
            "orjson.dumps (list 100)",
            metadata={"library": "orjson", "operation": "serialize", "size": "list_100"},
        )
        return benchmark.run(self._orjson.dumps, self.list_data)

    def _benchmark_fast_json_renderer(self) -> BenchmarkResult:
        """Benchmark FastJSONRenderer (uses best available library)."""
        try:
            from django_matt.utils.performance import FastJSONRenderer

            renderer = FastJSONRenderer()
            benchmark = self.create_benchmark(
                "FastJSONRenderer.dumps (medium)",
                metadata={
                    "library": renderer.library_name,
                    "operation": "serialize",
                    "size": "medium",
                },
            )
            return benchmark.run(FastJSONRenderer.dumps, self.medium_data)
        except ImportError:
            return BenchmarkResult(
                name="FastJSONRenderer.dumps (medium)",
                scenario=self.name,
                iterations=0,
                total_time_ms=0,
                mean_time_ms=0,
                median_time_ms=0,
                min_time_ms=0,
                max_time_ms=0,
                std_dev_ms=0,
                ops_per_second=0,
                metadata={"skipped": True, "reason": "django_matt not available"},
            )


class SchemaValidationScenario(BenchmarkScenario):
    """
    Benchmark Pydantic schema validation performance.

    Tests:
    - Simple schema validation
    - Complex nested schemas
    - Schema with custom validators
    - Model serialization (model_dump)
    """

    name = "schema"
    description = "Schema validation benchmarks"

    def __init__(self, iterations: int = 5000, warmup: int = 50):
        super().__init__(iterations, warmup)
        self._pydantic_available = False
        try:
            self._setup_schemas()
            self._pydantic_available = True
        except ImportError:
            pass

    def _setup_schemas(self):
        """Set up Pydantic schemas for testing."""
        from pydantic import BaseModel, Field, field_validator

        class SimpleSchema(BaseModel):
            id: int
            name: str
            email: str
            active: bool = True

        class AddressSchema(BaseModel):
            street: str
            city: str
            state: str
            zip_code: str = Field(pattern=r"^\d{5}$")

        class NestedSchema(BaseModel):
            id: int
            name: str
            email: str
            address: AddressSchema
            tags: list[str] = []

        class ValidatedSchema(BaseModel):
            id: int
            name: str = Field(min_length=1, max_length=100)
            email: str
            age: int = Field(ge=0, le=150)
            score: float = Field(ge=0.0, le=100.0)

            @field_validator("email")
            @classmethod
            def validate_email(cls, v: str) -> str:
                if "@" not in v:
                    raise ValueError("Invalid email format")
                return v.lower()

        self.SimpleSchema = SimpleSchema
        self.AddressSchema = AddressSchema
        self.NestedSchema = NestedSchema
        self.ValidatedSchema = ValidatedSchema

        # Sample data
        self.simple_data = {
            "id": 1,
            "name": "Test User",
            "email": "test@example.com",
            "active": True,
        }

        self.nested_data = {
            "id": 1,
            "name": "Test User",
            "email": "test@example.com",
            "address": {
                "street": "123 Main St",
                "city": "New York",
                "state": "NY",
                "zip_code": "10001",
            },
            "tags": ["python", "django", "pydantic"],
        }

        self.validated_data = {
            "id": 1,
            "name": "Test User",
            "email": "test@example.com",
            "age": 30,
            "score": 85.5,
        }

    def run(self) -> list[BenchmarkResult]:
        """Run schema validation benchmarks."""
        if not self._pydantic_available:
            return [self._create_skip_result("pydantic_not_available")]

        results = []

        # Simple validation
        results.append(self._benchmark_simple_validation())
        results.append(self._benchmark_simple_serialization())

        # Nested validation
        results.append(self._benchmark_nested_validation())
        results.append(self._benchmark_nested_serialization())

        # Validated schema
        results.append(self._benchmark_validated_validation())

        # Bulk validation
        results.append(self._benchmark_bulk_validation())

        # ModelSchema benchmark (if django is set up)
        try:
            results.append(self._benchmark_model_schema())
        except Exception:
            pass  # Django not configured

        return results

    def _create_skip_result(self, reason: str) -> BenchmarkResult:
        """Create a result indicating the benchmark was skipped."""
        return BenchmarkResult(
            name=f"schema ({reason})",
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

    def _benchmark_simple_validation(self) -> BenchmarkResult:
        """Benchmark simple schema validation."""
        benchmark = self.create_benchmark(
            "SimpleSchema validation",
            metadata={"schema": "simple", "operation": "validate"},
        )
        return benchmark.run(self.SimpleSchema, **self.simple_data)

    def _benchmark_simple_serialization(self) -> BenchmarkResult:
        """Benchmark simple schema serialization."""
        instance = self.SimpleSchema(**self.simple_data)
        benchmark = self.create_benchmark(
            "SimpleSchema.model_dump()",
            metadata={"schema": "simple", "operation": "serialize"},
        )
        return benchmark.run(instance.model_dump)

    def _benchmark_nested_validation(self) -> BenchmarkResult:
        """Benchmark nested schema validation."""
        benchmark = self.create_benchmark(
            "NestedSchema validation",
            metadata={"schema": "nested", "operation": "validate"},
        )
        return benchmark.run(self.NestedSchema, **self.nested_data)

    def _benchmark_nested_serialization(self) -> BenchmarkResult:
        """Benchmark nested schema serialization."""
        instance = self.NestedSchema(**self.nested_data)
        benchmark = self.create_benchmark(
            "NestedSchema.model_dump()",
            metadata={"schema": "nested", "operation": "serialize"},
        )
        return benchmark.run(instance.model_dump)

    def _benchmark_validated_validation(self) -> BenchmarkResult:
        """Benchmark schema with custom validators."""
        benchmark = self.create_benchmark(
            "ValidatedSchema validation",
            metadata={"schema": "validated", "operation": "validate"},
        )
        return benchmark.run(self.ValidatedSchema, **self.validated_data)

    def _benchmark_bulk_validation(self) -> BenchmarkResult:
        """Benchmark bulk schema validation."""
        items = [
            {
                "id": i,
                "name": f"User {i}",
                "email": f"user{i}@example.com",
                "active": True,
            }
            for i in range(100)
        ]

        def validate_bulk():
            return [self.SimpleSchema(**item) for item in items]

        benchmark = self.create_benchmark(
            "SimpleSchema bulk validation (100)",
            iterations=self.iterations // 10,  # Fewer iterations for bulk
            metadata={"schema": "simple", "operation": "bulk_validate", "count": 100},
        )
        return benchmark.run(validate_bulk)

    def _benchmark_model_schema(self) -> BenchmarkResult:
        """Benchmark ModelSchema from Django Matt."""
        from django_matt.core.schema import ModelSchema

        # Create a test schema dynamically
        class TestSchema(ModelSchema):
            id: int
            name: str
            email: str

            class Config:
                from_attributes = True

        data = {"id": 1, "name": "Test", "email": "test@example.com"}

        benchmark = self.create_benchmark(
            "ModelSchema validation",
            metadata={"schema": "model_schema", "operation": "validate"},
        )
        return benchmark.run(TestSchema, **data)


class RoutingScenario(BenchmarkScenario):
    """
    Benchmark request routing performance.

    Tests:
    - URL pattern matching
    - Route resolution
    - Parameter extraction
    """

    name = "routing"
    description = "Request routing benchmarks"

    def __init__(self, iterations: int = 5000, warmup: int = 50):
        super().__init__(iterations, warmup)
        self._router_available = False
        try:
            self._setup_router()
            self._router_available = True
        except ImportError:
            pass

    def _setup_router(self):
        """Set up router for testing."""
        from django_matt.core.router import APIRouter

        self.router = APIRouter()

        # Register various routes
        @self.router.get("/")
        def index():
            return {"message": "Hello"}

        @self.router.get("/users")
        def list_users():
            return []

        @self.router.get("/users/{user_id}")
        def get_user(user_id: int):
            return {"id": user_id}

        @self.router.post("/users")
        def create_user(body: dict):
            return body

        @self.router.get("/organizations/{org_id}/teams/{team_id}/members")
        def list_members(org_id: int, team_id: int):
            return []

        # Add many routes to test scaling
        for i in range(100):

            @self.router.get(f"/resource{i}")
            def resource_handler():
                return {}

    def run(self) -> list[BenchmarkResult]:
        """Run routing benchmarks."""
        if not self._router_available:
            return [self._create_skip_result("router_not_available")]

        results = []

        # Route registration benchmark
        results.append(self._benchmark_route_registration())

        # URL pattern matching
        results.append(self._benchmark_simple_match())
        results.append(self._benchmark_parameterized_match())
        results.append(self._benchmark_nested_match())

        # Get URLs generation
        results.append(self._benchmark_get_urls())

        return results

    def _create_skip_result(self, reason: str) -> BenchmarkResult:
        """Create a result indicating the benchmark was skipped."""
        return BenchmarkResult(
            name=f"routing ({reason})",
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

    def _benchmark_route_registration(self) -> BenchmarkResult:
        """Benchmark route registration."""
        from django_matt.core.router import APIRouter

        def register_routes():
            router = APIRouter()
            for i in range(10):

                @router.get(f"/test{i}")
                def handler():
                    return {}

        benchmark = self.create_benchmark(
            "Route registration (10 routes)",
            metadata={"operation": "register", "count": 10},
        )
        return benchmark.run(register_routes)

    def _benchmark_simple_match(self) -> BenchmarkResult:
        """Benchmark simple URL matching."""

        def find_route():
            for route in self.router.routes:
                if route["path"] == "/users":
                    return route
            return None

        benchmark = self.create_benchmark(
            "Simple route match",
            metadata={"operation": "match", "pattern": "simple"},
        )
        return benchmark.run(find_route)

    def _benchmark_parameterized_match(self) -> BenchmarkResult:
        """Benchmark parameterized URL matching."""
        import re

        pattern = re.compile(r"/users/(\d+)")

        def match_url():
            return pattern.match("/users/123")

        benchmark = self.create_benchmark(
            "Parameterized route match",
            metadata={"operation": "match", "pattern": "parameterized"},
        )
        return benchmark.run(match_url)

    def _benchmark_nested_match(self) -> BenchmarkResult:
        """Benchmark nested URL matching."""
        import re

        pattern = re.compile(r"/organizations/(\d+)/teams/(\d+)/members")

        def match_url():
            return pattern.match("/organizations/1/teams/2/members")

        benchmark = self.create_benchmark(
            "Nested route match",
            metadata={"operation": "match", "pattern": "nested"},
        )
        return benchmark.run(match_url)

    def _benchmark_get_urls(self) -> BenchmarkResult:
        """Benchmark URL pattern generation."""
        benchmark = self.create_benchmark(
            "Generate URL patterns (100+ routes)",
            iterations=self.iterations // 10,
            metadata={"operation": "get_urls", "count": len(self.router.routes)},
        )
        return benchmark.run(self.router.get_urls)


class DatabaseScenario(BenchmarkScenario):
    """
    Benchmark database CRUD operations.

    Note: This scenario requires Django to be properly configured with a database.
    It uses an in-memory SQLite database for benchmarking.
    """

    name = "database"
    description = "Database CRUD benchmarks"

    def __init__(self, iterations: int = 500, warmup: int = 10):
        super().__init__(iterations, warmup)
        self._model = None

    def setup(self):
        """Set up test database and model."""
        try:
            import django
            from django.conf import settings

            if not settings.configured:
                settings.configure(
                    DEBUG=True,
                    DATABASES={
                        "default": {
                            "ENGINE": "django.db.backends.sqlite3",
                            "NAME": ":memory:",
                        }
                    },
                    INSTALLED_APPS=[
                        "django.contrib.contenttypes",
                        "django.contrib.auth",
                    ],
                    DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
                )
                django.setup()

            from django.db import connection

            # Create a test table
            with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS benchmark_test (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(100),
                        email VARCHAR(255),
                        active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

            self._connection = connection
            self._db_available = True
        except Exception:
            self._db_available = False

    def teardown(self):
        """Clean up test database."""
        if self._db_available:
            try:
                with self._connection.cursor() as cursor:
                    cursor.execute("DROP TABLE IF EXISTS benchmark_test")
            except Exception:
                pass

    def run(self) -> list[BenchmarkResult]:
        """Run database benchmarks."""
        if not getattr(self, "_db_available", False):
            return [self._create_skip_result("database_unavailable")]

        results = []

        # Individual CRUD operations
        results.append(self._benchmark_insert())
        results.append(self._benchmark_select_single())
        results.append(self._benchmark_select_list())
        results.append(self._benchmark_update())
        results.append(self._benchmark_delete())

        # Bulk operations
        results.append(self._benchmark_bulk_insert())

        return results

    def _create_skip_result(self, reason: str) -> BenchmarkResult:
        """Create a result indicating the benchmark was skipped."""
        return BenchmarkResult(
            name=f"database ({reason})",
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

    def _benchmark_insert(self) -> BenchmarkResult:
        """Benchmark single row insert."""
        counter = [0]

        def insert_row():
            counter[0] += 1
            with self._connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO benchmark_test (name, email) VALUES (?, ?)",
                    [f"User {counter[0]}", f"user{counter[0]}@example.com"],
                )

        benchmark = self.create_benchmark(
            "DB INSERT (single row)",
            metadata={"operation": "insert", "rows": 1},
        )
        return benchmark.run(insert_row)

    def _benchmark_select_single(self) -> BenchmarkResult:
        """Benchmark single row select."""
        # Ensure there's data to select
        with self._connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO benchmark_test (name, email) VALUES (?, ?)",
                ["Test", "test@example.com"],
            )
            cursor.execute("SELECT last_insert_rowid()")
            row_id = cursor.fetchone()[0]

        def select_row():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM benchmark_test WHERE id = ?",
                    [row_id],
                )
                return cursor.fetchone()

        benchmark = self.create_benchmark(
            "DB SELECT (single row by PK)",
            metadata={"operation": "select", "rows": 1},
        )
        return benchmark.run(select_row)

    def _benchmark_select_list(self) -> BenchmarkResult:
        """Benchmark list select."""
        # Insert sample data
        with self._connection.cursor() as cursor:
            for i in range(100):
                cursor.execute(
                    "INSERT INTO benchmark_test (name, email) VALUES (?, ?)",
                    [f"User {i}", f"user{i}@example.com"],
                )

        def select_list():
            with self._connection.cursor() as cursor:
                cursor.execute("SELECT * FROM benchmark_test LIMIT 20")
                return cursor.fetchall()

        benchmark = self.create_benchmark(
            "DB SELECT (list with LIMIT 20)",
            metadata={"operation": "select", "rows": 20},
        )
        return benchmark.run(select_list)

    def _benchmark_update(self) -> BenchmarkResult:
        """Benchmark single row update."""
        with self._connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO benchmark_test (name, email) VALUES (?, ?)",
                ["Update Test", "update@example.com"],
            )
            cursor.execute("SELECT last_insert_rowid()")
            row_id = cursor.fetchone()[0]

        def update_row():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE benchmark_test SET name = ? WHERE id = ?",
                    ["Updated Name", row_id],
                )

        benchmark = self.create_benchmark(
            "DB UPDATE (single row)",
            metadata={"operation": "update", "rows": 1},
        )
        return benchmark.run(update_row)

    def _benchmark_delete(self) -> BenchmarkResult:
        """Benchmark single row delete."""

        def setup():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO benchmark_test (name, email) VALUES (?, ?)",
                    ["Delete Test", "delete@example.com"],
                )

        def delete_row():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM benchmark_test WHERE email = ?",
                    ["delete@example.com"],
                )

        benchmark = self.create_benchmark(
            "DB DELETE (single row)",
            metadata={"operation": "delete", "rows": 1},
        )
        return benchmark.run(delete_row, setup=setup)

    def _benchmark_bulk_insert(self) -> BenchmarkResult:
        """Benchmark bulk insert."""

        def bulk_insert():
            with self._connection.cursor() as cursor:
                data = [(f"Bulk User {i}", f"bulk{i}@example.com") for i in range(100)]
                cursor.executemany(
                    "INSERT INTO benchmark_test (name, email) VALUES (?, ?)",
                    data,
                )

        benchmark = self.create_benchmark(
            "DB BULK INSERT (100 rows)",
            iterations=self.iterations // 10,
            metadata={"operation": "bulk_insert", "rows": 100},
        )
        return benchmark.run(bulk_insert)


class CachingScenario(BenchmarkScenario):
    """
    Benchmark caching operations.

    Tests:
    - Cache get/set operations
    - Cache manager performance
    - Distributed cache operations
    """

    name = "caching"
    description = "Caching benchmarks"

    def __init__(self, iterations: int = 5000, warmup: int = 50):
        super().__init__(iterations, warmup)

    def setup(self):
        """Set up caching infrastructure."""
        try:
            import django
            from django.conf import settings

            if not settings.configured:
                settings.configure(
                    DEBUG=True,
                    CACHES={
                        "default": {
                            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                            "LOCATION": "benchmark-cache",
                        }
                    },
                )
                django.setup()

            from django.core.cache import cache

            self._cache = cache
            self._cache_available = True
        except Exception:
            self._cache_available = False

    def run(self) -> list[BenchmarkResult]:
        """Run caching benchmarks."""
        if not getattr(self, "_cache_available", False):
            return [self._create_skip_result("cache_unavailable")]

        results = []

        # Basic cache operations
        results.append(self._benchmark_cache_set())
        results.append(self._benchmark_cache_get())
        results.append(self._benchmark_cache_get_miss())
        results.append(self._benchmark_cache_delete())

        # Cache manager
        results.append(self._benchmark_cache_manager())

        # Distributed cache manager
        results.append(self._benchmark_distributed_cache())

        return results

    def _create_skip_result(self, reason: str) -> BenchmarkResult:
        """Create a result indicating the benchmark was skipped."""
        return BenchmarkResult(
            name=f"caching ({reason})",
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

    def _benchmark_cache_set(self) -> BenchmarkResult:
        """Benchmark cache set operation."""
        counter = [0]

        def cache_set():
            counter[0] += 1
            self._cache.set(f"key_{counter[0]}", {"data": "value"}, 300)

        benchmark = self.create_benchmark(
            "Cache SET",
            metadata={"operation": "set"},
        )
        return benchmark.run(cache_set)

    def _benchmark_cache_get(self) -> BenchmarkResult:
        """Benchmark cache get operation (hit)."""
        self._cache.set("benchmark_key", {"data": "cached_value"}, 300)

        def cache_get():
            return self._cache.get("benchmark_key")

        benchmark = self.create_benchmark(
            "Cache GET (hit)",
            metadata={"operation": "get", "hit": True},
        )
        return benchmark.run(cache_get)

    def _benchmark_cache_get_miss(self) -> BenchmarkResult:
        """Benchmark cache get operation (miss)."""

        def cache_get_miss():
            return self._cache.get("nonexistent_key")

        benchmark = self.create_benchmark(
            "Cache GET (miss)",
            metadata={"operation": "get", "hit": False},
        )
        return benchmark.run(cache_get_miss)

    def _benchmark_cache_delete(self) -> BenchmarkResult:
        """Benchmark cache delete operation."""
        counter = [0]

        def setup():
            counter[0] += 1
            self._cache.set(f"delete_key_{counter[0]}", "value", 300)

        def cache_delete():
            self._cache.delete(f"delete_key_{counter[0]}")

        benchmark = self.create_benchmark(
            "Cache DELETE",
            metadata={"operation": "delete"},
        )
        return benchmark.run(cache_delete, setup=setup)

    def _benchmark_cache_manager(self) -> BenchmarkResult:
        """Benchmark CacheManager operations."""
        from django_matt.utils.performance import CacheManager

        manager = CacheManager(self._cache)
        counter = [0]

        def cache_manager_ops():
            counter[0] += 1
            key = f"manager_key_{counter[0]}"
            manager.set(key, {"data": counter[0]})
            manager.get(key)

        benchmark = self.create_benchmark(
            "CacheManager set+get",
            metadata={"operation": "manager_ops"},
        )
        return benchmark.run(cache_manager_ops)

    def _benchmark_distributed_cache(self) -> BenchmarkResult:
        """Benchmark DistributedCacheManager operations."""
        from django_matt.utils.performance import DistributedCacheManager

        manager = DistributedCacheManager(self._cache, namespace="benchmark")

        def get_or_set_op():
            return manager.get_or_set(
                "compute_key",
                lambda: {"computed": True},
                timeout=300,
            )

        benchmark = self.create_benchmark(
            "DistributedCacheManager.get_or_set",
            metadata={"operation": "get_or_set"},
        )
        return benchmark.run(get_or_set_op)
