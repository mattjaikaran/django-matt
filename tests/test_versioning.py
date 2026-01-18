"""
Tests for the versioning module in Django Matt.
"""

import warnings
from datetime import date
from unittest.mock import MagicMock

from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from django_matt.versioning import (
    AcceptHeaderVersioning,
    BaseVersioning,
    HeaderVersioning,
    HostNameVersioning,
    QueryParameterVersioning,
    URLPathVersioning,
    deprecated,
    max_version,
    min_version,
    version,
)
from django_matt.versioning.base import VersioningError
from django_matt.versioning.decorators import VersionedMixin, version_range
from django_matt.versioning.schemes import NamespaceVersioning

# =============================================================================
# BaseVersioning Tests
# =============================================================================


class ConcreteVersioning(BaseVersioning):
    """Concrete implementation for testing BaseVersioning."""

    def determine_version(self, request, **kwargs):
        return kwargs.get("version", self.default_version)


class TestBaseVersioning(TestCase):
    """Tests for BaseVersioning base class."""

    def test_default_initialization(self):
        """Test default initialization."""
        versioning = ConcreteVersioning()
        self.assertIsNone(versioning.default_version)
        self.assertIsNone(versioning.allowed_versions)

    def test_custom_initialization(self):
        """Test custom initialization."""
        versioning = ConcreteVersioning(
            default_version="1.0",
            allowed_versions=["1.0", "2.0"],
        )
        self.assertEqual(versioning.default_version, "1.0")
        self.assertEqual(versioning.allowed_versions, ["1.0", "2.0"])

    def test_is_allowed_version_all_allowed(self):
        """Test is_allowed_version when all versions allowed."""
        versioning = ConcreteVersioning()
        self.assertTrue(versioning.is_allowed_version("1.0"))
        self.assertTrue(versioning.is_allowed_version("99.0"))

    def test_is_allowed_version_specific_list(self):
        """Test is_allowed_version with specific list."""
        versioning = ConcreteVersioning(allowed_versions=["1.0", "2.0"])
        self.assertTrue(versioning.is_allowed_version("1.0"))
        self.assertTrue(versioning.is_allowed_version("2.0"))
        self.assertFalse(versioning.is_allowed_version("3.0"))

    def test_is_allowed_version_none_with_default(self):
        """Test is_allowed_version with None when default exists."""
        versioning = ConcreteVersioning(default_version="1.0", allowed_versions=["1.0", "2.0"])
        self.assertTrue(versioning.is_allowed_version(None))

    def test_is_allowed_version_none_without_default(self):
        """Test is_allowed_version with None when no default."""
        versioning = ConcreteVersioning(allowed_versions=["1.0", "2.0"])
        self.assertFalse(versioning.is_allowed_version(None))

    def test_validate_version_uses_default(self):
        """Test validate_version uses default when None."""
        versioning = ConcreteVersioning(default_version="1.0", allowed_versions=["1.0", "2.0"])
        result = versioning.validate_version(None)
        self.assertEqual(result, "1.0")

    def test_validate_version_raises_for_invalid(self):
        """Test validate_version raises for invalid version."""
        versioning = ConcreteVersioning(allowed_versions=["1.0", "2.0"])
        with self.assertRaises(VersioningError) as ctx:
            versioning.validate_version("3.0")

        self.assertEqual(ctx.exception.version, "3.0")
        self.assertEqual(ctx.exception.allowed_versions, ["1.0", "2.0"])

    def test_parse_version_simple(self):
        """Test parsing simple version strings."""
        self.assertEqual(BaseVersioning.parse_version("1"), (1,))
        self.assertEqual(BaseVersioning.parse_version("2"), (2,))

    def test_parse_version_with_dots(self):
        """Test parsing version strings with dots."""
        self.assertEqual(BaseVersioning.parse_version("1.0"), (1, 0))
        self.assertEqual(BaseVersioning.parse_version("1.2.3"), (1, 2, 3))

    def test_parse_version_with_v_prefix(self):
        """Test parsing version strings with 'v' prefix."""
        self.assertEqual(BaseVersioning.parse_version("v1"), (1,))
        self.assertEqual(BaseVersioning.parse_version("V2.0"), (2, 0))

    def test_parse_version_with_suffix(self):
        """Test parsing version strings with suffix."""
        self.assertEqual(BaseVersioning.parse_version("1.0-beta"), (1, 0))
        self.assertEqual(BaseVersioning.parse_version("2.0-rc1"), (2, 0))

    def test_compare_versions_equal(self):
        """Test comparing equal versions."""
        self.assertEqual(BaseVersioning.compare_versions("1.0", "1.0"), 0)
        self.assertEqual(BaseVersioning.compare_versions("2", "2.0"), 0)
        self.assertEqual(BaseVersioning.compare_versions("1.0.0", "1"), 0)

    def test_compare_versions_less_than(self):
        """Test comparing versions where first is less."""
        self.assertEqual(BaseVersioning.compare_versions("1.0", "2.0"), -1)
        self.assertEqual(BaseVersioning.compare_versions("1.0", "1.1"), -1)
        self.assertEqual(BaseVersioning.compare_versions("1.9", "2.0"), -1)

    def test_compare_versions_greater_than(self):
        """Test comparing versions where first is greater."""
        self.assertEqual(BaseVersioning.compare_versions("2.0", "1.0"), 1)
        self.assertEqual(BaseVersioning.compare_versions("1.1", "1.0"), 1)
        self.assertEqual(BaseVersioning.compare_versions("2.0", "1.9"), 1)


