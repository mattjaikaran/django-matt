"""
Tests for the throttling module in Django Matt.
"""

import time
from typing import Any
from unittest.mock import MagicMock

from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from django_matt.throttling import (
    AnonRateThrottle,
    BaseThrottle,
    InMemoryBackend,
    ScopedRateThrottle,
    UserRateThrottle,
    throttle,
)
from django_matt.throttling.backends import (
    DjangoCacheBackend,
    get_default_backend,
    set_default_backend,
)
from django_matt.throttling.decorators import (
    ThrottleError,
    ThrottlesMixin,
    throttle_anon,
    throttle_user,
)
from django_matt.throttling.middleware import (
    PathSpecificThrottleMiddleware,
    ThrottleMiddleware,
    throttle_exception_handler,
)
from django_matt.throttling.throttles import BurstRateThrottle

# =============================================================================
# BaseThrottle Tests
# =============================================================================


class ConcreteThrottle(BaseThrottle):
    """Concrete implementation for testing BaseThrottle."""

    def get_cache_key(self, request):
        return f"test:{self.get_ident(request)}"


class TestBaseThrottle(TestCase):
    """Tests for BaseThrottle base class."""

    def test_parse_rate_per_second(self):
        """Test parsing rate per second."""
        throttle = ConcreteThrottle(rate="10/s")
        self.assertEqual(throttle.num_requests, 10)
        self.assertEqual(throttle.duration, 1)

        throttle = ConcreteThrottle(rate="10/second")
        self.assertEqual(throttle.num_requests, 10)
        self.assertEqual(throttle.duration, 1)

    def test_parse_rate_per_minute(self):
        """Test parsing rate per minute."""
        throttle = ConcreteThrottle(rate="60/m")
        self.assertEqual(throttle.num_requests, 60)
        self.assertEqual(throttle.duration, 60)

        throttle = ConcreteThrottle(rate="60/minute")
        self.assertEqual(throttle.num_requests, 60)
        self.assertEqual(throttle.duration, 60)

    def test_parse_rate_per_hour(self):
        """Test parsing rate per hour."""
        throttle = ConcreteThrottle(rate="100/h")
        self.assertEqual(throttle.num_requests, 100)
        self.assertEqual(throttle.duration, 3600)

        throttle = ConcreteThrottle(rate="100/hour")
        self.assertEqual(throttle.num_requests, 100)
        self.assertEqual(throttle.duration, 3600)

    def test_parse_rate_per_day(self):
        """Test parsing rate per day."""
        throttle = ConcreteThrottle(rate="1000/d")
        self.assertEqual(throttle.num_requests, 1000)
        self.assertEqual(throttle.duration, 86400)

        throttle = ConcreteThrottle(rate="1000/day")
        self.assertEqual(throttle.num_requests, 1000)
        self.assertEqual(throttle.duration, 86400)

    def test_parse_rate_none(self):
        """Test parsing None rate."""
        throttle = ConcreteThrottle(rate=None)
        self.assertIsNone(throttle.num_requests)
        self.assertIsNone(throttle.duration)

    def test_parse_rate_invalid_format(self):
        """Test parsing invalid rate format."""
        with self.assertRaises(ValueError):
            ConcreteThrottle(rate="invalid")

    def test_parse_rate_invalid_number(self):
        """Test parsing invalid number in rate."""
        with self.assertRaises(ValueError):
            ConcreteThrottle(rate="abc/hour")

    def test_parse_rate_invalid_period(self):
        """Test parsing invalid period in rate."""
        with self.assertRaises(ValueError):
            ConcreteThrottle(rate="100/week")

    def test_get_ident_remote_addr(self):
        """Test getting identifier from REMOTE_ADDR."""
        factory = RequestFactory()
        request = factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        throttle = ConcreteThrottle(rate="100/hour")
        self.assertEqual(throttle.get_ident(request), "192.168.1.1")

    def test_get_ident_x_forwarded_for(self):
        """Test getting identifier from X-Forwarded-For."""
        factory = RequestFactory()
        request = factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "10.0.0.1, 10.0.0.2"
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        throttle = ConcreteThrottle(rate="100/hour")
        self.assertEqual(throttle.get_ident(request), "10.0.0.1")

    def test_allow_request_no_rate(self):
        """Test allow_request with no rate limit."""
        factory = RequestFactory()
        request = factory.get("/")

        throttle = ConcreteThrottle(rate=None)
        self.assertTrue(throttle.allow_request(request))

    def test_allow_request_under_limit(self):
        """Test allow_request when under rate limit."""
        factory = RequestFactory()
        request = factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        backend = InMemoryBackend()
        throttle = ConcreteThrottle(rate="10/minute")
        throttle.backend = backend

        # First 10 requests should be allowed
        for _ in range(10):
            self.assertTrue(throttle.allow_request(request))

    def test_allow_request_over_limit(self):
        """Test allow_request when over rate limit."""
        factory = RequestFactory()
        request = factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        backend = InMemoryBackend()
        throttle = ConcreteThrottle(rate="5/minute")
        throttle.backend = backend

        # First 5 requests should be allowed
        for _ in range(5):
            self.assertTrue(throttle.allow_request(request))

        # 6th request should be denied
        self.assertFalse(throttle.allow_request(request))

    def test_wait_returns_time_to_wait(self):
        """Test wait() returns correct wait time."""
        factory = RequestFactory()
        request = factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        backend = InMemoryBackend()
        throttle = ConcreteThrottle(rate="1/minute")
        throttle.backend = backend

        # Make a request
        throttle.allow_request(request)

        # wait() should return approximately 60 seconds
        wait_time = throttle.wait()
        self.assertIsNotNone(wait_time)
        self.assertGreater(wait_time, 50)
        self.assertLessEqual(wait_time, 60)

    def test_get_throttle_headers(self):
        """Test getting rate limit headers."""
        factory = RequestFactory()
        request = factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        backend = InMemoryBackend()
        throttle = ConcreteThrottle(rate="10/minute")
        throttle.backend = backend

        # Make 3 requests
        for _ in range(3):
            throttle.allow_request(request)

        headers = throttle.get_throttle_headers()
        self.assertEqual(headers["X-RateLimit-Limit"], "10")
        self.assertEqual(headers["X-RateLimit-Remaining"], "7")
        self.assertIn("X-RateLimit-Reset", headers)


