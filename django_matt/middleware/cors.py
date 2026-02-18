"""CORS middleware — configurable origins, preflight, credentials."""

from django.conf import settings
from django.http import HttpResponse


class CORSMiddleware:
    """
    Handle Cross-Origin Resource Sharing.

    Configured via settings.DJANGO_MATT["CORS"]. All config cached at __init__.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        matt_config = getattr(settings, "DJANGO_MATT", {})
        cors = matt_config.get("CORS", {})

        origins = cors.get("ALLOWED_ORIGINS", [])
        if origins is True or origins == ["*"]:
            self.allow_all = True
            self.allowed_origins = set()
        else:
            self.allow_all = False
            self.allowed_origins = set(origins)

        self.allow_credentials = cors.get("ALLOW_CREDENTIALS", False)
        self.allow_methods = cors.get(
            "ALLOW_METHODS", ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
        )
        self.allow_headers = cors.get(
            "ALLOW_HEADERS",
            ["Accept", "Authorization", "Content-Type", "X-Request-ID"],
        )
        self.expose_headers = cors.get("EXPOSE_HEADERS", ["X-Request-ID", "X-Response-Time"])
        self.max_age = cors.get("MAX_AGE", 86400)
        self.enabled = cors.get("ENABLED", True)

    def __call__(self, request):
        if not self.enabled:
            return self.get_response(request)

        # Handle preflight
        if request.method == "OPTIONS":
            response = HttpResponse(status=204)
            self._add_cors_headers(request, response)
            return response

        response = self.get_response(request)
        self._add_cors_headers(request, response)
        return response

    def _add_cors_headers(self, request, response):
        origin = request.META.get("HTTP_ORIGIN")
        if not origin:
            return

        if self.allow_all:
            response["Access-Control-Allow-Origin"] = "*"
        elif origin in self.allowed_origins:
            response["Access-Control-Allow-Origin"] = origin
            response["Vary"] = "Origin"
        else:
            return

        if self.allow_credentials:
            response["Access-Control-Allow-Credentials"] = "true"

        if request.method == "OPTIONS":
            response["Access-Control-Allow-Methods"] = ", ".join(self.allow_methods)
            response["Access-Control-Allow-Headers"] = ", ".join(self.allow_headers)
            if self.max_age:
                response["Access-Control-Max-Age"] = str(self.max_age)

        if self.expose_headers:
            response["Access-Control-Expose-Headers"] = ", ".join(self.expose_headers)