# =============================================================================
# VersioningError Tests
# =============================================================================


class TestVersioningError(TestCase):
    """Tests for VersioningError exception."""

    def test_default_message(self):
        """Test default error message."""
        error = VersioningError()
        self.assertEqual(str(error), "Invalid API version")

    def test_custom_message(self):
        """Test custom error message."""
        error = VersioningError("Custom error")
        self.assertEqual(str(error), "Custom error")

    def test_version_stored(self):
        """Test version is stored."""
        error = VersioningError(version="3.0")
        self.assertEqual(error.version, "3.0")

    def test_allowed_versions_stored(self):
        """Test allowed versions are stored."""
        error = VersioningError(allowed_versions=["1.0", "2.0"])
        self.assertEqual(error.allowed_versions, ["1.0", "2.0"])


# =============================================================================
# URLPathVersioning Tests
# =============================================================================


class TestURLPathVersioning(TestCase):
    """Tests for URLPathVersioning."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_default_values(self):
        """Test default values."""
        versioning = URLPathVersioning()
        self.assertEqual(versioning.version_param, "version")
        self.assertIsNotNone(versioning.version_regex)

    def test_determine_version_from_kwargs(self):
        """Test extracting version from kwargs."""
        versioning = URLPathVersioning(default_version="1", allowed_versions=["1", "2"])
        request = self.factory.get("/api/v2/users/")

        result = versioning.determine_version(request, version="2")
        self.assertEqual(result, "2")

    def test_determine_version_with_v_prefix(self):
        """Test extracting version with 'v' prefix in kwargs."""
        versioning = URLPathVersioning(default_version="1", allowed_versions=["1", "2"])
        request = self.factory.get("/api/v2/users/")

        result = versioning.determine_version(request, version="v2")
        self.assertEqual(result, "2")

    def test_determine_version_from_path_regex(self):
        """Test extracting version from path using regex."""
        versioning = URLPathVersioning(default_version="1", allowed_versions=["1", "2"])
        request = self.factory.get("/api/v2/users/")

        result = versioning.determine_version(request)
        self.assertEqual(result, "2")

    def test_determine_version_falls_back_to_default(self):
        """Test falling back to default version."""
        versioning = URLPathVersioning(default_version="1", allowed_versions=["1", "2"])
        request = self.factory.get("/api/users/")

        result = versioning.determine_version(request)
        self.assertEqual(result, "1")

    def test_custom_version_param(self):
        """Test custom version parameter name."""
        versioning = URLPathVersioning(
            default_version="1",
            allowed_versions=["1", "2"],
            version_param="api_version",
        )
        request = self.factory.get("/api/v2/users/")

        result = versioning.determine_version(request, api_version="2")
        self.assertEqual(result, "2")


# =============================================================================
# HeaderVersioning Tests
# =============================================================================


class TestHeaderVersioning(TestCase):
    """Tests for HeaderVersioning."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_default_header_name(self):
        """Test default header name."""
        versioning = HeaderVersioning()
        self.assertEqual(versioning.header_name, "X-API-Version")

    def test_determine_version_from_header(self):
        """Test extracting version from header."""
        versioning = HeaderVersioning(default_version="1", allowed_versions=["1", "2"])
        request = self.factory.get("/api/users/")
        request.META["HTTP_X_API_VERSION"] = "2"

        result = versioning.determine_version(request)
        self.assertEqual(result, "2")

    def test_determine_version_with_v_prefix(self):
        """Test extracting version with 'v' prefix."""
        versioning = HeaderVersioning(default_version="1", allowed_versions=["1", "2"])
        request = self.factory.get("/api/users/")
        request.META["HTTP_X_API_VERSION"] = "v2"

        result = versioning.determine_version(request)
        self.assertEqual(result, "2")

    def test_determine_version_falls_back_to_default(self):
        """Test falling back to default when no header."""
        versioning = HeaderVersioning(default_version="1", allowed_versions=["1", "2"])
        request = self.factory.get("/api/users/")

        result = versioning.determine_version(request)
        self.assertEqual(result, "1")

    def test_custom_header_name(self):
        """Test custom header name."""
        versioning = HeaderVersioning(
            default_version="1",
            allowed_versions=["1", "2"],
            header_name="X-Version",
        )
        request = self.factory.get("/api/users/")
        request.META["HTTP_X_VERSION"] = "2"

        result = versioning.determine_version(request)
        self.assertEqual(result, "2")


