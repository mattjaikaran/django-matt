"""
Tests for the django_matt.testing module.

Covers:
- ModelFactory: build, create, create_batch, Sequence, SubFactory,
  LazyAttribute, PostGeneration, Field, override fields, reset_sequences
- factory_for_model(): dynamic factory from Django User model, field
  auto-detection, custom overrides
- APITestClient: constructor, force_authenticate, header building,
  JSON methods, set_organization / clear_organization
- AsyncAPITestClient: async force_authenticate, header building,
  inherits from AsyncClient
- Assertion helpers: assert_status, assert_json_equal, assert_contains_keys,
  assert_error_response, assert_list_response, assert_pagination,
  assert_not_found, assert_forbidden, assert_unauthorized, assert_created,
  assert_no_content, assert_validation_error
- DataGenerator: seed reproducibility, name, email, date, numeric, text,
  collections
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import orjson
import pytest
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import AsyncClient, Client

from django_matt.testing.assertions import (
    assert_contains_keys,
    assert_created,
    assert_error_response,
    assert_forbidden,
    assert_json_equal,
    assert_list_response,
    assert_no_content,
    assert_not_found,
    assert_pagination,
    assert_status,
    assert_unauthorized,
    assert_validation_error,
)
from django_matt.testing.client import APITestClient, AsyncAPITestClient
from django_matt.testing.generators import DataGenerator, fake
from django_matt.testing.model_factory import (
    Field,
    LazyAttribute,
    ModelFactory,
    PostGeneration,
    Sequence,
    SubFactory,
    factory_for_model,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(data: dict | list | str, status_code: int = 200) -> HttpResponse:
    """Build a minimal HttpResponse with JSON content for assertion tests."""
    if isinstance(data, (dict, list)):
        content = orjson.dumps(data)
    else:
        content = data.encode("utf-8")
    resp = HttpResponse(content=content, content_type="application/json")
    resp.status_code = status_code
    return resp


# ===========================================================================
# 1. ModelFactory tests
# ===========================================================================

class TestModelFactory:
    """Tests for the core ModelFactory, Field, Sequence, etc."""

    def test_build_returns_unsaved_instance(self):
        """build() should return a model instance with no pk set."""

        class SimpleUserFactory(ModelFactory):
            class Meta:
                model = "auth.User"

            username = Sequence(lambda n: f"builduser{n}")
            is_active = True

        user = SimpleUserFactory.build()
        assert user.pk is None
        assert user.username.startswith("builduser")
        assert user.is_active is True

    @pytest.mark.django_db
    def test_create_saves_to_db(self):
        """create() should persist the instance in the database."""

        class DBUserFactory(ModelFactory):
            class Meta:
                model = "auth.User"

            username = Sequence(lambda n: f"dbuser{n}")
            is_active = True

        user = DBUserFactory.create()
        assert user.pk is not None
        assert User.objects.filter(pk=user.pk).exists()

    @pytest.mark.django_db
    def test_create_batch_creates_multiple(self):
        """create_batch(n) should create exactly n saved instances."""

        class BatchUserFactory(ModelFactory):
            class Meta:
                model = "auth.User"

            username = Sequence(lambda n: f"batchuser{n}")

        users = BatchUserFactory.create_batch(3)
        assert len(users) == 3
        for u in users:
            assert u.pk is not None

    def test_sequence_increments(self):
        """Sequence fields should produce incrementing values across builds."""

        class SeqFactory(ModelFactory):
            class Meta:
                model = "auth.User"

            username = Sequence(lambda n: f"seq{n}")

        SeqFactory.reset_sequences()
        u0 = SeqFactory.build()
        u1 = SeqFactory.build()
        assert u0.username == "seq0"
        assert u1.username == "seq1"

    def test_field_lazy_evaluation_no_args(self):
        """Field with a no-arg callable should invoke it at build time."""

        class LazyFactory(ModelFactory):
            class Meta:
                model = "auth.User"

            username = Sequence(lambda n: f"lazy{n}")
            first_name = Field(lambda: "ComputedFirst")

        user = LazyFactory.build()
        assert user.first_name == "ComputedFirst"

    def test_field_lazy_with_self_reference(self):
        """Field lambda referencing self accesses _values for already-resolved fields."""

        class LazyFactory(ModelFactory):
            class Meta:
                model = "auth.User"

            username = Sequence(lambda n: f"lazy{n}")
            # Field that uses self — the factory stores resolved values in _values,
            # so self.username returns the resolved string from __getattr__
            # only if 'username' is NOT a class attribute. Because Sequence IS a class
            # attribute, self.username returns the Sequence dataclass. Verify that
            # the field's callable receives the factory instance and can access _values.
            email = Field(lambda self: f"{self._values.get('username', 'fallback')}@test.io")

        LazyFactory.reset_sequences()
        user = LazyFactory.build()
        assert user.email == "lazy0@test.io"

    def test_lazy_attribute_alias(self):
        """LazyAttribute should behave identically to Field (callable with self)."""

        class LAFactory(ModelFactory):
            class Meta:
                model = "auth.User"

            username = Sequence(lambda n: f"la{n}")
            email = LazyAttribute(lambda obj: f"{obj._values.get('username', 'x')}@lazy.com")

        LAFactory.reset_sequences()
        user = LAFactory.build()
        assert user.email == "la0@lazy.com"

    def test_override_fields(self):
        """Explicit kwargs should override factory defaults."""

        class OverrideFactory(ModelFactory):
            class Meta:
                model = "auth.User"

            username = Sequence(lambda n: f"over{n}")
            is_staff = False

        user = OverrideFactory.build(username="custom", is_staff=True)
        assert user.username == "custom"
        assert user.is_staff is True

    def test_reset_sequences(self):
        """reset_sequences() should reset the counter back to 0."""

        class ResetFactory(ModelFactory):
            class Meta:
                model = "auth.User"

            username = Sequence(lambda n: f"reset{n}")

        ResetFactory.reset_sequences()
        u0 = ResetFactory.build()
        assert u0.username == "reset0"
        ResetFactory.reset_sequences()
        u0_again = ResetFactory.build()
        assert u0_again.username == "reset0"


# ===========================================================================
# 2. factory_for_model() tests
# ===========================================================================

class TestFactoryForModel:
    """Tests for the dynamic factory_for_model() helper."""

    def test_creates_factory_class(self):
        """factory_for_model should return a ModelFactory subclass."""
        DynFactory = factory_for_model(
            "auth.User",
            username=Sequence(lambda n: f"dyn{n}"),
        )
        assert issubclass(DynFactory, ModelFactory)

    def test_build_with_dynamic_factory(self):
        """Dynamic factory should produce valid unsaved instances."""
        DynFactory = factory_for_model(
            "auth.User",
            username=Sequence(lambda n: f"dynbuild{n}"),
        )
        DynFactory.reset_sequences()
        user = DynFactory.build()
        assert user.username == "dynbuild0"
        assert user.pk is None

    @pytest.mark.django_db
    def test_create_with_dynamic_factory(self):
        """Dynamic factory create() should save to the database."""
        DynFactory = factory_for_model(
            "auth.User",
            username=Sequence(lambda n: f"dyncreate{n}"),
        )
        user = DynFactory.create()
        assert user.pk is not None
        assert User.objects.filter(pk=user.pk).exists()

    def test_custom_field_overrides(self):
        """Dynamic factory should accept Field definitions and kwargs."""
        DynFactory = factory_for_model(
            "auth.User",
            username=Sequence(lambda n: f"dynov{n}"),
            is_staff=True,
        )
        user = DynFactory.build()
        assert user.is_staff is True


# ===========================================================================
# 3. APITestClient tests
# ===========================================================================

class TestAPITestClient:
    """Tests for the sync APITestClient."""

    def test_constructor_defaults(self):
        """Constructor should initialize auth state to None."""
        client = APITestClient()
        assert client._auth_token is None
        assert client._organization_id is None
        assert client._user is None

    def test_inherits_from_django_client(self):
        """APITestClient should be a subclass of Django's test Client."""
        assert issubclass(APITestClient, Client)

    def test_force_authenticate_with_token(self):
        """force_authenticate(token=...) should store the token directly."""
        client = APITestClient()
        client.force_authenticate(token="my-jwt-token")
        assert client._auth_token == "my-jwt-token"

    def test_header_building_with_auth(self):
        """_get_headers should include Authorization when token is set."""
        client = APITestClient()
        client._auth_token = "tok123"
        headers = client._get_headers()
        assert headers["HTTP_AUTHORIZATION"] == "Bearer tok123"

    def test_header_building_with_organization(self):
        """_get_headers should include X-Organization-ID when set."""
        client = APITestClient()
        client._organization_id = "org-abc"
        headers = client._get_headers()
        assert headers["HTTP_X_ORGANIZATION_ID"] == "org-abc"

    def test_header_building_extra_headers_normalized(self):
        """Extra headers without HTTP_ prefix should be auto-prefixed."""
        client = APITestClient()
        headers = client._get_headers({"X-Custom": "value"})
        assert headers["HTTP_X_CUSTOM"] == "value"

    def test_set_organization_with_string(self):
        """set_organization with a plain string should store it."""
        client = APITestClient()
        client.set_organization("org-42")
        assert client._organization_id == "org-42"

    def test_set_organization_with_object(self):
        """set_organization with an object having .id should use str(id)."""
        org = MagicMock()
        org.id = 99
        client = APITestClient()
        client.set_organization(org)
        assert client._organization_id == "99"

    def test_clear_organization(self):
        """clear_organization should reset organization_id to None."""
        client = APITestClient()
        client.set_organization("org-x")
        client.clear_organization()
        assert client._organization_id is None

    @pytest.mark.django_db
    def test_logout_clears_state(self):
        """logout() should clear auth token and user."""
        client = APITestClient()
        client._auth_token = "tok"
        client._user = "some-user"
        client.logout()
        assert client._auth_token is None
        assert client._user is None

    def test_json_static_method(self):
        """APITestClient.json() should parse orjson-encoded content."""
        resp = HttpResponse(
            content=orjson.dumps({"key": "value"}),
            content_type="application/json",
        )
        result = APITestClient.json(resp)
        assert result == {"key": "value"}

    # --- Cookie helpers ---

    def test_set_cookie(self):
        """set_cookie should store a cookie in the cookie jar."""
        client = APITestClient()
        client.set_cookie("session_id", "abc123")
        assert client.get_cookie("session_id") == "abc123"

    def test_set_cookie_with_attributes(self):
        """set_cookie should accept extra cookie attributes."""
        client = APITestClient()
        client.set_cookie("token", "xyz", max_age=3600, path="/api")
        assert client.get_cookie("token") == "xyz"
        morsel = client.cookies["token"]
        assert morsel["max-age"] == 3600
        assert morsel["path"] == "/api"

    def test_get_cookie_returns_none_for_missing(self):
        """get_cookie should return None for a cookie that doesn't exist."""
        client = APITestClient()
        assert client.get_cookie("nonexistent") is None

    def test_delete_cookie(self):
        """delete_cookie should remove a cookie from the jar."""
        client = APITestClient()
        client.set_cookie("temp", "val")
        assert client.get_cookie("temp") == "val"
        client.delete_cookie("temp")
        assert client.get_cookie("temp") is None

    def test_delete_cookie_noop_for_missing(self):
        """delete_cookie should not raise for a missing cookie."""
        client = APITestClient()
        client.delete_cookie("nope")  # should not raise

    def test_clear_cookies(self):
        """clear_cookies should remove all cookies."""
        client = APITestClient()
        client.set_cookie("a", "1")
        client.set_cookie("b", "2")
        client.clear_cookies()
        assert client.get_cookie("a") is None
        assert client.get_cookie("b") is None

    def test_cookies_persist_across_manual_sets(self):
        """Multiple set_cookie calls should all persist."""
        client = APITestClient()
        client.set_cookie("csrf", "tok1")
        client.set_cookie("session", "tok2")
        assert client.get_cookie("csrf") == "tok1"
        assert client.get_cookie("session") == "tok2"


