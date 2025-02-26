# Django Matt Framework

A lightweight, high-performance Django extension for building modern APIs with minimal boilerplate.


# Django Matt

New Django API framework started Feb 2025.

I want to build my own custom API framework for Django because I feel like it.

v1 is just for me. not meant for mass adoption.

Reasons: 
- I want to learn something new and do a project I've never done before. 
    - This seems like a tough project but I'm looking forward to learning a lot.
- Lots of new Rust based tooling and other tools to enhance Python frameworks.
- I want to build a framework that has the things I need and use and find useful.
    - DX scripts to enhance productivity
    - Mixins to enhance functionality
    - CRUD generation to enhance productivity
    - I want a config folder
        - I want the config folder data to be used as a cleaner more organized way to manage the settings.py file
        - I want to be able to have different settings for different environments.
        - I want to be able to have different settings for different apps.
    - I want a deployment folder
    - I want a docs folder
    - I want a machine learning folder
    - I want a templates folder
    - I want a tests folder
    - I want a utils folder
    - I want a views folder
- I don't really enjoy how settings.py is used in Django. I want to try something different. 
- Inspired by several frameworks and tools: 
    - Django Rest Framework: mixins
    - Django Ninja: fast, newer, easy, flexible, async supported, pydantic supported
    - Django Ninja Extra: extra features to add class based views to Django Ninja
    - FastAPI: fast, can be lightweight and simple or complex
    - FastUI: React and FastAPI minimalistic full stack framework
    - Ruby on Rails: CLI integration, crud generation
        - https://guides.rubyonrails.org/command_line.html
    - [InertiaJS](https://inertiajs.com/): build single page apps with Django
- Built in Authentication and Permissions
    - JWT
    - Passwordless login
        - Email 
        - Magic Link
        - Passkeys
        - WebAuthn
    - OAuth
    - Social Auth
    - Multi tenant
- LLM/AI IDE integration
    - Cursor context files
    - I want others using this framework to have the best experience with LLM/AI IDE integration. 
- tRPC like experience. 
    - I want to sync Pydantic models on the back end and TypeScript interfaces on the front end for end to end type safety.
    - I want to generate the TypeScript interfaces automatically from the Pydantic models.
        - The TypeScript interfaces should be able to be used in the front end
        - There should be a conversion of types casing from Pydantic models to TypeScript interfaces
            - ie: datimetime_created => datetimeCreated
- I want some kind of easy deployment process. 
    - Support for Docker
    - Support for Digital Ocean
    - Support for Fly.io
    - Support for PlanetScale
    - Support for Railway
    - Support for Render
    - Support for AWS


## Advanced Performance Features

Django Matt includes several advanced performance features to help you build faster, more efficient APIs:

### 1. Fast JSON Serialization

Django Matt provides optimized JSON serialization using the fastest available JSON libraries:

- **`FastJSONRenderer`**: Automatically uses the fastest available JSON library (orjson > ujson > json)
- **`FastJsonResponse`**: Drop-in replacement for Django's JsonResponse with improved performance

```python
from django_matt import FastJsonResponse

def my_view(request):
    return FastJsonResponse({"data": my_data})
```

### 2. MessagePack Serialization

For even faster serialization and smaller payload sizes, Django Matt supports MessagePack:

- **`MessagePackRenderer`**: Efficient binary serialization with MessagePack
- **`MessagePackResponse`**: HTTP response that renders content as MessagePack

```python
from django_matt import MessagePackResponse

def my_view(request):
    return MessagePackResponse({"data": my_data})
```

### 3. Streaming Responses

For large datasets, Django Matt provides streaming response capabilities:

- **`StreamingJsonResponse`**: Stream large JSON datasets without loading everything into memory
- **`stream_json_list`**: Helper function to stream JSON lists efficiently

```python
from django_matt import StreamingJsonResponse, stream_json_list

def my_view(request):
    def items_generator():
        for item in large_dataset:
            yield item
    
    return StreamingJsonResponse(
        streaming_content=stream_json_list(items_generator())
    )
```

### 4. Caching Mechanisms

Django Matt includes a powerful caching system for API responses:

- **`CacheManager`**: Manage caching of API responses
- **`cache_response`**: Decorator to cache entire responses
- **`cache_result`**: Decorator to cache function results

```python
from django_matt import cache_manager

@cache_manager.cache_response(timeout=60)  # Cache for 60 seconds
def my_view(request):
    # Expensive operation
    return FastJsonResponse({"data": expensive_operation()})
```

### 5. Performance Benchmarking

Django Matt provides tools to measure and optimize API performance:

- **`APIBenchmark`**: Measure the performance of API endpoints
- **`benchmark`**: Decorator to measure execution time
- **`BenchmarkMiddleware`**: Middleware to automatically benchmark all requests

```python
from django_matt import benchmark

@benchmark.measure('my_operation')
def expensive_operation():
    # Expensive operation
    return result

# Get benchmark results
benchmark_results = benchmark.get_report()
```

## Database Support

Django Matt provides first-class support for PostgreSQL while also supporting MySQL and SQLite with easy configuration.

### 1. PostgreSQL as Default

PostgreSQL is the default database backend in Django Matt, offering robust features and performance:

```python
# PostgreSQL is configured by default
settings = configure(
    environment='development',
    components=['database', 'cache', 'security', 'performance'],
)
```

### 2. Vector Support with pgvector

Django Matt includes built-in support for pgvector, enabling vector similarity search in PostgreSQL:

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

### 3. Easy Database Configuration

Configure your database with environment variables or settings:

```python
# Environment variables
DB_TYPE=postgres  # or mysql, sqlite
DB_NAME=myproject
DB_USER=postgres
DB_PASSWORD=mypassword

# Or in settings
settings = configure(
    extra_settings={
        "DB_TYPE": "postgres",
    }
)
```

### 4. Multiple Database Support

Django Matt supports multiple databases and database routers:

```python
# Configure multiple databases
DB_MULTIPLE={"readonly": {"type": "postgres", "name": "readonly_db"}, "analytics": {"type": "mysql", "name": "analytics_db"}}

# Configure database routers
DB_ROUTERS=myapp.routers.PrimaryReplicaRouter,myapp.routers.AnalyticsRouter
```

For more information, see the [Database documentation](docs/database.md).

## Configuration System

Django Matt provides a more organized and flexible approach to Django settings management:

### 1. Modular Settings Organization

- **Separate settings by concern**: Database, cache, security, and performance settings are organized into separate modules
- **Support for multiple environments**: Development, staging, and production environments have their own settings
- **Component-based configuration**: Load only the components you need

```python
from django_matt.config import configure

# Configure the application
settings = configure(
    environment='development',
    components=['database', 'cache', 'security', 'performance'],
    extra_settings={
        'ROOT_URLCONF': 'myproject.urls',
        'WSGI_APPLICATION': 'myproject.wsgi.application',
    },
)
```

### 2. Environment Variable Integration

- **Load settings from environment variables**: Sensitive information is loaded from environment variables
- **Environment-specific defaults**: Each environment has sensible defaults
- **Utility functions**: Helper functions for working with environment variables

```python
from django_matt.config.utils import get_env_bool, get_env_list

# Get a boolean value from an environment variable
debug = get_env_bool('DEBUG', False)

# Get a list value from an environment variable
allowed_hosts = get_env_list('ALLOWED_HOSTS', ['localhost'], ',')
```

### 3. Configuration Management Command

Django Matt includes a management command for working with configuration files:

```bash
# Initialize configuration files for your project
python manage.py config init

# Generate a settings.py file for a specific environment
python manage.py config generate --env production

# Generate a .env file for a specific environment
python manage.py config env --env staging
```

For more information, see the [Configuration System documentation](docs/configuration_system.md).

## Command-Line Tools

Django Matt provides several command-line tools to help you manage your Django projects:

### 1. Configuration Management

```bash
python manage.py config init      # Initialize configuration files
python manage.py config generate  # Generate a settings.py file
python manage.py config env       # Generate a .env file
```

### 2. Hot Reloading

```bash
python manage.py runserver_hot    # Run the development server with hot reloading
```

For more information, see the [CLI Tools documentation](docs/cli_tools.md).

## Example

Check out the `examples/advanced_performance_demo.py` file for a complete example of these features in action.

To run the example:

```bash
# Install required dependencies
pip install django msgpack

# Run the example
python examples/advanced_performance_demo.py
```

Then open your browser at http://localhost:8000 to see the demo.

## Installation

```bash
pip install django-matt
```

## Optional Dependencies

For optimal performance, install these optional dependencies:

```bash
pip install orjson ujson msgpack redis django-pgvector
```

## Features
- [UV](https://docs.astral.sh/uv/) package manager
- [Ruff](https://beta.ruff.rs/) for linting and formatting
- Class based views first class support
- CRUD generation
    - Generate front end and back end code for CRUD operations
- Generate Django models from Pydantic models
- Authentication
    - JWT
    - Passwordless login
        - Email 
        - Magic Link
        - Passkeys
        - WebAuthn
    - API Keys
- Docs
    - OpenAPI and Swagger
- Rate Limiting
- Caching
- Configuration System
    - Modular settings organization
    - Environment-specific settings
    - Component-based configuration
- Command-Line Tools
    - Configuration management
    - Hot reloading
- Database Support
    - First-class PostgreSQL support
    - pgvector integration for vector similarity search
    - Easy configuration for MySQL and SQLite
    - Multiple database support
    - Connection pooling

## Tech Stack

- Python 3.10+
- Django 5.1+
- PostgreSQL (recommended)


