"""
Error Handling Demo for Django Matt.

This example demonstrates the automatic error handling in controllers.
"""

import os
import sys
from typing import Any

# Add the parent directory to the path so we can import django_matt
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import django
from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.urls import path

from django_matt.core.controller import APIController
from django_matt.core.errors import (
    APIError,
    NotFoundAPIError,
    PermissionAPIError,
    ValidationAPIError,
)
from django_matt.core.router import Router, get

# Configure Django settings
if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY="demo-secret-key",
        ROOT_URLCONF=__name__,
        MIDDLEWARE=[
            "django.middleware.common.CommonMiddleware",
            "django_matt.core.errors.ErrorMiddleware",
        ],
    )
    django.setup()


# Create a router
api = Router()


# Create a controller with automatic error handling
class ErrorDemoController(APIController):
    """Demo controller for error handling."""

    prefix = "errors/"

    @get("basic")
    async def basic_error(self, request: HttpRequest) -> dict[str, Any]:
        """Demonstrate a basic error."""
        # This will raise a ZeroDivisionError
        return {"result": 1 / 0}

    @get("not-found")
    async def not_found_error(self, request: HttpRequest) -> dict[str, Any]:
        """Demonstrate a not found error."""
        # Raise a NotFoundAPIError
        raise NotFoundAPIError(
            message="Item not found",
            resource_type="Item",
            resource_id="123",
        )

    @get("permission")
    async def permission_error(self, request: HttpRequest) -> dict[str, Any]:
        """Demonstrate a permission error."""
        # Raise a PermissionAPIError
        raise PermissionAPIError(
            message="You don't have permission to access this resource",
            required_permission="admin",
        )

    @get("validation")
    async def validation_error(self, request: HttpRequest) -> dict[str, Any]:
        """Demonstrate a validation error."""
        # Raise a ValidationAPIError
        raise ValidationAPIError(
            message="Validation failed",
            errors=[
                {"field": "name", "message": "Name is required"},
                {"field": "email", "message": "Invalid email format"},
            ],
        )

    @get("custom")
    async def custom_error(self, request: HttpRequest) -> dict[str, Any]:
        """Demonstrate a custom API error."""
        # Raise a custom APIError
        raise APIError(
            message="Something went wrong",
            status_code=400,
            code="custom_error",
            context={"additional_info": "This is a custom error"},
        )

    @get("key-error")
    async def key_error(self, request: HttpRequest) -> dict[str, Any]:
        """Demonstrate a KeyError."""
        # This will raise a KeyError
        data = {}
        return {"result": data["non_existent_key"]}

    @get("attribute-error")
    async def attribute_error(self, request: HttpRequest) -> dict[str, Any]:
        """Demonstrate an AttributeError."""
        # This will raise an AttributeError
        return {"result": request.non_existent_attribute}

    @get("type-error")
    async def type_error(self, request: HttpRequest) -> dict[str, Any]:
        """Demonstrate a TypeError."""
        # This will raise a TypeError
        return {"result": "string" + 123}

    @get("index-error")
    async def index_error(self, request: HttpRequest) -> dict[str, Any]:
        """Demonstrate an IndexError."""
        # This will raise an IndexError
        data = [1, 2, 3]
        return {"result": data[10]}

    @get("value-error")
    async def value_error(self, request: HttpRequest) -> dict[str, Any]:
        """Demonstrate a ValueError."""
        # This will raise a ValueError
        return {"result": int("not a number")}