# =============================================================================
# AnonRateThrottle Tests
# =============================================================================


class TestAnonRateThrottle(TestCase):
    """Tests for AnonRateThrottle."""

    def test_default_rate(self):
        """Test default rate is 100/hour."""
        throttle = AnonRateThrottle()
        self.assertEqual(throttle.rate, "100/hour")

    def test_get_cache_key_anonymous(self):
        """Test cache key for anonymous users."""
        factory = RequestFactory()
        request = factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.user = MagicMock()
        request.user.is_authenticated = False

        throttle = AnonRateThrottle()
        key = throttle.get_cache_key(request)

        self.assertIsNotNone(key)
        self.assertIn("anon", key)
        self.assertIn("192.168.1.1", key)

    def test_get_cache_key_authenticated_returns_none(self):
        """Test cache key returns None for authenticated users."""
        factory = RequestFactory()
        request = factory.get("/")
        request.user = MagicMock()
        request.user.is_authenticated = True

        throttle = AnonRateThrottle()
        key = throttle.get_cache_key(request)

        self.assertIsNone(key)

    def test_skip_throttle_for_authenticated(self):
        """Test that authenticated users bypass anon throttle."""
        factory = RequestFactory()
        request = factory.get("/")
        request.user = MagicMock()
        request.user.is_authenticated = True

        backend = InMemoryBackend()
        throttle = AnonRateThrottle(rate="1/minute")
        throttle.backend = backend

        # Should always be allowed for authenticated users
        for _ in range(10):
            self.assertTrue(throttle.allow_request(request))


