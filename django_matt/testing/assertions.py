"""
Custom assertions for API testing.
"""

import json
from typing import Any, Dict, List, Optional, Union

from django.http import HttpResponse


def assert_status(
    response: HttpResponse,
    expected_status: int,
    message: Optional[str] = None,
):
    """
    Assert that the response has the expected status code.
    
    Args:
        response: HttpResponse object
        expected_status: Expected HTTP status code
        message: Optional custom message
    
    Raises:
        AssertionError: If status code doesn't match
    """
    if response.status_code != expected_status:
        try:
            body = json.loads(response.content)
        except (json.JSONDecodeError, ValueError):
            body = response.content.decode("utf-8", errors="replace")
        
        msg = message or (
            f"Expected status {expected_status}, got {response.status_code}. "
            f"Response: {body}"
        )
        raise AssertionError(msg)


def assert_json_equal(
    response: HttpResponse,
    expected: Dict[str, Any],
    message: Optional[str] = None,
):
    """
    Assert that the JSON response equals the expected dict.
    
    Args:
        response: HttpResponse object
        expected: Expected dictionary
        message: Optional custom message
    
    Raises:
        AssertionError: If JSON doesn't match
    """
    try:
        actual = json.loads(response.content)
    except (json.JSONDecodeError, ValueError) as e:
        raise AssertionError(f"Response is not valid JSON: {e}")
    
    if actual != expected:
        msg = message or f"JSON mismatch. Expected: {expected}, Got: {actual}"
        raise AssertionError(msg)


def assert_contains_keys(
    response: HttpResponse,
    keys: List[str],
    message: Optional[str] = None,
):
    """
    Assert that the JSON response contains all specified keys.
    
    Args:
        response: HttpResponse object
        keys: List of keys that must be present
        message: Optional custom message
    
    Raises:
        AssertionError: If any key is missing
    """
    try:
        data = json.loads(response.content)
    except (json.JSONDecodeError, ValueError) as e:
        raise AssertionError(f"Response is not valid JSON: {e}")
    
    if not isinstance(data, dict):
        raise AssertionError(f"Response is not a dict: {type(data)}")
    
    missing = [key for key in keys if key not in data]
    if missing:
        msg = message or f"Missing keys: {missing}. Got keys: {list(data.keys())}"
        raise AssertionError(msg)


def assert_error_response(
    response: HttpResponse,
    expected_status: int,
    error_key: str = "error",
    message: Optional[str] = None,
):
    """
    Assert that the response is an error with the expected status.
    
    Args:
        response: HttpResponse object
        expected_status: Expected HTTP status code
        error_key: Key in response containing error message
        message: Optional custom message
    
    Raises:
        AssertionError: If not an error response
    """
    assert_status(response, expected_status, message)
    
    try:
        data = json.loads(response.content)
    except (json.JSONDecodeError, ValueError) as e:
        raise AssertionError(f"Response is not valid JSON: {e}")
    
    if not isinstance(data, dict):
        raise AssertionError(f"Response is not a dict: {type(data)}")
    
    if error_key not in data and "detail" not in data and "message" not in data:
        raise AssertionError(
            f"Response doesn't contain error key. Keys: {list(data.keys())}"
        )


def assert_validation_error(
    response: HttpResponse,
    field: Optional[str] = None,
    message: Optional[str] = None,
):
    """
    Assert that the response is a validation error (422).
    
    Args:
        response: HttpResponse object
        field: Optional field name that should have an error
        message: Optional custom message
    
    Raises:
        AssertionError: If not a validation error
    """
    assert_status(response, 422, message)
    
    try:
        data = json.loads(response.content)
    except (json.JSONDecodeError, ValueError) as e:
        raise AssertionError(f"Response is not valid JSON: {e}")
    
    if field:
        # Check if the field has a validation error
        errors = data.get("errors", data.get("detail", []))
        if isinstance(errors, list):
            field_errors = [
                e for e in errors
                if field in e.get("loc", []) or e.get("field") == field
            ]
            if not field_errors:
                raise AssertionError(
                    f"No validation error for field '{field}'. Errors: {errors}"
                )


