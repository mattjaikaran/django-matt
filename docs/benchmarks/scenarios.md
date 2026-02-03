# Benchmark Scenarios

Django Matt includes five built-in benchmark scenarios that cover the most performance-critical areas of API development. Each scenario contains multiple benchmarks with realistic workloads.

## JSON Serialization Scenario

**Name:** `json`
**Default Iterations:** 5,000

Benchmarks JSON serialization and deserialization performance across different libraries and payload sizes.

### Benchmarks Included

| Benchmark | Description |
|-----------|-------------|
| `json.dumps (small)` | Stdlib JSON encode - 4 fields |
| `json.loads (small)` | Stdlib JSON decode - 4 fields |
| `json.dumps (medium)` | Stdlib JSON encode - nested object |
| `json.dumps (large)` | Stdlib JSON encode - 100 nested items |
| `json.dumps (list 100)` | Stdlib JSON encode - 100 objects |
| `orjson.dumps (small)` | orjson encode - 4 fields |
| `orjson.loads (small)` | orjson decode - 4 fields |
| `orjson.dumps (medium)` | orjson encode - nested object |
| `orjson.dumps (large)` | orjson encode - 100 nested items |
| `orjson.dumps (list 100)` | orjson encode - 100 objects |
| `ujson.dumps (small)` | ujson encode - 4 fields |
| `ujson.loads (small)` | ujson decode - 4 fields |
| `FastJSONRenderer.dumps (medium)` | Django Matt auto-selection |

### Sample Data Sizes

**Small (4 fields):**
```python
{
    "id": 1,
    "name": "Test User",
    "email": "test@example.com",
    "active": True,
}
```

**Medium (nested):**
```python
{
    "id": 1,
    "name": "Test User",
    "email": "test@example.com",
    "active": True,
    "created_at": "2024-01-15T10:30:00",
    "profile": {
        "bio": "A test user biography...",
        "social": {"twitter": "@user", "github": "user"},
    },
    "tags": ["python", "django", "api"],
    "settings": {"notifications": True, "theme": "dark"},
}
```

**Large (100 nested items):**
```python
{
    "id": 1,
    "items": [
        {
            "id": i,
            "title": f"Item {i}",
            "description": "Long description...",
            "price": 99.99,
            "quantity": 10,
            "categories": ["cat1", "cat2", "cat3"],
            "metadata": {"weight": 1.5, "dimensions": {...}},
        }
        for i in range(100)
    ],
}
```

### Example Results

```
[JSON]
--------------------------------------------------------------------------------
Benchmark                                       Mean        Min        Max     Ops/s
  orjson.dumps (small)                        0.002ms    0.001ms    0.015ms   500.0K
  orjson.loads (small)                        0.002ms    0.001ms    0.012ms   500.0K
  ujson.dumps (small)                         0.004ms    0.003ms    0.025ms   250.0K
  json.dumps (small)                          0.015ms    0.012ms    0.089ms    66.7K
  orjson.dumps (medium)                       0.008ms    0.006ms    0.045ms   125.0K
  json.dumps (medium)                         0.045ms    0.038ms    0.156ms    22.2K
  orjson.dumps (large)                        0.250ms    0.200ms    0.450ms     4.0K
  json.dumps (large)                          1.200ms    1.000ms    1.800ms     0.8K
```

---

## Schema Validation Scenario

**Name:** `schema`
**Default Iterations:** 5,000

Benchmarks Pydantic schema validation, serialization, and bulk operations.

### Benchmarks Included

| Benchmark | Description |
|-----------|-------------|
| `SimpleSchema validation` | Basic 4-field schema validation |
| `SimpleSchema.model_dump()` | Basic schema serialization |
| `NestedSchema validation` | Schema with nested models |
| `NestedSchema.model_dump()` | Nested schema serialization |
| `ValidatedSchema validation` | Schema with field validators |
| `SimpleSchema bulk validation (100)` | Validate 100 items |
| `ModelSchema validation` | Django Matt ModelSchema |

### Schema Definitions

**SimpleSchema:**
```python
class SimpleSchema(BaseModel):
    id: int
    name: str
    email: str
    active: bool = True
```

**NestedSchema:**
```python
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
```

**ValidatedSchema:**
```python
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
```

### Example Results

```
[SCHEMA]
--------------------------------------------------------------------------------
Benchmark                                       Mean        Min        Max     Ops/s
  SimpleSchema validation                     0.008ms    0.006ms    0.045ms   125.0K
  SimpleSchema.model_dump()                   0.004ms    0.003ms    0.025ms   250.0K
  NestedSchema validation                     0.025ms    0.020ms    0.098ms    40.0K
  ValidatedSchema validation                  0.012ms    0.009ms    0.055ms    83.3K
  SimpleSchema bulk validation (100)          0.800ms    0.700ms    1.200ms     1.3K
```

---

## Routing Scenario

**Name:** `routing`
**Default Iterations:** 5,000

Benchmarks URL routing, pattern matching, and route resolution performance.

### Benchmarks Included

| Benchmark | Description |
|-----------|-------------|
| `Route registration (10 routes)` | Register 10 new routes |
| `Simple route match` | Match static URL path |
| `Parameterized route match` | Match URL with parameter |
| `Nested route match` | Match deeply nested URL |
| `Generate URL patterns (100+ routes)` | Generate Django URLconf |

### Route Patterns Tested

```python
# Simple static routes
"/users"
"/products"

# Parameterized routes
"/users/{user_id}"
"/products/{product_id}"

# Deeply nested routes
"/organizations/{org_id}/teams/{team_id}/members"
```