# =============================================================================
# AcceptHeaderVersioning Tests
# =============================================================================


class TestAcceptHeaderVersioning(TestCase):
    """Tests for AcceptHeaderVersioning."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_determine_version_from_accept_header(self):
        """Test extracting version from Accept header."""
        versioning = AcceptHeaderVersioning(default_version="1", allowed_versions=["1", "2"])
        request = self.factory.get("/api/users/")
        request.META["HTTP_ACCEPT"] = "application/json; version=2"

        result = versioning.determine_version(request)
        self.assertEqual(result, "2")

    def test_determine_version_vendor_media_type(self):
        """Test extracting version from vendor media type."""
        versioning = AcceptHeaderVersioning(default_version="1", allowed_versions=["1", "2"])
        request = self.factory.get("/api/users/")
        request.META["HTTP_ACCEPT"] = "application/vnd.myapi.v2+json"

        result = versioning.determine_version(request)
        self.assertEqual(result, "2")

    def test_determine_version_falls_back_to_default(self):
        """Test falling back to default when no version in header."""
        versioning = AcceptHeaderVersioning(default_version="1", allowed_versions=["1", "2"])
        request = self.factory.get("/api/users/")
        request.META["HTTP_ACCEPT"] = "application/json"

        result = versioning.determine_version(request)
        self.assertEqual(result, "1")


# =============================================================================
# QueryParameterVersioning Tests
# =============================================================================


class TestQueryParameterVersioning(TestCase):
    """Tests for QueryParameterVersioning."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_default_query_param(self):
        """Test default query parameter name."""
        versioning = QueryParameterVersioning()
        self.assertEqual(versioning.query_param, "version")

    def test_determine_version_from_query(self):
        """Test extracting version from query parameter."""
        versioning = QueryParameterVersioning(default_version="1", allowed_versions=["1", "2"])
        request = self.factory.get("/api/users/?version=2")

        result = versioning.determine_version(request)
        self.assertEqual(result, "2")

    def test_determine_version_with_v_prefix(self):
        """Test extracting version with 'v' prefix."""
        versioning = QueryParameterVersioning(default_version="1", allowed_versions=["1", "2"])
        request = self.factory.get("/api/users/?version=v2")

        result = versioning.determine_version(request)
        self.assertEqual(result, "2")

    def test_determine_version_falls_back_to_default(self):
        """Test falling back to default when no query param."""
        versioning = QueryParameterVersioning(default_version="1", allowed_versions=["1", "2"])
        request = self.factory.get("/api/users/")

        result = versioning.determine_version(request)
        self.assertEqual(result, "1")

    def test_custom_query_param(self):
        """Test custom query parameter name."""
        versioning = QueryParameterVersioning(
            default_version="1",
            allowed_versions=["1", "2"],
            query_param="v",
        )
        request = self.factory.get("/api/users/?v=2")

        result = versioning.determine_version(request)
        self.assertEqual(result, "2")


# =============================================================================
# HostNameVersioning Tests
# =============================================================================