# =============================================================================
# UserRateThrottle Tests
# =============================================================================


class TestUserRateThrottle(TestCase):
    """Tests for UserRateThrottle."""

    def test_default_rate(self):
        """Test default rate is 1000/day."""
        throttle = UserRateThrottle()
        self.assertEqual(throttle.rate, "1000/day")

    def test_get_cache_key_authenticated(self):
        """Test cache key for authenticated users uses user ID."""
        factory = RequestFactory()
        request = factory.get("/")
        request.user = MagicMock()
        request.user.is_authenticated = True
        request.user.pk = 42

        throttle = UserRateThrottle()
        key = throttle.get_cache_key(request)

        self.assertIsNotNone(key)
        self.assertIn("user", key)
        self.assertIn("42", key)

    def test_get_cache_key_anonymous(self):
        """Test cache key for anonymous users uses IP."""
        factory = RequestFactory()
        request = factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.user = MagicMock()
        request.user.is_authenticated = False

        throttle = UserRateThrottle()
        key = throttle.get_cache_key(request)

        self.assertIsNotNone(key)
        self.assertIn("user", key)
        self.assertIn("192.168.1.1", key)


# =============================================================================
# ScopedRateThrottle Tests
# =============================================================================


class TestScopedRateThrottle(TestCase):
    """Tests for ScopedRateThrottle."""

    def test_default_scope(self):
        """Test default scope is 'default'."""
        throttle = ScopedRateThrottle(rate="100/hour")
        self.assertEqual(throttle.scope, "default")

    def test_custom_scope(self):
        """Test custom scope is used."""
        throttle = ScopedRateThrottle(rate="10/hour", scope="uploads")
        self.assertEqual(throttle.scope, "uploads")

    def test_cache_key_includes_scope(self):
        """Test cache key includes scope."""
        factory = RequestFactory()
        request = factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.user = MagicMock()
        request.user.is_authenticated = False

        throttle = ScopedRateThrottle(rate="10/hour", scope="uploads")
        key = throttle.get_cache_key(request)

        self.assertIn("uploads", key)

    @override_settings(THROTTLE_RATES={"search": "30/minute", "default": "100/hour"})
    def test_rate_from_settings(self):
        """Test rate lookup from Django settings."""
        throttle = ScopedRateThrottle(scope="search")
        self.assertEqual(throttle.num_requests, 30)
        self.assertEqual(throttle.duration, 60)


# =============================================================================
# BurstRateThrottle Tests
# =============================================================================


class TestBurstRateThrottle(TestCase):
    """Tests for BurstRateThrottle."""

    def test_default_rates(self):
        """Test default burst and sustained rates."""
        throttle = BurstRateThrottle()
        self.assertEqual(throttle.burst_rate, "10/second")
        self.assertEqual(throttle.sustained_rate, "100/minute")

    def test_custom_rates(self):
        """Test custom burst and sustained rates."""
        throttle = BurstRateThrottle(burst_rate="5/second", sustained_rate="50/minute")
        self.assertEqual(throttle.burst_requests, 5)
        self.assertEqual(throttle.burst_duration, 1)
        self.assertEqual(throttle.sustained_requests, 50)
        self.assertEqual(throttle.sustained_duration, 60)

    def test_burst_limit_enforced(self):
        """Test burst limit is enforced."""
        factory = RequestFactory()
        request = factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.user = MagicMock()
        request.user.is_authenticated = False

        backend = InMemoryBackend()
        throttle = BurstRateThrottle(burst_rate="3/second", sustained_rate="100/minute")
        throttle.backend = backend

        # First 3 requests should be allowed (burst)
        for _ in range(3):
            self.assertTrue(throttle.allow_request(request))

        # 4th request should be denied (burst limit)
        self.assertFalse(throttle.allow_request(request))


# =============================================================================
# InMemoryBackend Tests
# =============================================================================


