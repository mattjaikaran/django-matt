# Database

- I want a way to fix the annoying migration issues while working within Django
- Can I have a way to notice when there is an issue with the database migrations and fix it?


## Database Types
- Postgres  
- SQLite
- MySQL

# Database Support in Django Matt

Django Matt provides first-class support for PostgreSQL while also supporting MySQL and SQLite with easy configuration. This document describes the database features and how to use them.

## Default Database Configuration

By default, Django Matt uses PostgreSQL as the database backend. This can be configured in your settings or environment variables.

### Configuration Options

You can configure the database in several ways:

1. **Environment Variables**:
   ```
   DB_TYPE=postgres  # or mysql, sqlite
   DB_ENGINE=django.db.backends.postgresql
   DB_NAME=myproject
   DB_USER=postgres
   DB_PASSWORD=mypassword
   DB_HOST=localhost
   DB_PORT=5432
   ```

2. **Settings Configuration**:
   ```python
   # In your settings.py
   settings = configure(
       # ...
       extra_settings={
           "DB_TYPE": "postgres",  # or mysql, sqlite
           # ...
       }
   )
   ```

3. **Command Line**:
   ```bash
   # When initializing a project
   python manage.py config init --db postgres  # or mysql, sqlite
   
   # When generating a settings file
   python manage.py config generate --db postgres
   
   # When generating an environment file
   python manage.py config env --db postgres
   ```

## PostgreSQL Features

Django Matt provides several PostgreSQL-specific features:

### Vector Support (pgvector)

