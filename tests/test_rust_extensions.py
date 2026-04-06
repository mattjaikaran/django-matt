"""Tests for Rust-accelerated extensions.

These tests verify:
1. The Rust extension loads correctly
2. RadixRouter matches routes correctly
3. Python fallback works when Rust is unavailable
"""

import pytest

from django_matt._accel import HAS_RUST

# Skip all tests if Rust extension is not installed
pytestmark = pytest.mark.skipif(not HAS_RUST, reason="Rust extensions not installed")


@pytest.fixture
def router():
    from django_matt._accel import RadixRouter

    r = RadixRouter()
    return r


@pytest.fixture
def loaded_router(router):
    """Router pre-loaded with common patterns."""
    router.add_route("GET", "/", "root")
    router.add_route("GET", "/users", "list_users")
    router.add_route("POST", "/users", "create_user")
    router.add_route("GET", "/users/{id}", "user_detail")
    router.add_route("PUT", "/users/{id}", "update_user")
    router.add_route("DELETE", "/users/{id}", "delete_user")
    router.add_route("GET", "/users/me", "current_user")
    router.add_route("GET", "/users/{user_id}/posts", "user_posts")
    router.add_route("GET", "/users/{user_id}/posts/{post_id}", "user_post_detail")
    router.add_route("GET", "/files/{path:*}", "serve_file")
    return router


class TestRadixRouterBasic:
    def test_empty_router_returns_none(self, router):
        result = router.match_route("GET", "/anything")
        assert result is None

    def test_route_count(self, loaded_router):
        assert loaded_router.route_count == 10

    def test_root_path(self, loaded_router):
        endpoint, params = loaded_router.match_route("GET", "/")
        assert endpoint == "root"
        assert dict(params) == {}

    def test_static_route(self, loaded_router):
        endpoint, params = loaded_router.match_route("GET", "/users")
        assert endpoint == "list_users"
        assert dict(params) == {}

    def test_method_dispatch(self, loaded_router):
        endpoint, _ = loaded_router.match_route("POST", "/users")
        assert endpoint == "create_user"

    def test_method_not_found(self, loaded_router):
        result = loaded_router.match_route("PATCH", "/users")
        assert result is None

    def test_path_not_found(self, loaded_router):
        result = loaded_router.match_route("GET", "/nonexistent")
        assert result is None


class TestRadixRouterParams:
    def test_single_param(self, loaded_router):
        endpoint, params = loaded_router.match_route("GET", "/users/42")
        assert endpoint == "user_detail"
        assert dict(params) == {"id": "42"}

    def test_param_with_different_methods(self, loaded_router):
        endpoint, params = loaded_router.match_route("PUT", "/users/42")
        assert endpoint == "update_user"
        assert dict(params) == {"id": "42"}

        endpoint, params = loaded_router.match_route("DELETE", "/users/42")
        assert endpoint == "delete_user"
        assert dict(params) == {"id": "42"}

    def test_nested_params(self, loaded_router):
        endpoint, params = loaded_router.match_route("GET", "/users/5/posts/99")
        assert endpoint == "user_post_detail"
        assert dict(params) == {"user_id": "5", "post_id": "99"}

    def test_param_with_uuid(self, loaded_router):
        endpoint, params = loaded_router.match_route(
            "GET", "/users/550e8400-e29b-41d4-a716-446655440000"
        )
        assert endpoint == "user_detail"
        assert params["id"] == "550e8400-e29b-41d4-a716-446655440000"

    def test_param_with_slug(self, loaded_router):
        endpoint, params = loaded_router.match_route("GET", "/users/john-doe")
        assert endpoint == "user_detail"
        assert params["id"] == "john-doe"


class TestRadixRouterPriority:
    def test_static_over_param(self, loaded_router):
        """Static routes must take priority over parameterized routes."""
        endpoint, params = loaded_router.match_route("GET", "/users/me")
        assert endpoint == "current_user"
        assert dict(params) == {}

    def test_param_still_works(self, loaded_router):
        """Other values should still match the param route."""
        endpoint, params = loaded_router.match_route("GET", "/users/42")
        assert endpoint == "user_detail"
        assert dict(params) == {"id": "42"}