class TestInMemoryBackend(TestCase):
    """Tests for InMemoryBackend."""

    def test_set_and_get(self):
        """Test setting and getting values."""
        backend = InMemoryBackend()
        backend.set("test_key", [1.0, 2.0, 3.0])

        result = backend.get("test_key")
        self.assertEqual(result, [1.0, 2.0, 3.0])

    def test_get_nonexistent(self):
        """Test getting nonexistent key."""
        backend = InMemoryBackend()
        result = backend.get("nonexistent")
        self.assertIsNone(result)

    def test_delete(self):
        """Test deleting a key."""
        backend = InMemoryBackend()
        backend.set("test_key", [1.0, 2.0])
        backend.delete("test_key")

        result = backend.get("test_key")
        self.assertIsNone(result)

    def test_delete_nonexistent(self):
        """Test deleting nonexistent key doesn't raise."""
        backend = InMemoryBackend()
        backend.delete("nonexistent")  # Should not raise

    def test_clear(self):
        """Test clearing all keys."""
        backend = InMemoryBackend()
        backend.set("key1", [1.0])
        backend.set("key2", [2.0])
        backend.clear()

        self.assertIsNone(backend.get("key1"))
        self.assertIsNone(backend.get("key2"))

    def test_ttl_expiration(self):
        """Test TTL expiration."""
        backend = InMemoryBackend()
        backend.set("test_key", [1.0], ttl=1)

        # Should exist immediately
        self.assertIsNotNone(backend.get("test_key"))

        # Wait for expiration
        time.sleep(1.1)

        # Should be expired
        self.assertIsNone(backend.get("test_key"))

    def test_cleanup_expired(self):
        """Test cleanup_expired removes expired entries."""
        backend = InMemoryBackend()
        backend.set("expired", [1.0], ttl=1)
        backend.set("not_expired", [2.0], ttl=3600)

        time.sleep(1.1)
        removed = backend.cleanup_expired()

        self.assertEqual(removed, 1)
        self.assertIsNone(backend.get("expired"))
        self.assertIsNotNone(backend.get("not_expired"))


# =============================================================================
# DjangoCacheBackend Tests
# =============================================================================


class TestDjangoCacheBackend(TestCase):
    """Tests for DjangoCacheBackend."""

    def test_set_and_get(self):
        """Test setting and getting values through Django cache."""
        backend = DjangoCacheBackend()
        backend.set("test_key", [1.0, 2.0, 3.0])

        result = backend.get("test_key")
        self.assertEqual(result, [1.0, 2.0, 3.0])

    def test_get_nonexistent(self):
        """Test getting nonexistent key."""
        backend = DjangoCacheBackend()
        result = backend.get("nonexistent_unique_key_12345")
        self.assertIsNone(result)

    def test_delete(self):
        """Test deleting a key."""
        backend = DjangoCacheBackend()
        backend.set("test_key_delete", [1.0, 2.0])
        backend.delete("test_key_delete")

        result = backend.get("test_key_delete")
        self.assertIsNone(result)

    def test_custom_prefix(self):
        """Test custom key prefix."""
        backend = DjangoCacheBackend(prefix="custom:")
        self.assertEqual(backend.prefix, "custom:")
        self.assertEqual(backend._make_key("test"), "custom:test")


# =============================================================================
# Throttle Decorator Tests
# =============================================================================