Django Matt includes built-in support for [pgvector](https://github.com/pgvector/pgvector), which enables vector similarity search in PostgreSQL.

#### Installation

1. Install the required packages:
   ```bash
   pip install django-pgvector
   ```

2. Enable pgvector in your environment variables:
   ```
   DB_PGVECTOR_ENABLED=True
   ```

3. Create the extension in PostgreSQL:
   ```python
   from django_matt.db import setup_pgvector
   
   # In a migration
   from django.db import migrations
   
   class Migration(migrations.Migration):
       operations = [
           migrations.RunPython(setup_pgvector),
           # ...
       ]
   ```

#### Usage

```python
from django.db import models
from django_matt.db import VectorField, CosineDistance

class Document(models.Model):
    content = models.TextField()
    embedding = VectorField(dimensions=1536)  # OpenAI embedding dimensions

# Query by vector similarity
query_embedding = get_embedding("What is Django Matt?")
similar_docs = Document.objects.order_by(CosineDistance('embedding', query_embedding))[:10]
```

#### Vector Indexes

You can create vector indexes to speed up similarity searches:

```python
from django_matt.db import create_vector_index
from myapp.models import Document

# Create an IVFFlat index (faster search, approximate results)
create_vector_index(Document, 'embedding', index_type='ivfflat', lists=100)

# Create an HNSW index (faster search, better recall)
create_vector_index(Document, 'embedding', index_type='hnsw')

# Create a standard index (slower search, exact results)
create_vector_index(Document, 'embedding', index_type=None)
```

#### Similarity Search

Django Matt provides a utility for similarity search:

```python
from django_matt.db import vector_manager
from myapp.models import Document

# Get similar documents using cosine similarity
similar_docs = vector_manager.similarity_search(
    Document.objects.all(),
    'embedding',
    query_vector,
    distance_func='cosine',  # or 'l2', 'dot'
    limit=10
)
```

### Connection Pooling

Django Matt supports connection pooling for PostgreSQL, which can improve performance by reusing database connections.

#### Configuration

Enable connection pooling in your environment variables:

```
DB_POOL_ENABLED=True
DB_POOL_MAX_CONNS=20
DB_POOL_MIN_CONNS=5
DB_POOL_MAX_IDLE=300
```

### PostgreSQL Extensions

Django Matt provides utilities for working with PostgreSQL extensions:

```python
from django_matt.db import create_extension, list_extensions, has_extension

# Create an extension
create_extension('hstore')

# List all installed extensions
extensions = list_extensions()

# Check if an extension is installed
if has_extension('postgis'):
    # Use PostGIS features
    pass
```

### Raw SQL Execution

Django Matt provides a utility for executing raw SQL:

```python
from django_matt.db import execute_sql

# Execute a SQL query
results = execute_sql("SELECT * FROM my_table WHERE id = %s", [1])
```

## MySQL Support

Django Matt supports MySQL as a database backend. To use MySQL:

1. Set the database type to `mysql`:
   ```
   DB_TYPE=mysql
   ```

2. Configure the MySQL connection:
   ```
   DB_ENGINE=django.db.backends.mysql
   DB_NAME=myproject
   DB_USER=root
   DB_PASSWORD=mypassword
   DB_HOST=localhost
   DB_PORT=3306
   ```

## SQLite Support

Django Matt supports SQLite as a database backend. To use SQLite:

1. Set the database type to `sqlite`:
   ```
   DB_TYPE=sqlite
   ```

2. Configure the SQLite connection:
   ```
   DB_ENGINE=django.db.backends.sqlite3
   DB_NAME=db.sqlite3
   ```

## Multiple Databases

Django Matt supports multiple databases. You can configure them using the `DB_MULTIPLE` environment variable:

```
DB_MULTIPLE={"readonly": {"type": "postgres", "name": "readonly_db", "user": "readonly_user"}, "analytics": {"type": "mysql", "name": "analytics_db"}}
```

## Database Routers

Django Matt supports database routers. You can configure them using the `DB_ROUTERS` environment variable:

```
DB_ROUTERS=myapp.routers.PrimaryReplicaRouter,myapp.routers.AnalyticsRouter
```

## Database Utilities

Django Matt provides several database utilities:

### Database Type Detection

```python
from django_matt.db import get_db_type, is_postgres, is_mysql, is_sqlite

# Get the database type
db_type = get_db_type()  # 'postgresql', 'mysql', 'sqlite', etc.

# Check if using PostgreSQL
if is_postgres():
    # Use PostgreSQL-specific features
    pass

# Check if using MySQL
if is_mysql():
    # Use MySQL-specific features
    pass

# Check if using SQLite
if is_sqlite():
    # Use SQLite-specific features
    pass
```

### Database Version

```python
from django_matt.db import get_db_version

# Get the database version
version = get_db_version()
```

### Database Introspection

```python
from django_matt.db import get_table_names, get_table_description

# Get all table names
tables = get_table_names()

# Get table description
description = get_table_description('my_table')
```

## Best Practices

1. **Use PostgreSQL for Production**: PostgreSQL is the recommended database for production environments due to its robustness, feature set, and performance.

2. **Use SQLite for Development**: SQLite is a good choice for development environments due to its simplicity and zero configuration.

3. **Use Connection Pooling**: Enable connection pooling in production environments to improve performance.

4. **Use Vector Indexes**: If you're using pgvector, create appropriate indexes to improve search performance.

5. **Use Environment Variables**: Store database credentials in environment variables rather than hardcoding them in your settings.

6. **Use Database Routers**: If you're using multiple databases, use database routers to control which database to use for which operations.

7. **Use Migrations**: Always use Django migrations to manage your database schema.

## Troubleshooting

### PostgreSQL Connection Issues

If you're having trouble connecting to PostgreSQL:

1. Check that PostgreSQL is running:
   ```bash
   pg_isready -h localhost -p 5432
   ```

2. Check that the database exists:
   ```bash
   psql -U postgres -c "SELECT datname FROM pg_database WHERE datname='myproject'"
   ```

3. Check that the user has access to the database:
   ```bash
   psql -U myuser -d myproject -c "SELECT 1"
   ```

### pgvector Issues

If you're having trouble with pgvector:

1. Check that the extension is installed:
   ```python
   from django_matt.db import has_extension
   has_extension('vector')
   ```

2. Check that the extension is created in the database:
   ```sql
   SELECT * FROM pg_extension WHERE extname = 'vector';
   ```

3. Check that the vector field is properly defined:
   ```python
   from django_matt.db import VectorField
   field = VectorField(dimensions=1536)
   ```

## Further Reading

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [Django Database Documentation](https://docs.djangoproject.com/en/stable/ref/databases/)
- [Django Multiple Databases](https://docs.djangoproject.com/en/stable/topics/db/multi-db/)