def assert_not_found(
    response: HttpResponse,
    message: Optional[str] = None,
):
    """
    Assert that the response is a 404 Not Found.
    
    Args:
        response: HttpResponse object
        message: Optional custom message
    
    Raises:
        AssertionError: If not a 404 response
    """
    assert_status(response, 404, message)


def assert_forbidden(
    response: HttpResponse,
    message: Optional[str] = None,
):
    """
    Assert that the response is a 403 Forbidden.
    
    Args:
        response: HttpResponse object
        message: Optional custom message
    
    Raises:
        AssertionError: If not a 403 response
    """
    assert_status(response, 403, message)


def assert_unauthorized(
    response: HttpResponse,
    message: Optional[str] = None,
):
    """
    Assert that the response is a 401 Unauthorized.
    
    Args:
        response: HttpResponse object
        message: Optional custom message
    
    Raises:
        AssertionError: If not a 401 response
    """
    assert_status(response, 401, message)


def assert_created(
    response: HttpResponse,
    message: Optional[str] = None,
):
    """
    Assert that the response is a 201 Created.
    
    Args:
        response: HttpResponse object
        message: Optional custom message
    
    Raises:
        AssertionError: If not a 201 response
    """
    assert_status(response, 201, message)


def assert_no_content(
    response: HttpResponse,
    message: Optional[str] = None,
):
    """
    Assert that the response is a 204 No Content.
    
    Args:
        response: HttpResponse object
        message: Optional custom message
    
    Raises:
        AssertionError: If not a 204 response
    """
    assert_status(response, 204, message)


def assert_list_response(
    response: HttpResponse,
    min_count: Optional[int] = None,
    max_count: Optional[int] = None,
    items_key: str = "items",
    count_key: str = "count",
    message: Optional[str] = None,
):
    """
    Assert that the response is a valid list response.
    
    Args:
        response: HttpResponse object
        min_count: Minimum expected count
        max_count: Maximum expected count
        items_key: Key for the items list
        count_key: Key for the count
        message: Optional custom message
    
    Raises:
        AssertionError: If not a valid list response
    """
    assert_status(response, 200, message)
    
    try:
        data = json.loads(response.content)
    except (json.JSONDecodeError, ValueError) as e:
        raise AssertionError(f"Response is not valid JSON: {e}")
    
    if not isinstance(data, dict):
        # Maybe it's a direct list
        if isinstance(data, list):
            items = data
            count = len(data)
        else:
            raise AssertionError(f"Response is not a dict or list: {type(data)}")
    else:
        items = data.get(items_key, data.get("results", []))
        count = data.get(count_key, data.get("total", len(items)))
    
    if min_count is not None and count < min_count:
        raise AssertionError(
            f"Expected at least {min_count} items, got {count}"
        )
    
    if max_count is not None and count > max_count:
        raise AssertionError(
            f"Expected at most {max_count} items, got {count}"
        )


def assert_pagination(
    response: HttpResponse,
    page: int = 1,
    page_size: int = 10,
    message: Optional[str] = None,
):
    """
    Assert that the response contains pagination info.
    
    Args:
        response: HttpResponse object
        page: Expected current page
        page_size: Expected page size
        message: Optional custom message
    
    Raises:
        AssertionError: If pagination is invalid
    """
    assert_status(response, 200, message)
    
    try:
        data = json.loads(response.content)
    except (json.JSONDecodeError, ValueError) as e:
        raise AssertionError(f"Response is not valid JSON: {e}")
    
    # Check for common pagination keys
    pagination_keys = ["page", "page_size", "total", "total_pages", "next", "previous"]
    has_pagination = any(key in data for key in pagination_keys)
    
    if not has_pagination:
        raise AssertionError(
            f"Response doesn't contain pagination. Keys: {list(data.keys())}"
        )