class TestThrottleDecorator(TestCase):
    """Tests for @throttle decorator."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        # Reset default backend
        set_default_backend(InMemoryBackend())

    def test_throttle_allows_request_under_limit(self):
        """Test throttle allows requests under limit."""

        @throttle(rate="10/minute")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.user = MagicMock()
        request.user.is_authenticated = False

        response = my_view(request)
        self.assertEqual(response.status_code, 200)

    def test_throttle_raises_error_over_limit(self):
        """Test throttle raises ThrottleError over limit."""
        backend = InMemoryBackend()
        set_default_backend(backend)

        @throttle(rate="2/minute")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.101"
        request.user = MagicMock()
        request.user.is_authenticated = False

        # First 2 requests should work
        my_view(request)
        my_view(request)

        # 3rd request should raise
        with self.assertRaises(ThrottleError) as ctx:
            my_view(request)

        self.assertIn("throttled", str(ctx.exception))

    def test_throttle_with_specific_class(self):
        """Test throttle with specific throttle class."""

        @throttle(UserRateThrottle, rate="100/hour")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.102"
        request.user = MagicMock()
        request.user.is_authenticated = True
        request.user.pk = 1

        response = my_view(request)
        self.assertEqual(response.status_code, 200)

    def test_throttle_adds_headers(self):
        """Test throttle adds rate limit headers."""

        @throttle(rate="10/minute")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.103"
        request.user = MagicMock()
        request.user.is_authenticated = False

        response = my_view(request)
        self.assertIn("X-RateLimit-Limit", response)
        self.assertIn("X-RateLimit-Remaining", response)

    def test_throttle_respects_methods(self):
        """Test throttle only applies to specified methods."""
        backend = InMemoryBackend()
        set_default_backend(backend)

        @throttle(rate="1/minute", methods=["POST"])
        def my_view(request):
            return HttpResponse("OK")

        # GET requests should not be throttled
        get_request = self.factory.get("/")
        get_request.META["REMOTE_ADDR"] = "192.168.1.104"
        get_request.user = MagicMock()
        get_request.user.is_authenticated = False

        for _ in range(5):
            response = my_view(get_request)
            self.assertEqual(response.status_code, 200)


class TestThrottleShortcuts(TestCase):
    """Tests for throttle_anon and throttle_user shortcuts."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        set_default_backend(InMemoryBackend())

    def test_throttle_anon(self):
        """Test throttle_anon shortcut."""

        @throttle_anon("50/hour")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.105"
        request.user = MagicMock()
        request.user.is_authenticated = False

        response = my_view(request)
        self.assertEqual(response.status_code, 200)

    def test_throttle_user(self):
        """Test throttle_user shortcut."""

        @throttle_user("500/hour")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")
        request.user = MagicMock()
        request.user.is_authenticated = True
        request.user.pk = 99

        response = my_view(request)
        self.assertEqual(response.status_code, 200)


# =============================================================================
# ThrottlesMixin Tests
# =============================================================================


class TestThrottlesMixin(TestCase):
    """Tests for ThrottlesMixin."""

    def test_get_throttles(self):
        """Test get_throttles returns configured throttles."""

        class MyView(ThrottlesMixin):
            throttle_classes = [AnonRateThrottle, UserRateThrottle]

        view = MyView()
        throttles = view.get_throttles()

        self.assertEqual(len(throttles), 2)
        self.assertIsInstance(throttles[0], AnonRateThrottle)
        self.assertIsInstance(throttles[1], UserRateThrottle)

    def test_get_throttles_with_rates(self):
        """Test get_throttles uses configured rates."""

        class MyView(ThrottlesMixin):
            throttle_classes = [AnonRateThrottle]
            throttle_rates = {"AnonRateThrottle": "50/hour"}

        view = MyView()
        throttles = view.get_throttles()

        self.assertEqual(throttles[0].num_requests, 50)
        self.assertEqual(throttles[0].duration, 3600)

    def test_check_throttles_passes(self):
        """Test check_throttles passes when under limit."""
        factory = RequestFactory()
        request = factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.106"
        request.user = MagicMock()
        request.user.is_authenticated = False

        class MyView(ThrottlesMixin):
            throttle_classes = [AnonRateThrottle]

        view = MyView()
        view.check_throttles(request)  # Should not raise

    def test_check_throttles_raises(self):
        """Test check_throttles raises when over limit."""
        factory = RequestFactory()
        request = factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.107"
        request.user = MagicMock()
        request.user.is_authenticated = False

        backend = InMemoryBackend()
        set_default_backend(backend)

        class MyView(ThrottlesMixin):
            throttle_classes = [AnonRateThrottle]
            throttle_rates = {"AnonRateThrottle": "1/minute"}

        view = MyView()
        view.check_throttles(request)  # First request OK

        with self.assertRaises(ThrottleError):
            view.check_throttles(request)  # Second should fail


