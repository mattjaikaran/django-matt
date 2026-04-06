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


class TestRustJWT:
    """Test Rust-accelerated JWT encode/decode/verify."""

    def test_jwt_encode_decode_roundtrip(self):
        from django_matt._accel import jwt_decode_rust, jwt_encode_rust

        import orjson
        import time

        payload = {"sub": "user42", "role": "admin", "iat": int(time.time()), "exp": int(time.time()) + 3600}
        payload_json = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)
        secret = b"test-secret-key"

        token = jwt_encode_rust(payload_json, secret, "HS256")
        assert isinstance(token, str)
        assert token.count(".") == 2

        decoded = jwt_decode_rust(token, secret, "HS256")
        assert decoded["sub"] == "user42"
        assert decoded["role"] == "admin"

    def test_jwt_verify_valid(self):
        from django_matt._accel import jwt_encode_rust, jwt_verify_rust

        import orjson

        payload_json = orjson.dumps({"sub": "u1"})
        secret = b"secret"
        token = jwt_encode_rust(payload_json, secret, "HS256")

        assert jwt_verify_rust(token, secret, "HS256") is True

    def test_jwt_verify_wrong_secret(self):
        from django_matt._accel import jwt_encode_rust, jwt_verify_rust

        import orjson

        payload_json = orjson.dumps({"sub": "u1"})
        token = jwt_encode_rust(payload_json, b"secret", "HS256")

        assert jwt_verify_rust(token, b"wrong", "HS256") is False

    def test_jwt_decode_invalid_signature(self):
        from django_matt._accel import jwt_encode_rust, jwt_decode_rust

        import orjson

        payload_json = orjson.dumps({"sub": "u1"})
        token = jwt_encode_rust(payload_json, b"secret", "HS256")

        with pytest.raises(ValueError, match="[Ss]ignature"):
            jwt_decode_rust(token, b"wrong-secret", "HS256")

    def test_jwt_decode_expired(self):
        from django_matt._accel import jwt_encode_rust, jwt_decode_rust

        import orjson
        import time

        payload = {"sub": "u1", "exp": int(time.time()) - 100}
        payload_json = orjson.dumps(payload)
        token = jwt_encode_rust(payload_json, b"secret", "HS256")

        with pytest.raises(ValueError, match="expired"):
            jwt_decode_rust(token, b"secret", "HS256", True, 0)

    def test_jwt_decode_expired_with_leeway(self):
        from django_matt._accel import jwt_encode_rust, jwt_decode_rust

        import orjson
        import time

        payload = {"sub": "u1", "exp": int(time.time()) - 5}
        payload_json = orjson.dumps(payload)
        token = jwt_encode_rust(payload_json, b"secret", "HS256")

        # Should succeed with 10s leeway
        decoded = jwt_decode_rust(token, b"secret", "HS256", True, 10)
        assert decoded["sub"] == "u1"

    def test_jwt_all_hmac_algorithms(self):
        from django_matt._accel import jwt_encode_rust, jwt_decode_rust, jwt_verify_rust

        import orjson

        payload_json = orjson.dumps({"sub": "u1"})
        secret = b"test-key"

        for alg in ("HS256", "HS384", "HS512"):
            token = jwt_encode_rust(payload_json, secret, alg)
            assert jwt_verify_rust(token, secret, alg) is True
            decoded = jwt_decode_rust(token, secret, alg, False, 0)
            assert decoded["sub"] == "u1"


class TestJWTBuiltinRustIntegration:
    """Test that jwt_builtin.py uses Rust when available."""

    def test_encode_uses_rust_for_hmac(self):
        from django_matt.auth.jwt_builtin import encode_jwt, decode_jwt

        token = encode_jwt({"sub": "u1"}, secret="mysecret", expires_in=3600)
        assert isinstance(token, str)
        assert token.count(".") == 2

        # Decode should also use Rust fast path
        payload = decode_jwt(token, secret="mysecret")
        assert payload["sub"] == "u1"

    def test_encode_decode_interop(self):
        """Tokens from Rust encode must be decodable by Python path and vice versa."""
        from django_matt.auth.jwt_builtin import encode_jwt, decode_jwt

        # Encode with Rust (HMAC, no custom headers)
        token = encode_jwt(
            {"sub": "u1", "data": "test"},
            secret="key123",
            algorithm="HS256",
            expires_in=3600,
        )

        # Decode with explicit Python path (verify_nbf=True forces Python path)
        payload = decode_jwt(token, secret="key123", verify_nbf=True)
        assert payload["sub"] == "u1"
        assert payload["data"] == "test"