# ===========================================================================
# 4. AsyncAPITestClient tests
# ===========================================================================

class TestAsyncAPITestClient:
    """Tests for the async AsyncAPITestClient."""

    def test_inherits_from_async_client(self):
        """AsyncAPITestClient should subclass Django's AsyncClient."""
        assert issubclass(AsyncAPITestClient, AsyncClient)

    async def test_force_authenticate_with_token(self):
        """Async force_authenticate should store the provided token."""
        client = AsyncAPITestClient()
        await client.force_authenticate(token="async-tok")
        assert client._auth_token == "async-tok"

    def test_header_building_with_auth(self):
        """_get_headers should include Authorization when token is set."""
        client = AsyncAPITestClient()
        client._auth_token = "atok"
        headers = client._get_headers()
        assert headers["HTTP_AUTHORIZATION"] == "Bearer atok"

    def test_set_organization(self):
        """set_organization should store the org id."""
        client = AsyncAPITestClient()
        client.set_organization("async-org-1")
        assert client._organization_id == "async-org-1"

    def test_clear_organization(self):
        """clear_organization should reset organization_id to None."""
        client = AsyncAPITestClient()
        client.set_organization("org-async")
        client.clear_organization()
        assert client._organization_id is None

    def test_logout_clears_state(self):
        """logout() should clear auth token and user."""
        client = AsyncAPITestClient()
        client._auth_token = "tok"
        client._user = "some-user"
        client.logout()
        assert client._auth_token is None
        assert client._user is None

    # --- Cookie helpers ---

    def test_set_cookie(self):
        """set_cookie should store a cookie in the async client cookie jar."""
        client = AsyncAPITestClient()
        client.set_cookie("session_id", "abc123")
        assert client.get_cookie("session_id") == "abc123"

    def test_get_cookie_returns_none_for_missing(self):
        """get_cookie should return None for a cookie that doesn't exist."""
        client = AsyncAPITestClient()
        assert client.get_cookie("nonexistent") is None

    def test_delete_cookie(self):
        """delete_cookie should remove a cookie from the jar."""
        client = AsyncAPITestClient()
        client.set_cookie("temp", "val")
        client.delete_cookie("temp")
        assert client.get_cookie("temp") is None

    def test_clear_cookies(self):
        """clear_cookies should remove all cookies."""
        client = AsyncAPITestClient()
        client.set_cookie("a", "1")
        client.set_cookie("b", "2")
        client.clear_cookies()
        assert client.get_cookie("a") is None
        assert client.get_cookie("b") is None


