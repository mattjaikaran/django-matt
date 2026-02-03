# Database Configuration

Django Matt provides first-class support for PostgreSQL (including pgvector), MySQL, and SQLite with modern connection pooling options for Django 5.2+.

## Quick Start

=== "Environment Variables"

    ```bash
    export DB_TYPE=postgres
    export DB_NAME=myapp
    export DB_USER=myuser
    export DB_PASSWORD=secret
    export DB_HOST=localhost
    export DB_PORT=5432
    ```

=== "Programmatic"

    ```python
    from django_matt.config.components.database import configure_database

    DATABASES = {
        "default": configure_database(
            db_type="postgres",
            name="myapp",
            user="myuser",
            password="secret",
            host="localhost",
            port="5432",
        )
    }
    ```

=== "Load Component"

    ```python
    from django_matt.config import configure

    configure(
        environment="production",
        components=["database"],
    )
    ```

## PostgreSQL Configuration

PostgreSQL is the recommended database for Django Matt applications.

### Basic Configuration

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "django_matt"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}
```

### Connection Pooling

Django Matt supports connection pooling for improved performance.

#### Django 5.2+ with psycopg3

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "myapp",
        "USER": "myuser",
        "PASSWORD": "secret",
        "HOST": "localhost",
        "PORT": "5432",
        # Persistent connections
        "CONN_MAX_AGE": None,
        # Health checks before reuse
        "CONN_HEALTH_CHECKS": True,
        # psycopg3 connection pool
        "OPTIONS": {
            "pool": {
                "min_size": 5,       # Minimum pool connections
                "max_size": 20,      # Maximum pool connections
                "max_idle": 300,     # Seconds before idle connection is closed
                "max_lifetime": 3600, # Max connection lifetime in seconds
                "timeout": 30,       # Seconds to wait for pool connection
            }
        },
    }
}
```

#### Environment Variables for Pooling

```bash
export DB_POOL_ENABLED=true
export DB_POOL_MIN_SIZE=5
export DB_POOL_MAX_SIZE=20
export DB_POOL_MAX_IDLE=300
export DB_POOL_MAX_LIFETIME=3600
export DB_POOL_TIMEOUT=30
```

### Connection Settings

| Setting | Description | Development | Production |
|---------|-------------|-------------|------------|
| `CONN_MAX_AGE` | Connection persistence | `60` | `None` (persistent) |
| `CONN_HEALTH_CHECKS` | Check connection before use | `True` | `True` |
| `ATOMIC_REQUESTS` | Wrap requests in transactions | `False` | `False` |
| `AUTOCOMMIT` | Enable autocommit | `True` | `True` |

```python
# Using configure_database helper
from django_matt.config.components.database import configure_database

DATABASES = {
    "default": configure_database(
        db_type="postgres",
        name="myapp",
        user="myuser",
        password="secret",
        conn_max_age=None,         # Persistent connections
        conn_health_checks=True,    # Django 5.1+
        pool_enabled=True,          # Django 5.2+ with psycopg3
        pool_min_size=5,
        pool_max_size=20,
    )
}
```

## pgvector Support

Django Matt provides utilities for working with PostgreSQL vector embeddings using pgvector.

### Installation

```bash
# Install the Python package
pip install django-pgvector

# Enable in PostgreSQL (requires superuser)
CREATE EXTENSION vector;
```

### Configuration

```bash
export DB_PGVECTOR_ENABLED=true
```

### Model Definition

```python
from django.db import models
from django_matt.db import VectorField

class Document(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    # 1536 dimensions for OpenAI embeddings
    embedding = VectorField(dimensions=1536)
```

### Migrations

```python
# migrations/0001_enable_pgvector.py
from django.db import migrations
from django_matt.db.postgres.vector import setup_pgvector

class Migration(migrations.Migration):
    operations = [
        migrations.RunPython(setup_pgvector),
    ]
```

### Vector Queries

```python
from django_matt.db import CosineDistance, L2Distance, MaxInnerProduct

# Get embedding from your embedding service
query_embedding = get_embedding("What is Django Matt?")

# Cosine similarity search (most common for text)
similar_docs = Document.objects.order_by(
    CosineDistance('embedding', query_embedding)
)[:10]

# L2 (Euclidean) distance
similar_docs = Document.objects.order_by(
    L2Distance('embedding', query_embedding)
)[:10]

# Max inner product (dot product)
similar_docs = Document.objects.order_by(
    MaxInnerProduct('embedding', query_embedding)
)[:10]
```

### Vector Manager

```python
from django_matt.db import vector_manager

# Convenience method for similarity search
similar_docs = vector_manager.similarity_search(
    queryset=Document.objects.all(),
    field_name="embedding",
    query_vector=query_embedding,
    distance_func="cosine",  # or "l2", "dot"
    limit=10,
)
```

### Vector Indexes

Create indexes for faster similarity search:

```python
from django_matt.db import create_vector_index
from myapp.models import Document

# IVFFlat index (good balance of speed and accuracy)
create_vector_index(Document, 'embedding', index_type='ivfflat', lists=100)

# HNSW index (faster but uses more memory)
create_vector_index(Document, 'embedding', index_type='hnsw')
```

## MySQL Configuration

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("DB_NAME", "django_matt"),
        "USER": os.environ.get("DB_USER", "root"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        "TEST": {
            "CHARSET": "utf8mb4",
            "COLLATION": "utf8mb4_unicode_ci",
        },
    }
}
```

### MySQL Environment Variables

```bash
export DB_TYPE=mysql
export DB_NAME=myapp
export DB_USER=root
export DB_PASSWORD=secret
export DB_HOST=localhost
export DB_PORT=3306
```

## SQLite Configuration

SQLite is useful for development and testing:

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
```