class TestHostNameVersioning(TestCase):
    """Tests for HostNameVersioning."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    @override_settings(ALLOWED_HOSTS=["*"])
    def test_determine_version_from_hostname(self):
        """Test extracting version from hostname."""
        versioning = HostNameVersioning(default_version="1", allowed_versions=["1", "2"])
        request = self.factory.get("/api/users/", HTTP_HOST="v2.api.example.com")

        result = versioning.determine_version(request)
        self.assertEqual(result, "2")

    @override_settings(ALLOWED_HOSTS=["*"])
    def test_determine_version_falls_back_to_default(self):
        """Test falling back to default when no version in hostname."""
        versioning = HostNameVersioning(default_version="1", allowed_versions=["1", "2"])
        request = self.factory.get("/api/users/", HTTP_HOST="api.example.com")

        result = versioning.determine_version(request)
        self.assertEqual(result, "1")


# =============================================================================
# NamespaceVersioning Tests
# =============================================================================


class TestNamespaceVersioning(TestCase):
    """Tests for NamespaceVersioning."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_determine_version_from_namespace(self):
        """Test extracting version from URL namespace."""
        versioning = NamespaceVersioning(default_version="1", allowed_versions=["1", "2"])
        request = self.factory.get("/api/users/")

        # Mock resolver_match with namespace
        request.resolver_match = MagicMock()
        request.resolver_match.namespace = "v2"

        result = versioning.determine_version(request)
        self.assertEqual(result, "2")

    def test_determine_version_no_resolver_match(self):
        """Test when no resolver_match available."""
        versioning = NamespaceVersioning(default_version="1", allowed_versions=["1", "2"])
        request = self.factory.get("/api/users/")

        result = versioning.determine_version(request)
        self.assertEqual(result, "1")


# =============================================================================
# @version Decorator Tests
# =============================================================================


class TestVersionDecorator(TestCase):
    """Tests for @version decorator."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_allows_supported_version(self):
        """Test decorator allows supported version."""

        @version("1", "2")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")
        request.version = "1"

        response = my_view(request)
        self.assertEqual(response.status_code, 200)

    def test_raises_for_unsupported_version(self):
        """Test decorator raises for unsupported version."""

        @version("1", "2")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")
        request.version = "3"

        with self.assertRaises(VersioningError) as ctx:
            my_view(request)

        self.assertEqual(ctx.exception.version, "3")
        self.assertEqual(list(ctx.exception.allowed_versions), ["1", "2"])

    def test_allows_no_version_when_versions_specified(self):
        """Test decorator allows request with no version."""

        @version("1", "2")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")
        # No version attribute

        response = my_view(request)
        self.assertEqual(response.status_code, 200)

    def test_stores_version_info_for_introspection(self):
        """Test decorator stores version info."""

        @version("1", "2", deprecated_in="2")
        def my_view(request):
            return HttpResponse("OK")

        self.assertEqual(my_view._versions, ("1", "2"))
        self.assertEqual(my_view._deprecated_in, "2")


# =============================================================================
# @deprecated Decorator Tests
# =============================================================================


class TestDeprecatedDecorator(TestCase):
    """Tests for @deprecated decorator."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_issues_warning(self):
        """Test decorator issues deprecation warning."""

        @deprecated(since="1.0")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            my_view(request)

            self.assertEqual(len(w), 1)
            self.assertTrue(issubclass(w[0].category, DeprecationWarning))
            self.assertIn("deprecated", str(w[0].message).lower())

    def test_adds_deprecation_headers(self):
        """Test decorator adds deprecation headers."""

        @deprecated(since="1.0", message="Use /new endpoint")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            response = my_view(request)

            self.assertEqual(response["Deprecation"], "true")
            self.assertIn("Use /new endpoint", response["X-Deprecation-Message"])

    def test_adds_sunset_header_from_date(self):
        """Test decorator adds Sunset header from date object."""

        @deprecated(sunset_date=date(2025, 6, 1))
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            response = my_view(request)

            self.assertIn("Sunset", response)
            self.assertIn("2025", response["Sunset"])

    def test_adds_sunset_header_from_string(self):
        """Test decorator adds Sunset header from string."""

        @deprecated(sunset_date="2025-06-01")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            response = my_view(request)

            self.assertIn("Sunset", response)

    def test_stores_deprecation_info(self):
        """Test decorator stores deprecation info."""

        @deprecated(since="1.0", removed_in="2.0", message="Custom message")
        def my_view(request):
            return HttpResponse("OK")

        self.assertTrue(my_view._deprecated)
        self.assertEqual(my_view._deprecated_since, "1.0")
        self.assertEqual(my_view._deprecated_removed_in, "2.0")
        self.assertEqual(my_view._deprecation_message, "Custom message")


# =============================================================================
# @min_version Decorator Tests
# =============================================================================