# =============================================================================
# ThrottleError Tests
# =============================================================================


class TestThrottleError(TestCase):
    """Tests for ThrottleError exception."""

    def test_default_message(self):
        """Test default error message."""
        error = ThrottleError()
        self.assertEqual(str(error), "Request was throttled")

    def test_custom_message(self):
        """Test custom error message."""
        error = ThrottleError("Too many requests")
        self.assertEqual(str(error), "Too many requests")

    def test_wait_time(self):
        """Test wait time is stored."""
        error = ThrottleError(wait=30.5)
        self.assertEqual(error.wait, 30.5)

    def test_headers(self):
        """Test headers are stored."""
        headers = {"Retry-After": "60", "X-RateLimit-Limit": "100"}
        error = ThrottleError(headers=headers)
        self.assertEqual(error.headers, headers)


# =============================================================================
# get_default_backend Tests
# =============================================================================


class TestGetDefaultBackend(TestCase):
    """Tests for get_default_backend function."""

    def tearDown(self):
        """Reset default backend after each test."""
        from django_matt.throttling import backends

        backends._default_backend = None

    def test_returns_in_memory_by_default(self):
        """Test returns InMemoryBackend when no settings configured."""
        from django_matt.throttling import backends

        backends._default_backend = None

        backend = get_default_backend()
        self.assertIsInstance(backend, InMemoryBackend)

    def test_set_default_backend(self):
        """Test set_default_backend sets the backend."""
        custom_backend = InMemoryBackend()
        set_default_backend(custom_backend)

        result = get_default_backend()
        self.assertIs(result, custom_backend)

    @override_settings(THROTTLE_BACKEND="memory")
    def test_memory_backend_from_settings(self):
        """Test memory backend from settings string."""
        from django_matt.throttling import backends

        backends._default_backend = None

        backend = get_default_backend()
        self.assertIsInstance(backend, InMemoryBackend)

    @override_settings(THROTTLE_BACKEND="cache")
    def test_cache_backend_from_settings(self):
        """Test Django cache backend from settings string."""
        from django_matt.throttling import backends

        backends._default_backend = None

        backend = get_default_backend()
        self.assertIsInstance(backend, DjangoCacheBackend)

    @override_settings(THROTTLE_BACKEND={"type": "cache", "prefix": "custom:"})
    def test_cache_backend_from_settings_dict(self):
        """Test Django cache backend from settings dict."""
        from django_matt.throttling import backends

        backends._default_backend = None

        backend = get_default_backend()
        self.assertIsInstance(backend, DjangoCacheBackend)
        self.assertEqual(backend.prefix, "custom:")


# =============================================================================
# Retry-After Header Tests (RFC 6585)
# =============================================================================