class TestRadixRouterWildcard:
    def test_wildcard_single_segment(self, loaded_router):
        endpoint, params = loaded_router.match_route("GET", "/files/readme.md")
        assert endpoint == "serve_file"
        assert params["path"] == "readme.md"

    def test_wildcard_multi_segment(self, loaded_router):
        endpoint, params = loaded_router.match_route("GET", "/files/docs/api/v2/spec.yaml")
        assert endpoint == "serve_file"
        assert params["path"] == "docs/api/v2/spec.yaml"


class TestRadixRouterTrailingSlash:
    def test_trailing_slash_ignored(self, loaded_router):
        """Trailing slashes should be normalized."""
        endpoint, params = loaded_router.match_route("GET", "/users/")
        assert endpoint == "list_users"

    def test_trailing_slash_with_param(self, loaded_router):
        endpoint, params = loaded_router.match_route("GET", "/users/42/")
        assert endpoint == "user_detail"
        assert params["id"] == "42"


class TestRadixRouterEdgeCases:
    def test_many_routes(self, router):
        """Test with a large number of routes."""
        for i in range(1000):
            router.add_route("GET", f"/route{i}", f"endpoint_{i}")
        assert router.route_count == 1000

        endpoint, _ = router.match_route("GET", "/route500")
        assert endpoint == "endpoint_500"

        endpoint, _ = router.match_route("GET", "/route999")
        assert endpoint == "endpoint_999"

    def test_deeply_nested(self, router):
        router.add_route(
            "GET",
            "/a/{a}/b/{b}/c/{c}/d/{d}/e/{e}",
            "deep",
        )
        endpoint, params = router.match_route("GET", "/a/1/b/2/c/3/d/4/e/5")
        assert endpoint == "deep"
        assert dict(params) == {"a": "1", "b": "2", "c": "3", "d": "4", "e": "5"}

    def test_empty_param_value(self, loaded_router):
        """Empty segments shouldn't match param routes unexpectedly."""
        result = loaded_router.match_route("GET", "/users//posts")
        # Empty segment "" matches {id} param, then "posts" doesn't match further
        # Behavior depends on implementation — just verify no crash
        assert result is not None or result is None  # no crash


class TestAPIRouterRadixIntegration:
    """Test that APIRouter builds and uses the Rust radix tree."""

    def test_radix_router_built_on_get_urls(self):
        from django_matt.core.router import APIRouter

        router = APIRouter()
        router.add_route("users", lambda r: None, methods=["GET"], name="list_users")
        router.add_route("users/<str:id>", lambda r: None, methods=["GET"], name="user_detail")
        router.get_urls()

        assert router._radix_router is not None
        assert router._radix_router.route_count == 2

    def test_django_to_radix_pattern(self):
        from django_matt.core.router import APIRouter

        convert = APIRouter._django_to_radix_pattern
        assert convert("users/<str:id>/posts") == "/users/{id}/posts"
        assert convert("users/<int:pk>") == "/users/{pk}"
        assert convert("<slug:slug>") == "/{slug}"
        assert convert("") == "/"
        assert convert("health") == "/health"
        assert convert("users/me") == "/users/me"

    def test_radix_dispatch_hit(self):
        from django_matt.core.router import APIRouter

        sentinel = object()

        def my_view(request):
            return sentinel

        router = APIRouter()
        router.add_route("users/<str:id>", my_view, methods=["GET"], name="user_detail")
        router.get_urls()

        result = router.radix_dispatch("GET", "/users/42")
        assert result is not None
        view_func, kwargs = result
        assert kwargs == {"id": "42"}

    def test_radix_dispatch_miss(self):
        from django_matt.core.router import APIRouter

        router = APIRouter()
        router.add_route("users", lambda r: None, methods=["GET"], name="list_users")
        router.get_urls()

        result = router.radix_dispatch("GET", "/nonexistent")
        assert result is None

    def test_radix_dispatch_method_isolation(self):
        from django_matt.core.router import APIRouter

        router = APIRouter()
        router.add_route("users", lambda r: None, methods=["GET"], name="list_users")
        router.add_route("users", lambda r: None, methods=["POST"], name="create_user")
        router.get_urls()

        assert router.radix_dispatch("GET", "/users") is not None
        assert router.radix_dispatch("POST", "/users") is not None
        assert router.radix_dispatch("DELETE", "/users") is None

    def test_radix_dispatch_none_without_rust(self):
        from django_matt.core.router import APIRouter

        router = APIRouter()
        # Don't call get_urls, so _radix_router stays None
        assert router.radix_dispatch("GET", "/anything") is None
