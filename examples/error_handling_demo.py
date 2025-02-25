"""
Example demonstrating Django Matt's enhanced error handling.

This example shows how to use the error handling features of Django Matt
to provide detailed error information and suggestions.

To run this example:
1. Install Django and Django Matt
2. Run this script with Python

"""

import os
import sys

import django
from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.http import HttpResponse, JsonResponse
from django.urls import path
from pydantic import Field, ValidationError

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
            "django_matt.utils.errors.ErrorMiddleware",
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
    )
    django.setup()

# Import Django Matt components
from django_matt import APIRouter, error_handler
from django_matt.core.schema import Schema


# Define a schema for our example
class UserSchema(Schema):
    """User schema for demonstration."""

    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., regex=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    age: int = Field(..., ge=18, le=120)


# Create a router
router = APIRouter()


# Example endpoint with error handling
@router.post("api/users/")
@error_handler
async def create_user(request):
    """Create a new user with error handling."""
    try:
        # Parse the request body
        if not request.body:
            raise ValueError("Request body is empty")

        import json

        data = json.loads(request.body)

        # Validate the data against our schema
        user = UserSchema(**data)

        # Simulate a database operation
        if user.username == "admin":
            raise PermissionError("Cannot create user with username 'admin'")

        # Return the created user
        return {"status": "success", "user": user.model_dump()}
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON in request body"}, status=400)
    except ValidationError:
        # The error_handler decorator will handle this
        raise


# Example endpoint that will cause a division by zero error
@router.get("api/error-demo/")
@error_handler
async def error_demo(request):
    """Demonstrate error handling with a deliberate error."""
    # This will cause a division by zero error
    result = 1 / 0
    return {"result": result}


# Example endpoint that will cause a type error
@router.get("api/type-error/")
@error_handler
async def type_error_demo(request):
    """Demonstrate error handling with a type error."""
    # This will cause a type error
    result = "string" + 123
    return {"result": result}


# Example endpoint that will cause an attribute error
@router.get("api/attribute-error/")
@error_handler
async def attribute_error_demo(request):
    """Demonstrate error handling with an attribute error."""

    # This will cause an attribute error
    class Example:
        pass

    obj = Example()
    result = obj.nonexistent_attribute
    return {"result": result}


# Create URL patterns
urlpatterns = router.get_urls()


# Add a simple HTML page to test the error handling
def index_view(request):
    """Simple HTML page to test the error handling."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Django Matt Error Handling Demo</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            h1 { color: #333; }
            .endpoint { background: #f5f5f5; padding: 15px; margin-bottom: 15px; border-radius: 5px; }
            .endpoint h3 { margin-top: 0; }
            button { background: #4CAF50; color: white; border: none; padding: 10px 15px; cursor: pointer; }
            pre { background: #f9f9f9; padding: 10px; overflow: auto; }
            #result { margin-top: 20px; }
        </style>
    </head>
    <body>
        <h1>Django Matt Error Handling Demo</h1>
        
        <div class="endpoint">
            <h3>Create User (Validation Error)</h3>
            <button onclick="testCreateUser()">Test</button>
            <p>This will trigger a validation error.</p>
        </div>
        
        <div class="endpoint">
            <h3>Division by Zero Error</h3>
            <button onclick="testDivisionByZero()">Test</button>
            <p>This will trigger a division by zero error.</p>
        </div>
        
        <div class="endpoint">
            <h3>Type Error</h3>
            <button onclick="testTypeError()">Test</button>
            <p>This will trigger a type error.</p>
        </div>
        
        <div class="endpoint">
            <h3>Attribute Error</h3>
            <button onclick="testAttributeError()">Test</button>
            <p>This will trigger an attribute error.</p>
        </div>
        
        <div id="result">
            <h2>Response:</h2>
            <pre id="response"></pre>
        </div>
        
        <script>
            async function testCreateUser() {
                try {
                    const response = await fetch('/api/users/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            username: 'a',  // Too short
                            email: 'invalid-email',  // Invalid email
                            age: 10,  // Too young
                        }),
                    });
                    
                    const data = await response.json();
                    document.getElementById('response').textContent = JSON.stringify(data, null, 2);
                } catch (error) {
                    document.getElementById('response').textContent = error.toString();
                }
            }
            
            async function testDivisionByZero() {
                try {
                    const response = await fetch('/api/error-demo/');
                    const data = await response.json();
                    document.getElementById('response').textContent = JSON.stringify(data, null, 2);
                } catch (error) {
                    document.getElementById('response').textContent = error.toString();
                }
            }
            
            async function testTypeError() {
                try {
                    const response = await fetch('/api/type-error/');
                    const data = await response.json();
                    document.getElementById('response').textContent = JSON.stringify(data, null, 2);
                } catch (error) {
                    document.getElementById('response').textContent = error.toString();
                }
            }
            
            async function testAttributeError() {
                try {
                    const response = await fetch('/api/attribute-error/');
                    const data = await response.json();
                    document.getElementById('response').textContent = JSON.stringify(data, null, 2);
                } catch (error) {
                    document.getElementById('response').textContent = error.toString();
                }
            }
        </script>
    </body>
    </html>
    """
    return HttpResponse(html)


urlpatterns.append(path("", index_view))

# Run the application
if __name__ == "__main__":
    from django.core.management import execute_from_command_line

    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])
else:
    # For WSGI servers
    application = get_wsgi_application()