class TestRetryAfterHeader(TestCase):
    """Tests for Retry-After header on 429 responses."""

    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.backend = InMemoryBackend()
        set_default_backend(self.backend)

    def _make_anon_request(self, ip: str = "10.0.0.1") -> Any:
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = ip
        request.user = MagicMock()
        request.user.is_authenticated = False
        return request

    # -- ThrottleMiddleware ---------------------------------------------------

    def test_throttle_middleware_429_includes_retry_after(self) -> None:
        """429 response from ThrottleMiddleware includes Retry-After header."""

        def dummy_view(request: Any) -> HttpResponse:
            return HttpResponse("OK")

        middleware = ThrottleMiddleware(dummy_view)
        middleware.backend = self.backend
        middleware._config = {"anon_rate": "1/minute"}

        request = self._make_anon_request()

        # First request allowed
        resp = middleware(request)
        self.assertEqual(resp.status_code, 200)

        # Second request throttled
        resp = middleware(request)
        self.assertEqual(resp.status_code, 429)
        self.assertIn("Retry-After", resp)
        retry_after = int(resp["Retry-After"])
        self.assertGreater(retry_after, 0)

    def test_throttle_middleware_allowed_no_retry_after(self) -> None:
        """Allowed response from ThrottleMiddleware has no Retry-After header."""

        def dummy_view(request: Any) -> HttpResponse:
            return HttpResponse("OK")

        middleware = ThrottleMiddleware(dummy_view)
        middleware.backend = self.backend
        middleware._config = {"anon_rate": "100/minute"}

        request = self._make_anon_request()
        resp = middleware(request)

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("Retry-After", resp)

    # -- PathSpecificThrottleMiddleware ---------------------------------------

    @override_settings(THROTTLE_PATH_RATES={"/api/": "1/minute"})
    def test_path_middleware_429_includes_retry_after(self) -> None:
        """429 response from PathSpecificThrottleMiddleware includes Retry-After."""

        def dummy_view(request: Any) -> HttpResponse:
            return HttpResponse("OK")

        middleware = PathSpecificThrottleMiddleware(dummy_view)
        middleware.backend = self.backend
        middleware._path_rates = {"/api/": "1/minute"}

        request = self._make_anon_request()
        request.path = "/api/test/"

        # First request allowed
        resp = middleware(request)
        self.assertEqual(resp.status_code, 200)

        # Second request throttled
        resp = middleware(request)
        self.assertEqual(resp.status_code, 429)
        self.assertIn("Retry-After", resp)
        retry_after = int(resp["Retry-After"])
        self.assertGreater(retry_after, 0)

    # -- throttle_exception_handler -------------------------------------------

    def test_exception_handler_429_includes_retry_after(self) -> None:
        """throttle_exception_handler sets Retry-After from ThrottleError."""
        exc = ThrottleError(
            message="Throttled",
            wait=45.0,
            headers={"X-RateLimit-Limit": "10"},
        )
        resp = throttle_exception_handler(exc)
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 429)
        self.assertIn("Retry-After", resp)
        self.assertEqual(resp["Retry-After"], "46")  # int(45) + 1

    def test_exception_handler_no_wait_no_retry_after(self) -> None:
        """throttle_exception_handler omits Retry-After when wait is None."""
        exc = ThrottleError(message="Throttled", wait=None, headers={})
        resp = throttle_exception_handler(exc)
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 429)
        self.assertNotIn("Retry-After", resp)

    # -- @throttle decorator --------------------------------------------------

    def test_decorator_throttle_error_has_retry_after_in_headers(self) -> None:
        """ThrottleError raised by @throttle decorator includes Retry-After."""

        @throttle(rate="1/minute")
        def my_view(request: Any) -> HttpResponse:
            return HttpResponse("OK")

        request = self._make_anon_request(ip="10.0.0.50")

        # First request OK
        my_view(request)

        # Second request raises
        with self.assertRaises(ThrottleError) as ctx:
            my_view(request)

        exc = ctx.exception
        self.assertIn("Retry-After", exc.headers)
        retry_after = int(exc.headers["Retry-After"])
        self.assertGreater(retry_after, 0)

    # -- BaseThrottle.get_throttle_headers() ----------------------------------

    def test_get_throttle_headers_retry_after_positive_int_string(self) -> None:
        """Retry-After in get_throttle_headers() is a positive int as string."""
        request = self._make_anon_request(ip="10.0.0.60")

        t = ConcreteThrottle(rate="1/minute")
        t.backend = self.backend

        t.allow_request(request)  # allowed
        t.allow_request(request)  # denied

        headers = t.get_throttle_headers()
        self.assertIn("Retry-After", headers)

        # Must be parseable as a positive integer
        val = int(headers["Retry-After"])
        self.assertGreater(val, 0)

    def test_get_throttle_headers_no_retry_after_when_allowed(self) -> None:
        """No Retry-After in headers when request is allowed."""
        request = self._make_anon_request(ip="10.0.0.70")

        t = ConcreteThrottle(rate="100/minute")
        t.backend = self.backend

        t.allow_request(request)

        headers = t.get_throttle_headers()
        self.assertNotIn("Retry-After", headers)
