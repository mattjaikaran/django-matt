"""
Django Matt Testing - Test utilities and helpers.

Provides:
- APITestClient with authentication helpers
- Built-in model factory system (no factory-boy required)
- Built-in data generators (no Faker required)
- pytest fixtures for common testing scenarios
- Custom assertions for API testing

Example:
    from django_matt.testing import APITestClient, UserFactory, fake

    class TestUserAPI:
        def test_list_users(self, api_client, user):
            api_client.force_authenticate(user)
            response = api_client.get("/api/users/")
            assert response.status_code == 200

    # Use built-in data generators
    email = fake.email()
    name = fake.name()
"""

# Test Client
# Assertions
from django_matt.testing.assertions import (
    assert_contains_keys,
    assert_created,
    assert_error_response,
    assert_forbidden,
    assert_json_equal,
    assert_no_content,
    assert_not_found,
    assert_query_count,
    assert_status,
    assert_unauthorized,
    assert_validation_error,
)
from django_matt.testing.client import (
    APITestClient,
    AsyncAPITestClient,
)

# Pre-built Factories
from django_matt.testing.factories import (
    BaseModelFactory,
    MembershipFactory,
    OrganizationFactory,
    TeamFactory,
    UserFactory,
)

# Fixtures
from django_matt.testing.fixtures import (
    get_admin_user,
    get_api_client,
    get_authenticated_client,
    get_organization,
    get_team,
    get_user,
)

# Built-in Data Generators (replaces Faker)
from django_matt.testing.generators import (
    DataGenerator,
    RandomGenerator,
    fake,
)

# Built-in Model Factory System
from django_matt.testing.model_factory import (
    Field,
    LazyAttribute,
    ModelFactory,
    PostGeneration,
    RelatedFactory,
    Sequence,
    SubFactory,
    factory_for_model,
)

__all__ = [
    # Client
    "APITestClient",
    "AsyncAPITestClient",
    # Model Factory System
    "ModelFactory",
    "Field",
    "LazyAttribute",
    "Sequence",
    "SubFactory",
    "PostGeneration",
    "RelatedFactory",
    "factory_for_model",
    # Data Generators
    "DataGenerator",
    "RandomGenerator",
    "fake",
    # Pre-built Factories
    "BaseModelFactory",
    "UserFactory",
    "OrganizationFactory",
    "TeamFactory",
    "MembershipFactory",
    # Assertions
    "assert_status",
    "assert_json_equal",
    "assert_contains_keys",
    "assert_error_response",
    "assert_validation_error",
    "assert_not_found",
    "assert_forbidden",
    "assert_unauthorized",
    "assert_created",
    "assert_no_content",
    "assert_query_count",
    # Fixtures
    "get_api_client",
    "get_authenticated_client",
    "get_user",
    "get_admin_user",
    "get_organization",
    "get_team",
]