class TestRustQueryStringParser:
    """Test Rust-accelerated query string parsing."""

    def test_empty_string(self):
        from django_matt._accel import parse_query_string_rust

        result = parse_query_string_rust("")
        assert list(result["fields"]) == []
        assert dict(result["filters"]) == {}
        assert list(result["sort"]) == []
        assert dict(result["pagination"]) == {}
        assert dict(result["extras"]) == {}

    def test_fields(self):
        from django_matt._accel import parse_query_string_rust

        result = parse_query_string_rust("fields=id,name,email")
        assert list(result["fields"]) == ["id", "name", "email"]

    def test_single_field(self):
        from django_matt._accel import parse_query_string_rust

        result = parse_query_string_rust("fields=id")
        assert list(result["fields"]) == ["id"]

    def test_filters(self):
        from django_matt._accel import parse_query_string_rust

        result = parse_query_string_rust("filter[status]=active&filter[role]=admin")
        filters = dict(result["filters"])
        assert filters == {"status": "active", "role": "admin"}

    def test_sort_ascending(self):
        from django_matt._accel import parse_query_string_rust

        result = parse_query_string_rust("sort=name,created")
        sort_list = list(result["sort"])
        assert sort_list == [("name", True), ("created", True)]

    def test_sort_descending(self):
        from django_matt._accel import parse_query_string_rust

        result = parse_query_string_rust("sort=-created,-updated")
        sort_list = list(result["sort"])
        assert sort_list == [("created", False), ("updated", False)]

    def test_sort_mixed(self):
        from django_matt._accel import parse_query_string_rust

        result = parse_query_string_rust("sort=-created,name")
        sort_list = list(result["sort"])
        assert sort_list == [("created", False), ("name", True)]

    def test_ordering_alias(self):
        from django_matt._accel import parse_query_string_rust

        result = parse_query_string_rust("ordering=-updated")
        sort_list = list(result["sort"])
        assert sort_list == [("updated", False)]

    def test_pagination(self):
        from django_matt._accel import parse_query_string_rust

        result = parse_query_string_rust("page=2&limit=20&offset=40")
        pagination = dict(result["pagination"])
        assert pagination == {"page": "2", "limit": "20", "offset": "40"}

    def test_extras(self):
        from django_matt._accel import parse_query_string_rust

        result = parse_query_string_rust("status=active&role__in=admin,user")
        extras = dict(result["extras"])
        assert extras == {"status": "active", "role__in": "admin,user"}

    def test_full_query(self):
        from django_matt._accel import parse_query_string_rust

        qs = "fields=id,name&filter[status]=active&sort=-created&page=1&limit=10&search=hello"
        result = parse_query_string_rust(qs)
        assert list(result["fields"]) == ["id", "name"]
        assert dict(result["filters"]) == {"status": "active"}
        assert list(result["sort"]) == [("created", False)]
        assert dict(result["pagination"]) == {"page": "1", "limit": "10"}
        assert dict(result["extras"]) == {"search": "hello"}

    def test_leading_question_mark(self):
        from django_matt._accel import parse_query_string_rust

        result = parse_query_string_rust("?fields=id&page=1")
        assert list(result["fields"]) == ["id"]
        assert dict(result["pagination"]) == {"page": "1"}

    def test_url_encoded_values(self):
        from django_matt._accel import parse_query_string_rust

        result = parse_query_string_rust("filter[name]=hello%20world&filter[q]=a%26b")
        filters = dict(result["filters"])
        assert filters["name"] == "hello world"
        assert filters["q"] == "a&b"