# ===========================================================================
# 5. Assertion helpers tests
# ===========================================================================

class TestAssertionHelpers:
    """Tests for the custom assertion functions."""

    # --- assert_status ---

    def test_assert_status_passes_on_match(self):
        resp = _make_response({"ok": True}, 200)
        assert_status(resp, 200)  # should not raise

    def test_assert_status_fails_on_mismatch(self):
        resp = _make_response({"error": "bad"}, 400)
        with pytest.raises(AssertionError, match="Expected status 200"):
            assert_status(resp, 200)

    def test_assert_status_custom_message(self):
        resp = _make_response({}, 500)
        with pytest.raises(AssertionError, match="custom msg"):
            assert_status(resp, 200, message="custom msg")

    # --- assert_json_equal ---

    def test_assert_json_equal_passes(self):
        resp = _make_response({"a": 1, "b": 2})
        assert_json_equal(resp, {"a": 1, "b": 2})

    def test_assert_json_equal_fails_on_mismatch(self):
        resp = _make_response({"a": 1})
        with pytest.raises(AssertionError, match="JSON mismatch"):
            assert_json_equal(resp, {"a": 2})

    def test_assert_json_equal_fails_on_non_json(self):
        resp = HttpResponse(content=b"not json", content_type="text/plain")
        with pytest.raises(AssertionError, match="not valid JSON"):
            assert_json_equal(resp, {})

    # --- assert_contains_keys ---

    def test_assert_contains_keys_passes(self):
        resp = _make_response({"name": "x", "email": "y"})
        assert_contains_keys(resp, ["name", "email"])

    def test_assert_contains_keys_fails_on_missing(self):
        resp = _make_response({"name": "x"})
        with pytest.raises(AssertionError, match="Missing keys"):
            assert_contains_keys(resp, ["name", "email"])

    # --- assert_error_response ---

    def test_assert_error_response_passes(self):
        resp = _make_response({"error": "something went wrong"}, 400)
        assert_error_response(resp, 400)

    def test_assert_error_response_detail_key(self):
        """Should also accept 'detail' as an error key."""
        resp = _make_response({"detail": "not found"}, 404)
        assert_error_response(resp, 404)

    def test_assert_error_response_fails_wrong_status(self):
        resp = _make_response({"error": "x"}, 200)
        with pytest.raises(AssertionError):
            assert_error_response(resp, 400)

    # --- assert_list_response ---

    def test_assert_list_response_passes(self):
        resp = _make_response({"items": [1, 2, 3], "count": 3})
        assert_list_response(resp, min_count=1)

    def test_assert_list_response_with_direct_list(self):
        resp = _make_response([1, 2, 3])
        assert_list_response(resp, min_count=1, max_count=5)

    def test_assert_list_response_fails_under_min(self):
        resp = _make_response({"items": [1], "count": 1})
        with pytest.raises(AssertionError, match="at least 5"):
            assert_list_response(resp, min_count=5)

    def test_assert_list_response_fails_over_max(self):
        resp = _make_response({"items": [1, 2, 3], "count": 3})
        with pytest.raises(AssertionError, match="at most 1"):
            assert_list_response(resp, max_count=1)

    # --- assert_pagination ---

    def test_assert_pagination_passes(self):
        resp = _make_response({
            "items": [],
            "page": 1,
            "page_size": 10,
            "total": 0,
            "total_pages": 0,
        })
        assert_pagination(resp)

    def test_assert_pagination_fails_no_keys(self):
        resp = _make_response({"items": []})
        with pytest.raises(AssertionError, match="pagination"):
            assert_pagination(resp)

    # --- convenience wrappers ---

    def test_assert_not_found(self):
        resp = _make_response({}, 404)
        assert_not_found(resp)

    def test_assert_forbidden(self):
        resp = _make_response({}, 403)
        assert_forbidden(resp)

    def test_assert_unauthorized(self):
        resp = _make_response({}, 401)
        assert_unauthorized(resp)

    def test_assert_created(self):
        resp = _make_response({"id": 1}, 201)
        assert_created(resp)

    def test_assert_no_content(self):
        resp = HttpResponse(status=204)
        assert_no_content(resp)

    # --- assert_validation_error ---

    def test_assert_validation_error_passes(self):
        resp = _make_response({"errors": [{"loc": ["body", "name"], "msg": "required"}]}, 422)
        assert_validation_error(resp, field="name")

    def test_assert_validation_error_fails_wrong_status(self):
        resp = _make_response({}, 400)
        with pytest.raises(AssertionError):
            assert_validation_error(resp)


