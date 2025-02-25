# Todo App Example

This is a simple Todo app example using the Django Matt framework.

## Features

- CRUD operations for Todo items
- Class-based controllers with async support
- Pydantic schemas for validation
- Error handling with appropriate status codes

## Usage

1. Add the app to your Django project's `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    'examples.todo_app',
    # ...
]
```

2. Include the app's URLs in your project's `urls.py`:

```python
from django.urls import path, include

urlpatterns = [
    # ...
    path('', include('examples.todo_app.urls')),
    # ...
]
```

3. Run migrations:

```bash
python manage.py makemigrations
python manage.py migrate
```

4. Start the development server:

```bash
python manage.py runserver
```

## API Endpoints

- `GET /api/todos/` - Get all todo items
- `GET /api/todos/{id}/` - Get a specific todo item
- `POST /api/todos/` - Create a new todo item
- `PUT /api/todos/{id}/` - Update an existing todo item
- `DELETE /api/todos/{id}/` - Delete a todo item

## Example Requests

### Create a Todo

```bash
curl -X POST http://localhost:8000/api/todos/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Learn Django Matt", "description": "Build a Todo app with Django Matt", "completed": false}'
```

### Get All Todos

```bash
curl -X GET http://localhost:8000/api/todos/
```

### Get a Specific Todo

```bash
curl -X GET http://localhost:8000/api/todos/123e4567-e89b-12d3-a456-426614174000/
```

### Update a Todo

```bash
curl -X PUT http://localhost:8000/api/todos/123e4567-e89b-12d3-a456-426614174000/ \
  -H "Content-Type: application/json" \
  -d '{"completed": true}'
```

### Delete a Todo

```bash
curl -X DELETE http://localhost:8000/api/todos/123e4567-e89b-12d3-a456-426614174000/
``` 