class TestMinVersionDecorator(TestCase):
    """Tests for @min_version decorator."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_allows_equal_version(self):
        """Test decorator allows equal version."""

        @min_version("2.0")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")
        request.version = "2.0"

        response = my_view(request)
        self.assertEqual(response.status_code, 200)

    def test_allows_higher_version(self):
        """Test decorator allows higher version."""

        @min_version("2.0")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")
        request.version = "3.0"

        response = my_view(request)
        self.assertEqual(response.status_code, 200)

    def test_raises_for_lower_version(self):
        """Test decorator raises for lower version."""

        @min_version("2.0")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")
        request.version = "1.0"

        with self.assertRaises(VersioningError) as ctx:
            my_view(request)

        self.assertIn("2.0 or higher", str(ctx.exception))

    def test_allows_no_version(self):
        """Test decorator allows request with no version."""

        @min_version("2.0")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")

        response = my_view(request)
        self.assertEqual(response.status_code, 200)


# =============================================================================
# @max_version Decorator Tests
# =============================================================================


class TestMaxVersionDecorator(TestCase):
    """Tests for @max_version decorator."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_allows_equal_version(self):
        """Test decorator allows equal version."""

        @max_version("2.0")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")
        request.version = "2.0"

        response = my_view(request)
        self.assertEqual(response.status_code, 200)

    def test_allows_lower_version(self):
        """Test decorator allows lower version."""

        @max_version("2.0")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")
        request.version = "1.0"

        response = my_view(request)
        self.assertEqual(response.status_code, 200)

    def test_raises_for_higher_version(self):
        """Test decorator raises for higher version."""

        @max_version("2.0")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")
        request.version = "3.0"

        with self.assertRaises(VersioningError) as ctx:
            my_view(request)

        self.assertIn("Maximum supported version is 2.0", str(ctx.exception))


# =============================================================================
# @version_range Decorator Tests
# =============================================================================


class TestVersionRangeDecorator(TestCase):
    """Tests for @version_range decorator."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_allows_version_in_range(self):
        """Test decorator allows version in range."""

        @version_range("1.5", "2.5")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")
        request.version = "2.0"

        response = my_view(request)
        self.assertEqual(response.status_code, 200)

    def test_allows_minimum_version(self):
        """Test decorator allows minimum version."""

        @version_range("1.5", "2.5")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")
        request.version = "1.5"

        response = my_view(request)
        self.assertEqual(response.status_code, 200)

    def test_allows_maximum_version(self):
        """Test decorator allows maximum version."""

        @version_range("1.5", "2.5")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")
        request.version = "2.5"

        response = my_view(request)
        self.assertEqual(response.status_code, 200)

    def test_raises_for_version_below_range(self):
        """Test decorator raises for version below range."""

        @version_range("1.5", "2.5")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")
        request.version = "1.0"

        with self.assertRaises(VersioningError):
            my_view(request)

    def test_raises_for_version_above_range(self):
        """Test decorator raises for version above range."""

        @version_range("1.5", "2.5")
        def my_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/")
        request.version = "3.0"

        with self.assertRaises(VersioningError):
            my_view(request)


# =============================================================================
# VersionedMixin Tests
# =============================================================================


class TestVersionedMixin(TestCase):
    """Tests for VersionedMixin."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_check_version_passes_supported(self):
        """Test check_version passes for supported version."""

        class MyView(VersionedMixin):
            supported_versions = ["1", "2"]

        view = MyView()
        request = self.factory.get("/")
        request.version = "1"

        view.check_version(request)  # Should not raise

    def test_check_version_raises_unsupported(self):
        """Test check_version raises for unsupported version."""

        class MyView(VersionedMixin):
            supported_versions = ["1", "2"]

        view = MyView()
        request = self.factory.get("/")
        request.version = "3"

        with self.assertRaises(VersioningError):
            view.check_version(request)

    def test_check_version_warns_deprecated(self):
        """Test check_version warns for deprecated version."""

        class MyView(VersionedMixin):
            supported_versions = ["1", "2"]
            deprecated_versions = ["1"]

        view = MyView()
        request = self.factory.get("/")
        request.version = "1"

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            view.check_version(request)

            self.assertEqual(len(w), 1)
            self.assertTrue(issubclass(w[0].category, DeprecationWarning))

    def test_check_version_passes_no_version(self):
        """Test check_version passes when no version on request."""

        class MyView(VersionedMixin):
            supported_versions = ["1", "2"]

        view = MyView()
        request = self.factory.get("/")

        view.check_version(request)  # Should not raise