# ===========================================================================
# 6. DataGenerator tests
# ===========================================================================

class TestDataGenerator:
    """Tests for the built-in DataGenerator (fake) instance."""

    def test_seed_reproducibility(self):
        """Same seed should produce identical sequences."""
        gen1 = DataGenerator(seed=42)
        gen2 = DataGenerator(seed=42)
        assert gen1.name() == gen2.name()
        assert gen1.email() == gen2.email()
        assert gen1.random_int() == gen2.random_int()

    def test_name_returns_string(self):
        result = fake.name()
        assert isinstance(result, str)
        assert " " in result  # first + last

    def test_first_name_male(self):
        gen = DataGenerator(seed=1)
        name = gen.first_name(gender="male")
        assert name in gen._first_names_male

    def test_email_format(self):
        email = fake.email()
        assert "@" in email
        assert "." in email.split("@")[1]

    def test_safe_email_uses_example_domain(self):
        email = fake.safe_email()
        assert email.endswith("@example.com")

    def test_date_this_year_in_current_year(self):
        d = fake.date_this_year()
        assert isinstance(d, date)
        assert d.year == date.today().year

    def test_random_int_within_bounds(self):
        for _ in range(20):
            val = fake.random_int(min=10, max=20)
            assert 10 <= val <= 20

    def test_random_float_within_bounds(self):
        for _ in range(20):
            val = fake.random_float(min=1.0, max=5.0, precision=2)
            assert 1.0 <= val <= 5.0

    def test_sentence_returns_string_ending_with_period(self):
        s = fake.sentence()
        assert isinstance(s, str)
        assert s.endswith(".")

    def test_paragraph_is_nonempty(self):
        p = fake.paragraph()
        assert isinstance(p, str)
        assert len(p) > 10

    def test_random_element(self):
        elements = ["a", "b", "c"]
        result = fake.random_element(elements)
        assert result in elements

    def test_random_elements_length(self):
        elements = [1, 2, 3, 4, 5]
        result = fake.random_elements(elements, length=4)
        assert len(result) == 4

    def test_random_sample_unique(self):
        elements = [1, 2, 3, 4, 5]
        sample = fake.random_sample(elements, length=3)
        assert len(sample) == 3
        assert len(set(sample)) == 3  # all unique

    def test_uuid4_format(self):
        u = fake.uuid4()
        assert len(u) == 36
        assert u.count("-") == 4

    def test_boolean_returns_bool(self):
        result = fake.boolean()
        assert isinstance(result, bool)
