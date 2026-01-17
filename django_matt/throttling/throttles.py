"""
Concrete throttle implementations for django-matt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django_matt.throttling.base import BaseThrottle

if TYPE_CHECKING:
    from django.http import HttpRequest


class AnonRateThrottle(BaseThrottle):
    """
    Rate limit anonymous (unauthenticated) requests by IP address.

    Authenticated users bypass this throttle.

    Example:
        @throttle(AnonRateThrottle, rate="100/hour")
        def public_endpoint(request):
            return {"message": "Hello"}

    Default rate: 100 requests per hour
    """

    rate = "100/hour"
    scope = "anon"

    def get_cache_key(self, request: HttpRequest) -> str | None:
        """
        Return cache key for anonymous users only.

        Args:
            request: The Django HTTP request

        Returns:
            Cache key based on IP, or None for authenticated users
        """
        # Skip throttling for authenticated users
        if hasattr(request, "user") and request.user.is_authenticated:
            return None

        ident = self.get_ident(request)
        return f"throttle:{self.scope}:{ident}"


class UserRateThrottle(BaseThrottle):
    """
    Rate limit authenticated users by user ID.

    Anonymous users are throttled by IP address.

    Example:
        @throttle(UserRateThrottle, rate="1000/day")
        def user_endpoint(request):
            return {"message": "Hello"}

    Default rate: 1000 requests per day
    """

    rate = "1000/day"
    scope = "user"

    def get_cache_key(self, request: HttpRequest) -> str | None:
        """
        Return cache key based on user ID or IP for anonymous.

        Args:
            request: The Django HTTP request

        Returns:
            Cache key based on user ID or IP address
        """
        if hasattr(request, "user") and request.user.is_authenticated:
            ident = str(request.user.pk)
        else:
            ident = self.get_ident(request)

        return f"throttle:{self.scope}:{ident}"


class ScopedRateThrottle(BaseThrottle):
    """
    Apply different rate limits based on the endpoint scope.

    Useful for applying different limits to different API sections.

    Example:
        # Configure scopes in settings
        THROTTLE_RATES = {
            "uploads": "10/hour",
            "search": "30/minute",
            "default": "1000/day",
        }

        @throttle(ScopedRateThrottle, scope="uploads")
        def upload_file(request):
            return {"message": "Uploaded"}

        @throttle(ScopedRateThrottle, scope="search")
        def search(request):
            return {"results": []}
    """

    scope: str = "default"
    scope_attr = "throttle_scope"

    # Rate lookup from Django settings
    _rate_cache: dict[str, str] = {}

    def __init__(self, rate: str | None = None, scope: str | None = None) -> None:
        """
        Initialize the scoped throttle.

        Args:
            rate: Rate string (overrides scope lookup)
            scope: The scope name for rate lookup
        """
        if scope is not None:
            self.scope = scope

        # If no explicit rate, look up from settings
        if rate is None:
            rate = self.get_rate_from_settings()

        super().__init__(rate=rate)

    def get_rate_from_settings(self) -> str | None:
        """
        Get the rate for this scope from Django settings.

        Looks for THROTTLE_RATES dict in settings.

        Returns:
            Rate string or None
        """
        try:
            from django.conf import settings

            rates = getattr(settings, "THROTTLE_RATES", {})
            return rates.get(self.scope, rates.get("default"))
        except Exception:
            return None

    def get_cache_key(self, request: HttpRequest) -> str | None:
        """
        Return cache key based on scope and user/IP.

        Args:
            request: The Django HTTP request

        Returns:
            Cache key including scope
        """
        if hasattr(request, "user") and request.user.is_authenticated:
            ident = str(request.user.pk)
        else:
            ident = self.get_ident(request)

        return f"throttle:{self.scope}:{ident}"


class BurstRateThrottle(BaseThrottle):
    """
    Allow short bursts of requests while maintaining an overall rate limit.

    Combines a short-term burst limit with a sustained rate limit.

    Example:
        @throttle(BurstRateThrottle, burst_rate="10/second", sustained_rate="100/minute")
        def api_endpoint(request):
            return {"message": "Hello"}
    """

    burst_rate: str = "10/second"
    sustained_rate: str = "100/minute"
    scope = "burst"

    def __init__(
        self,
        rate: str | None = None,
        burst_rate: str | None = None,
        sustained_rate: str | None = None,
    ) -> None:
        """
        Initialize the burst throttle.

        Args:
            rate: Not used, for compatibility
            burst_rate: Short-term burst limit
            sustained_rate: Long-term sustained limit
        """
        if burst_rate is not None:
            self.burst_rate = burst_rate
        if sustained_rate is not None:
            self.sustained_rate = sustained_rate

        # Parse both rates
        self.burst_requests, self.burst_duration = self.parse_rate(self.burst_rate)
        self.sustained_requests, self.sustained_duration = self.parse_rate(self.sustained_rate)

        # Use sustained for base class
        super().__init__(rate=self.sustained_rate)

    def get_cache_key(self, request: HttpRequest) -> str | None:
        """
        Return cache key for burst throttling.

        Args:
            request: The Django HTTP request

        Returns:
            Cache key based on user/IP
        """
        if hasattr(request, "user") and request.user.is_authenticated:
            ident = str(request.user.pk)
        else:
            ident = self.get_ident(request)

        return f"throttle:{self.scope}:{ident}"

    def allow_request(self, request: HttpRequest) -> bool:
        """
        Check both burst and sustained limits.

        Args:
            request: The Django HTTP request

        Returns:
            True if request is allowed by both limits
        """
        import time

        cache_key = self.get_cache_key(request)
        if cache_key is None:
            return True

        now = time.time()
        self.history = self.get_history(cache_key)

        # Check burst limit (short window)
        if self.burst_requests and self.burst_duration:
            burst_cutoff = now - self.burst_duration
            burst_history = [t for t in self.history if t > burst_cutoff]
            if len(burst_history) >= self.burst_requests:
                return False

        # Check sustained limit (long window)
        if self.sustained_requests and self.sustained_duration:
            sustained_cutoff = now - self.sustained_duration
            sustained_history = [t for t in self.history if t > sustained_cutoff]
            if len(sustained_history) >= self.sustained_requests:
                return False

        # Request allowed, update history
        self.history.append(now)
        # Keep history for the longer duration
        max_duration = max(self.burst_duration or 0, self.sustained_duration or 0)
        cutoff = now - max_duration
        self.history = [t for t in self.history if t > cutoff]
        self.set_history(cache_key, self.history)

        return True
