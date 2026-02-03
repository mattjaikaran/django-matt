"""
Analytics middleware.

Provides auto-tracking of sessions, page views, and request timing.

Usage:
    # In settings.py
    MIDDLEWARE = [
        ...
        'django_matt.analytics.AnalyticsMiddleware',
        ...
    ]

    # Configuration (optional)
    DJANGO_MATT_ANALYTICS = {
        "MIDDLEWARE": {
            "track_sessions": True,
            "track_page_views": True,
            "track_timing": True,
            "session_cookie_name": "_matt_session",
            "session_timeout_minutes": 30,
            "exclude_paths": ["/health", "/metrics", "/static"],
            "exclude_bots": True,
            "anonymize_ip": False,
            "respect_dnt": True,
        },
    }
"""

import hashlib
import logging
import re
import time
import uuid
from typing import Callable
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from .models import AnalyticsSession, SessionStatus

logger = logging.getLogger("django_matt.analytics")

# Common bot patterns
BOT_PATTERNS = [
    r"bot",
    r"crawler",
    r"spider",
    r"scraper",
    r"curl",
    r"wget",
    r"python-requests",
    r"go-http-client",
    r"httpie",
    r"postman",
    r"insomnia",
    r"googlebot",
    r"bingbot",
    r"slurp",
    r"duckduckbot",
    r"baiduspider",
    r"yandexbot",
    r"facebookexternalhit",
    r"twitterbot",
    r"linkedinbot",
    r"whatsapp",
    r"telegram",
    r"discord",
    r"slack",
]