### SQLite Environment Variables

```bash
export DB_TYPE=sqlite
export DB_NAME=/path/to/db.sqlite3
```

## Multiple Databases

### Configuration

```python
DATABASES = {
    "default": configure_database(
        db_type="postgres",
        name="main_db",
        host="primary.db.example.com",
    ),
    "replica": configure_database(
        db_type="postgres",
        name="main_db",
        host="replica.db.example.com",
    ),
    "analytics": configure_database(
        db_type="postgres",
        name="analytics_db",
        host="analytics.db.example.com",
    ),
}
```

### Using JSON Environment Variable

```bash
export DB_MULTIPLE='{"replica":{"host":"replica.db.example.com","name":"main_db"},"analytics":{"host":"analytics.db.example.com","name":"analytics_db"}}'
```

### Database Router

```python
# myapp/db_routers.py
class PrimaryReplicaRouter:
    """Route reads to replica, writes to primary."""

    def db_for_read(self, model, **hints):
        return "replica"

    def db_for_write(self, model, **hints):
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db == "default"
```

```bash
export DB_ROUTERS=myapp.db_routers.PrimaryReplicaRouter
```

## Database Utilities

Django Matt provides utilities for database introspection:

```python
from django_matt.db import (
    get_db_type,
    get_db_version,
    is_postgres,
    is_mysql,
    is_sqlite,
    get_table_names,
    get_table_description,
    execute_raw_sql,
)

# Check database type
if is_postgres():
    print(f"PostgreSQL version: {get_db_version()}")

# List all tables
tables = get_table_names()

# Get table schema
columns = get_table_description("myapp_product")

# Execute raw SQL
results = execute_raw_sql(
    "SELECT * FROM myapp_product WHERE price > %s",
    params=[100],
    database="default",
)
```

### PostgreSQL Utilities

```python
from django_matt.db import (
    check_postgres_connection,
    is_postgres_version_compatible,
    create_extension,
    list_extensions,
    has_extension,
    execute_sql,
)

# Check PostgreSQL connection
if check_postgres_connection():
    print("PostgreSQL is connected")

# Check version compatibility
if is_postgres_version_compatible(14, 0):
    print("PostgreSQL 14+ features available")

# Manage extensions
create_extension("vector")
extensions = list_extensions()
if has_extension("vector"):
    print("pgvector is enabled")
```

## Connection Health Monitoring

### Health Check Endpoint

```python
# views.py
from django.http import JsonResponse
from django.db import connection
from django_matt.db import get_db_version, get_db_type

def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        return JsonResponse({
            "status": "healthy",
            "database": {
                "type": get_db_type(),
                "version": get_db_version(),
            }
        })
    except Exception as e:
        return JsonResponse({
            "status": "unhealthy",
            "error": str(e),
        }, status=503)
```

### Connection Metrics

```python
from django.db import connection

# Get connection info
print(f"Vendor: {connection.vendor}")
print(f"Database: {connection.settings_dict['NAME']}")

# Check if connected
print(f"Connected: {connection.is_usable()}")

# Connection queries (DEBUG=True only)
print(f"Query count: {len(connection.queries)}")
```

## Best Practices

### Development

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "myapp_dev",
        "USER": "postgres",
        "PASSWORD": "",
        "HOST": "localhost",
        "PORT": "5432",
        "CONN_MAX_AGE": 60,  # Short for dev
        "CONN_HEALTH_CHECKS": True,
    }
}
```

### Production

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.environ["DB_HOST"],
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": None,  # Persistent
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "pool": {
                "min_size": 5,
                "max_size": 20,
            }
        },
    }
}
```

### Testing

```python
# Use SQLite for faster tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Or use a test database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "myapp_test",
        "TEST": {
            "NAME": "myapp_test",
        },
    }
}
```

## Environment Variable Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_TYPE` | `postgres` | Database type |
| `DB_ENGINE` | Auto | Full engine path |
| `DB_NAME` | `django_matt` | Database name |
| `DB_USER` | `postgres` | Username |
| `DB_PASSWORD` | `""` | Password |
| `DB_HOST` | `localhost` | Host |
| `DB_PORT` | `5432` | Port |
| `DB_CONN_MAX_AGE` | `600` / `None` | Connection max age |
| `DB_CONN_HEALTH_CHECKS` | `True` | Enable health checks |
| `DB_ATOMIC_REQUESTS` | `False` | Atomic requests |
| `DB_AUTOCOMMIT` | `True` | Autocommit |
| `DB_TIME_ZONE` | None | Database timezone |
| `DB_TEST_NAME` | None | Test database name |
| `DB_OPTIONS` | `{}` | Additional options |
| `DB_POOL_ENABLED` | `False` | Enable pooling |
| `DB_POOL_MIN_SIZE` | `5` | Min pool size |
| `DB_POOL_MAX_SIZE` | `20` | Max pool size |
| `DB_POOL_MAX_IDLE` | `300` | Max idle seconds |
| `DB_POOL_MAX_LIFETIME` | `3600` | Max connection lifetime |
| `DB_POOL_TIMEOUT` | `30` | Pool timeout |
| `DB_PGVECTOR_ENABLED` | `False` | Enable pgvector |
| `DB_MULTIPLE` | None | JSON for multiple DBs |
| `DB_ROUTERS` | None | Database routers |
