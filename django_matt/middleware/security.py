"""Security headers middleware — CSP, HSTS, X-Frame-Options, etc."""

from django.conf import settings


class SecurityHeadersMiddleware:
    """
    Adds security headers to every response.

    Configured via settings.DJANGO_MATT["SECURITY_HEADERS"]. Defaults are
    production-safe. All config is cached at __init__ time.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        matt_config = getattr(settings, "DJANGO_MATT", {})
        sec = matt_config.get("SECURITY_HEADERS", {})

        self.csp = sec.get(
            "CONTENT_SECURITY_POLICY",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'",
        )
        self.hsts_max_age = sec.get("HSTS_MAX_AGE", 31536000)
        self.hsts_include_subdomains = sec.get("HSTS_INCLUDE_SUBDOMAINS", True)
        self.hsts_preload = sec.get("HSTS_PRELOAD", False)
        self.x_frame_options = sec.get("X_FRAME_OPTIONS", "DENY")
        self.x_content_type_options = sec.get("X_CONTENT_TYPE_OPTIONS", "nosniff")
        self.referrer_policy = sec.get("REFERRER_POLICY", "strict-origin-when-cross-origin")
        self.permissions_policy = sec.get("PERMISSIONS_POLICY", "geolocation=(), camera=(), microphone=()")
        self.enabled = sec.get("ENABLED", True)

    def __call__(self, request):
        response = self.get_response(request)
        if not self.enabled:
            return response
        return self._add_headers(response)

    def _add_headers(self, response):
        if self.csp:
            response["Content-Security-Policy"] = self.csp
        if self.hsts_max_age:
            value = f"max-age={self.hsts_max_age}"
            if self.hsts_include_subdomains:
                value += "; includeSubDomains"
            if self.hsts_preload:
                value += "; preload"
            response["Strict-Transport-Security"] = value
        if self.x_frame_options:
            response["X-Frame-Options"] = self.x_frame_options
        if self.x_content_type_options:
            response["X-Content-Type-Options"] = self.x_content_type_options
        if self.referrer_policy:
            response["Referrer-Policy"] = self.referrer_policy
        if self.permissions_policy:
            response["Permissions-Policy"] = self.permissions_policy
        return response