class AnalyticsMiddleware:
    """
    Middleware for automatic analytics tracking.

    Features:
    - Session tracking with cookie-based identification
    - Automatic page view tracking
    - Request timing measurement
    - Bot filtering
    - DNT (Do Not Track) header support
    - IP anonymization
    - UTM parameter extraction
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

        # Load configuration
        config = getattr(settings, "DJANGO_MATT_ANALYTICS", {})
        middleware_config = config.get("MIDDLEWARE", {})

        self.track_sessions = middleware_config.get("track_sessions", True)
        self.track_page_views = middleware_config.get("track_page_views", True)
        self.track_timing = middleware_config.get("track_timing", True)
        self.session_cookie_name = middleware_config.get("session_cookie_name", "_matt_session")
        self.anonymous_cookie_name = middleware_config.get("anonymous_cookie_name", "_matt_anon")
        self.session_timeout_minutes = middleware_config.get("session_timeout_minutes", 30)
        self.exclude_paths = middleware_config.get("exclude_paths", [
            "/health",
            "/healthz",
            "/ready",
            "/metrics",
            "/static",
            "/media",
            "/favicon.ico",
            "/robots.txt",
            "/sitemap.xml",
        ])
        self.exclude_extensions = middleware_config.get("exclude_extensions", [
            ".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg",
            ".ico", ".woff", ".woff2", ".ttf", ".eot", ".map",
        ])
        self.exclude_bots = middleware_config.get("exclude_bots", True)
        self.anonymize_ip = middleware_config.get("anonymize_ip", False)
        self.respect_dnt = middleware_config.get("respect_dnt", True)
        self.cookie_domain = middleware_config.get("cookie_domain", None)
        self.cookie_secure = middleware_config.get("cookie_secure", True)
        self.cookie_samesite = middleware_config.get("cookie_samesite", "Lax")
        self.cookie_max_age = middleware_config.get("cookie_max_age", 365 * 24 * 60 * 60)  # 1 year

        # Compile bot patterns
        self._bot_pattern = re.compile("|".join(BOT_PATTERNS), re.IGNORECASE)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Check if tracking should be skipped
        if self._should_skip(request):
            return self.get_response(request)

        # Start timing
        start_time = time.time()

        # Initialize tracking context
        session = None
        anonymous_id = None

        if self.track_sessions:
            session, anonymous_id = self._get_or_create_session(request)
            request.analytics_session = session  # type: ignore
            request.analytics_anonymous_id = anonymous_id  # type: ignore

        # Process request
        response = self.get_response(request)

        # Track page view for successful HTML responses
        if self.track_page_views and self._should_track_page_view(request, response):
            self._track_page_view(request, session, anonymous_id)

        # Add timing header
        if self.track_timing:
            elapsed = (time.time() - start_time) * 1000
            response["X-Analytics-Time"] = f"{elapsed:.2f}ms"

        # Set cookies
        if self.track_sessions and session:
            response = self._set_cookies(response, session, anonymous_id)

        return response

    def _should_skip(self, request: HttpRequest) -> bool:
        """Check if request should skip tracking."""
        path = request.path

        # Check excluded paths
        for excluded in self.exclude_paths:
            if path.startswith(excluded):
                return True

        # Check excluded extensions
        for ext in self.exclude_extensions:
            if path.endswith(ext):
                return True

        # Check DNT header
        if self.respect_dnt and request.META.get("HTTP_DNT") == "1":
            return True

        # Check for bots
        if self.exclude_bots:
            user_agent = request.META.get("HTTP_USER_AGENT", "")
            if self._bot_pattern.search(user_agent):
                return True

        return False

    def _get_or_create_session(
        self,
        request: HttpRequest,
    ) -> tuple[AnalyticsSession | None, str]:
        """Get existing session or create new one."""
        # Get session ID from cookie
        session_id = request.COOKIES.get(self.session_cookie_name)
        anonymous_id = request.COOKIES.get(self.anonymous_cookie_name) or str(uuid.uuid4())

        session = None

        if session_id:
            try:
                session = AnalyticsSession.objects.get(
                    session_id=session_id,
                    status=SessionStatus.ACTIVE.value,
                )
                # Check if session has expired
                timeout = timezone.now() - timezone.timedelta(minutes=self.session_timeout_minutes)
                if session.last_activity_at < timeout:
                    session.status = SessionStatus.EXPIRED.value
                    session.ended_at = session.last_activity_at
                    session.save(update_fields=["status", "ended_at"])
                    session = None
                else:
                    # Update activity
                    session.last_activity_at = timezone.now()
                    session.events_count += 1
                    session.save(update_fields=["last_activity_at", "events_count"])
            except AnalyticsSession.DoesNotExist:
                session = None

        if session is None:
            # Create new session
            session = self._create_session(request, anonymous_id)

        # Link to user if authenticated
        if request.user.is_authenticated and session.user is None:
            session.user = request.user
            session.save(update_fields=["user"])

        return session, anonymous_id

    def _create_session(
        self,
        request: HttpRequest,
        anonymous_id: str,
    ) -> AnalyticsSession:
        """Create a new analytics session."""
        session_id = str(uuid.uuid4())
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        # Parse device info from user agent
        device_info = self._parse_user_agent(user_agent)

        # Get client IP
        ip_address = self._get_client_ip(request)
        ip_hash = ""

        if self.anonymize_ip and ip_address:
            ip_hash = hashlib.sha256(ip_address.encode()).hexdigest()[:32]
            ip_address = None

        # Extract UTM parameters
        utm_source = request.GET.get("utm_source", "")
        utm_medium = request.GET.get("utm_medium", "")
        utm_campaign = request.GET.get("utm_campaign", "")
        utm_term = request.GET.get("utm_term", "")
        utm_content = request.GET.get("utm_content", "")

        # Get referrer
        referrer = request.META.get("HTTP_REFERER")
        referrer_domain = ""
        if referrer:
            try:
                parsed = urlparse(referrer)
                referrer_domain = parsed.netloc
            except Exception:
                pass

        # Check DNT header
        do_not_track = request.META.get("HTTP_DNT") == "1"

        session = AnalyticsSession.objects.create(
            session_id=session_id,
            user=request.user if request.user.is_authenticated else None,
            anonymous_id=anonymous_id,
            ip_address=ip_address,
            ip_hash=ip_hash,
            user_agent=user_agent,
            device_type=device_info.get("device_type", ""),
            browser=device_info.get("browser", ""),
            os=device_info.get("os", ""),
            referrer=referrer,
            referrer_domain=referrer_domain,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            utm_term=utm_term,
            utm_content=utm_content,
            landing_page=request.path,
            do_not_track=do_not_track,
        )

        logger.debug(f"Created new session: {session_id}")
        return session

    def _should_track_page_view(
        self,
        request: HttpRequest,
        response: HttpResponse,
    ) -> bool:
        """Check if this request should have a page view tracked."""
        # Only track GET requests
        if request.method != "GET":
            return False

        # Only track successful responses
        if response.status_code >= 400:
            return False

        # Only track HTML content
        content_type = response.get("Content-Type", "")
        if "text/html" not in content_type and "application/json" not in content_type:
            return False

        return True

    def _track_page_view(
        self,
        request: HttpRequest,
        session: AnalyticsSession | None,
        anonymous_id: str,
    ):
        """Track a page view."""
        from .models import PageView

        referrer = request.META.get("HTTP_REFERER")
        referrer_domain = ""
        if referrer:
            try:
                parsed = urlparse(referrer)
                referrer_domain = parsed.netloc
            except Exception:
                pass

        # Check if this is the landing page (first page in session)
        is_entrance = session and session.page_views == 0

        PageView.objects.create(
            path=request.path,
            url=request.build_absolute_uri(),
            title="",  # Would need JS to capture
            query_string=request.META.get("QUERY_STRING", ""),
            session=session,
            user=request.user if request.user.is_authenticated else None,
            anonymous_id=anonymous_id,
            referrer=referrer,
            referrer_domain=referrer_domain,
            is_entrance=is_entrance,
        )

        # Update session page view count
        if session:
            session.page_views += 1
            session.exit_page = request.path
            if is_entrance:
                session.landing_page = request.path
            session.save(update_fields=["page_views", "exit_page", "landing_page"])

    def _set_cookies(
        self,
        response: HttpResponse,
        session: AnalyticsSession,
        anonymous_id: str,
    ) -> HttpResponse:
        """Set analytics cookies on response."""
        # Session cookie
        response.set_cookie(
            self.session_cookie_name,
            session.session_id,
            max_age=self.session_timeout_minutes * 60,
            domain=self.cookie_domain,
            secure=self.cookie_secure,
            httponly=True,
            samesite=self.cookie_samesite,
        )

        # Anonymous ID cookie (long-lived)
        response.set_cookie(
            self.anonymous_cookie_name,
            anonymous_id,
            max_age=self.cookie_max_age,
            domain=self.cookie_domain,
            secure=self.cookie_secure,
            httponly=True,
            samesite=self.cookie_samesite,
        )

        return response

    def _get_client_ip(self, request: HttpRequest) -> str | None:
        """Get client IP address from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

    def _parse_user_agent(self, user_agent: str) -> dict:
        """Parse user agent string for device info."""
        ua_lower = user_agent.lower()

        # Device type
        if "mobile" in ua_lower or "android" in ua_lower and "mobile" in ua_lower:
            device_type = "mobile"
        elif "tablet" in ua_lower or "ipad" in ua_lower:
            device_type = "tablet"
        else:
            device_type = "desktop"

        # Browser detection
        browser = "unknown"
        if "chrome" in ua_lower and "edge" not in ua_lower and "opr" not in ua_lower:
            browser = "chrome"
        elif "firefox" in ua_lower:
            browser = "firefox"
        elif "safari" in ua_lower and "chrome" not in ua_lower:
            browser = "safari"
        elif "edge" in ua_lower or "edg" in ua_lower:
            browser = "edge"
        elif "opr" in ua_lower or "opera" in ua_lower:
            browser = "opera"
        elif "msie" in ua_lower or "trident" in ua_lower:
            browser = "ie"

        # OS detection
        os = "unknown"
        if "windows" in ua_lower:
            os = "windows"
        elif "macintosh" in ua_lower or "mac os" in ua_lower:
            os = "macos"
        elif "linux" in ua_lower and "android" not in ua_lower:
            os = "linux"
        elif "android" in ua_lower:
            os = "android"
        elif "iphone" in ua_lower or "ipad" in ua_lower:
            os = "ios"

        return {
            "device_type": device_type,
            "browser": browser,
            "os": os,
        }