# Create a controller with custom error handling
class CustomErrorHandlingController(APIController):
    """Demo controller with custom error handling."""

    prefix = "custom-handling/"

    def handle_exception(
        self, exc: Exception, request: HttpRequest = None
    ) -> JsonResponse:
        """Custom exception handler."""
        # Handle ZeroDivisionError specially
        if isinstance(exc, ZeroDivisionError):
            return JsonResponse(
                {
                    "error": "Cannot divide by zero",
                    "suggestion": "Try using a non-zero divisor",
                },
                status=400,
            )

        # Handle KeyError specially
        if isinstance(exc, KeyError):
            return JsonResponse(
                {
                    "error": f"Key '{exc.args[0]}' not found",
                    "suggestion": "Check the available keys before accessing",
                },
                status=400,
            )

        # Fall back to default handling for other exceptions
        return super().handle_exception(exc, request)

    @get("zero-division")
    async def zero_division(self, request: HttpRequest) -> dict[str, Any]:
        """Demonstrate custom handling of ZeroDivisionError."""
        return {"result": 1 / 0}

    @get("key-error")
    async def key_error(self, request: HttpRequest) -> dict[str, Any]:
        """Demonstrate custom handling of KeyError."""
        data = {}
        return {"result": data["non_existent_key"]}

    @get("other-error")
    async def other_error(self, request: HttpRequest) -> dict[str, Any]:
        """Demonstrate fallback to default handling."""
        return {"result": "string" + 123}


# Create a controller with disabled error handling
class DisabledErrorHandlingController(APIController):
    """Demo controller with disabled error handling."""

    prefix = "disabled-handling/"
    auto_error_handling = False  # Disable automatic error handling

    @get("manual-handling")
    async def manual_handling(self, request: HttpRequest) -> dict[str, Any]:
        """Demonstrate manual error handling."""
        try:
            result = 1 / 0
            return {"result": result}
        except Exception as e:
            return JsonResponse(
                {
                    "error": "An error occurred",
                    "message": str(e),
                    "type": e.__class__.__name__,
                },
                status=500,
            )

    @get("no-handling")
    async def no_handling(self, request: HttpRequest) -> dict[str, Any]:
        """Demonstrate no error handling (will be caught by middleware)."""
        return {"result": 1 / 0}


# Register controllers
api.include_controller(ErrorDemoController())
api.include_controller(CustomErrorHandlingController())
api.include_controller(DisabledErrorHandlingController())


# Create a simple index view
def index(request):
    """Index view with links to error examples."""
    links = [
        {"url": "/api/errors/basic", "description": "Basic error (ZeroDivisionError)"},
        {"url": "/api/errors/not-found", "description": "Not found error"},
        {"url": "/api/errors/permission", "description": "Permission error"},
        {"url": "/api/errors/validation", "description": "Validation error"},
        {"url": "/api/errors/custom", "description": "Custom API error"},
        {"url": "/api/errors/key-error", "description": "Key error"},
        {"url": "/api/errors/attribute-error", "description": "Attribute error"},
        {"url": "/api/errors/type-error", "description": "Type error"},
        {"url": "/api/errors/index-error", "description": "Index error"},
        {"url": "/api/errors/value-error", "description": "Value error"},
        {
            "url": "/api/custom-handling/zero-division",
            "description": "Custom handling of ZeroDivisionError",
        },
        {
            "url": "/api/custom-handling/key-error",
            "description": "Custom handling of KeyError",
        },
        {
            "url": "/api/custom-handling/other-error",
            "description": "Fallback to default handling",
        },
        {
            "url": "/api/disabled-handling/manual-handling",
            "description": "Manual error handling",
        },
        {
            "url": "/api/disabled-handling/no-handling",
            "description": "No error handling (caught by middleware)",
        },
    ]

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Django Matt Error Handling Demo</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            h1 { color: #333; }
            ul { list-style-type: none; padding: 0; }
            li { margin-bottom: 10px; }
            a { color: #0066cc; text-decoration: none; }
            a:hover { text-decoration: underline; }
            .note { background-color: #f8f9fa; padding: 10px; border-left: 4px solid #0066cc; margin-bottom: 20px; }
        </style>
    </head>
    <body>
        <h1>Django Matt Error Handling Demo</h1>
        <div class="note">
            <p>This demo shows how Django Matt's automatic error handling works in controllers.</p>
            <p>Click on the links below to see different types of errors and how they are handled.</p>
        </div>
        <ul>
    """

    for link in links:
        html += f'<li><a href="{link["url"]}">{link["description"]}</a></li>'

    html += """
        </ul>
    </body>
    </html>
    """

    return HttpResponse(html)


# URL patterns
urlpatterns = [
    path("", index),
    path("api/", api.urls),
]


# Run the server
if __name__ == "__main__":
    from django.core.management import execute_from_command_line

    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])
