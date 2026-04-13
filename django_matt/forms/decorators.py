"""
Form view decorators for AJAX/HTMX/fetch integration.

Provides decorators that make Django form views return JSON responses
when called via XHR/HTMX/fetch, while preserving normal behavior
for standard browser requests.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from django.http import HttpRequest, HttpResponse, JsonResponse

logger = logging.getLogger("django_matt.forms")


def _is_ajax(request: HttpRequest) -> bool:
    """Detect AJAX/HTMX/fetch requests."""
    # HTMX
    if request.headers.get("HX-Request"):
        return True
    # XMLHttpRequest
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    # Accept header indicates JSON
    accept = request.headers.get("Accept", "")
    if "application/json" in accept:
        return True
    return False


def _form_errors_dict(form: Any) -> dict[str, list[str]]:
    """Extract form errors as a plain dict."""
    errors: dict[str, list[str]] = {}
    for field_name, error_list in form.errors.items():
        errors[field_name] = [str(e) for e in error_list]
    return errors


def ajax_form(
    success_url: str | None = None,
    success_data: Callable[..., dict[str, Any]] | None = None,
) -> Callable:
    """
    Decorator for form views that returns JSON on AJAX/HTMX/fetch requests.

    On AJAX requests:
      - Success: {"success": true, "redirect": url} or {"success": true, "data": {...}}
      - Validation error: {"success": false, "errors": {"field": ["message"]}}

    On regular requests: normal Django form handling (returns HttpResponse).

    Works with both function-based views and CBV methods.

    Usage (function view):
        @ajax_form(success_url="/dashboard/")
        def contact_view(request):
            if request.method == "POST":
                form = ContactForm(request.POST)
                if form.is_valid():
                    form.save()
                    return form  # Return the valid form; decorator handles response
                return form  # Return invalid form; decorator sends errors
            return ContactForm()

    Usage (CBV):
        class ContactView(FormView):
            form_class = ContactForm

            @ajax_form(success_url="/dashboard/")
            def post(self, request, *args, **kwargs):
                form = self.get_form()
                if form.is_valid():
                    return self.form_valid(form)
                return form

    Args:
        success_url: URL to redirect to on success (returned in JSON as "redirect").
        success_data: Callable that receives the form and returns extra data for success response.
    """

    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(*args: Any, **kwargs: Any) -> HttpResponse:
            # Extract request from args (works for both FBV and CBV)
            request: HttpRequest | None = None
            for arg in args:
                if isinstance(arg, HttpRequest):
                    request = arg
                    break

            if request is None:
                # Could be CBV where self is first arg
                if len(args) >= 2 and isinstance(args[1], HttpRequest):
                    request = args[1]

            if request is None or not _is_ajax(request):
                return view_func(*args, **kwargs)

            try:
                result = view_func(*args, **kwargs)
            except Exception:
                logger.exception("Form view error")
                return JsonResponse(
                    {"success": False, "errors": {"__all__": ["An unexpected error occurred."]}},
                    status=500,
                )

            # If result is already an HttpResponse, pass through
            if isinstance(result, HttpResponse):
                # Check if it's a redirect (success case in standard Django)
                if hasattr(result, "url"):
                    redirect_url = success_url or getattr(result, "url", "/")
                    return JsonResponse({"success": True, "redirect": redirect_url})
                return result

            # If result is a form instance
            if hasattr(result, "is_valid") and hasattr(result, "errors"):
                if result.is_bound and not result.errors:
                    # Valid form
                    response_data: dict[str, Any] = {"success": True}
                    if success_url:
                        response_data["redirect"] = success_url
                    if success_data is not None:
                        response_data["data"] = success_data(result)
                    return JsonResponse(response_data)

                if result.errors:
                    # Invalid form
                    return JsonResponse(
                        {"success": False, "errors": _form_errors_dict(result)},
                        status=422,
                    )

                # Unbound form (GET) — shouldn't normally happen in POST handler
                return JsonResponse({"success": True})

            # If result is a dict, return as-is
            if isinstance(result, dict):
                return JsonResponse(result)

            # Fallback
            return JsonResponse({"success": True})

        return wrapper

    return decorator