class AsyncAnalyticsMiddleware:
    """
    Async version of AnalyticsMiddleware.

    Use this with ASGI applications.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self._sync_middleware = AnalyticsMiddleware(lambda r: None)

    async def __call__(self, request: HttpRequest) -> HttpResponse:
        # Check if tracking should be skipped
        if self._sync_middleware._should_skip(request):
            return await self.get_response(request)

        # Start timing
        start_time = time.time()

        # Initialize tracking context
        session = None
        anonymous_id = None

        if self._sync_middleware.track_sessions:
            session, anonymous_id = await self._get_or_create_session_async(request)
            request.analytics_session = session  # type: ignore
            request.analytics_anonymous_id = anonymous_id  # type: ignore

        # Process request
        response = await self.get_response(request)

        # Track page view for successful HTML responses
        if self._sync_middleware.track_page_views and self._sync_middleware._should_track_page_view(request, response):
            await self._track_page_view_async(request, session, anonymous_id)

        # Add timing header
        if self._sync_middleware.track_timing:
            elapsed = (time.time() - start_time) * 1000
            response["X-Analytics-Time"] = f"{elapsed:.2f}ms"

        # Set cookies
        if self._sync_middleware.track_sessions and session:
            response = self._sync_middleware._set_cookies(response, session, anonymous_id)

        return response

    async def _get_or_create_session_async(
        self,
        request: HttpRequest,
    ) -> tuple[AnalyticsSession | None, str]:
        """Async version of get_or_create_session."""
        import asyncio
        return await asyncio.to_thread(
            self._sync_middleware._get_or_create_session,
            request,
        )

    async def _track_page_view_async(
        self,
        request: HttpRequest,
        session: AnalyticsSession | None,
        anonymous_id: str,
    ):
        """Async version of track_page_view."""
        import asyncio
        return await asyncio.to_thread(
            self._sync_middleware._track_page_view,
            request,
            session,
            anonymous_id,
        )


__all__ = [
    "AnalyticsMiddleware",
    "AsyncAnalyticsMiddleware",
]