### Example Results

```
[ROUTING]
--------------------------------------------------------------------------------
Benchmark                                       Mean        Min        Max     Ops/s
  Simple route match                          0.001ms    0.001ms    0.008ms  1000.0K
  Parameterized route match                   0.002ms    0.001ms    0.012ms   500.0K
  Nested route match                          0.003ms    0.002ms    0.015ms   333.3K
  Route registration (10 routes)              0.150ms    0.120ms    0.350ms     6.7K
  Generate URL patterns (100+ routes)         2.500ms    2.000ms    4.000ms     0.4K
```

---

## Database Scenario

**Name:** `database`
**Default Iterations:** 500

Benchmarks database CRUD operations using SQLite in-memory database.

### Benchmarks Included

| Benchmark | Description |
|-----------|-------------|
| `DB INSERT (single row)` | Insert one row |
| `DB SELECT (single row by PK)` | Select by primary key |
| `DB SELECT (list with LIMIT 20)` | Select multiple rows |
| `DB UPDATE (single row)` | Update one row |
| `DB DELETE (single row)` | Delete one row |
| `DB BULK INSERT (100 rows)` | Insert 100 rows at once |

### Table Schema

```sql
CREATE TABLE benchmark_test (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100),
    email VARCHAR(255),
    active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Example Results

```
[DATABASE]
--------------------------------------------------------------------------------
Benchmark                                       Mean        Min        Max     Ops/s
  DB SELECT (single row by PK)                0.015ms    0.010ms    0.045ms    66.7K
  DB INSERT (single row)                      0.025ms    0.018ms    0.085ms    40.0K
  DB UPDATE (single row)                      0.020ms    0.015ms    0.065ms    50.0K
  DB DELETE (single row)                      0.018ms    0.012ms    0.055ms    55.6K
  DB SELECT (list with LIMIT 20)              0.045ms    0.035ms    0.125ms    22.2K
  DB BULK INSERT (100 rows)                   1.200ms    1.000ms    1.800ms     0.8K
```

!!! note "Database Configuration"
    The database scenario uses SQLite in-memory for consistent, fast benchmarks.
    Production database performance will vary based on your specific configuration.

---

## Caching Scenario

**Name:** `caching`
**Default Iterations:** 5,000

Benchmarks cache operations including Django cache, CacheManager, and DistributedCacheManager.

### Benchmarks Included

| Benchmark | Description |
|-----------|-------------|
| `Cache SET` | Basic cache set operation |
| `Cache GET (hit)` | Cache get with existing key |
| `Cache GET (miss)` | Cache get with missing key |
| `Cache DELETE` | Cache key deletion |
| `CacheManager set+get` | Django Matt CacheManager |
| `DistributedCacheManager.get_or_set` | Stampede-safe caching |

### Cache Configuration

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "benchmark-cache",
    }
}
```

### Example Results

```
[CACHING]
--------------------------------------------------------------------------------
Benchmark                                       Mean        Min        Max     Ops/s
  Cache GET (hit)                             0.002ms    0.001ms    0.012ms   500.0K
  Cache GET (miss)                            0.002ms    0.001ms    0.010ms   500.0K
  Cache SET                                   0.003ms    0.002ms    0.015ms   333.3K
  Cache DELETE                                0.002ms    0.001ms    0.012ms   500.0K
  CacheManager set+get                        0.006ms    0.004ms    0.025ms   166.7K
  DistributedCacheManager.get_or_set          0.008ms    0.005ms    0.035ms   125.0K
```

---

## Running Individual Scenarios

### From CLI

```bash
# Single scenario
python manage.py benchmark --scenario json

# Multiple scenarios
python manage.py benchmark --scenario json schema

# Exclude slow scenarios
python manage.py benchmark --scenario json schema routing caching
```

### Programmatic

```python
from django_matt.benchmarks import (
    JSONSerializationScenario,
    SchemaValidationScenario,
    RoutingScenario,
    DatabaseScenario,
    CachingScenario,
)

# Run single scenario directly
scenario = JSONSerializationScenario(iterations=1000)
scenario.setup()
results = scenario.run()
scenario.teardown()

for result in results:
    print(f"{result.name}: {result.ops_per_second:.0f} ops/s")
```

## Scenario Configuration

### Adjusting Iterations

```python
# Lower iterations for quick checks
scenario = JSONSerializationScenario(iterations=100, warmup=5)

# Higher iterations for accuracy
scenario = JSONSerializationScenario(iterations=10000, warmup=100)
```

### Custom Data Sizes

```python
class CustomJSONScenario(JSONSerializationScenario):
    def __init__(self, iterations=5000):
        super().__init__(iterations)
        # Override with custom data
        self.large_data = generate_custom_data(items=1000)
```

## Performance Baselines

These are typical performance ranges on modern hardware (Apple M1/M2, Intel i7):

| Operation | Good | Acceptable | Needs Optimization |
|-----------|------|------------|-------------------|
| JSON encode (small) | < 5us | < 20us | > 50us |
| JSON encode (medium) | < 50us | < 200us | > 500us |
| Schema validation (simple) | < 10us | < 50us | > 100us |
| Route matching | < 5us | < 20us | > 50us |
| Cache GET | < 5us | < 20us | > 50us |
| DB SELECT (single) | < 50us | < 200us | > 500us |

!!! tip "Optimization Priority"
    Focus optimization efforts on operations that appear in hot paths.
    A 10x slower JSON encode matters more if it runs 1000 times per request.
