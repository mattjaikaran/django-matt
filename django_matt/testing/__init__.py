"""
Django Matt Testing - Test utilities and helpers.

Provides:
- APITestClient with authentication helpers
- Base factory classes for model factories
- pytest fixtures for common testing scenarios
- Custom assertions for API testing

Example:
    from django_matt.testing import APITestClient, UserFactory
    
    class TestUserAPI:
        def test_list_users(self, api_client, user):
            api_client.force_authenticate(user)
            response = api_client.get("/api/users/")
            assert response.status_code == 200
"""

# Test Client
from django_matt.testing.client import (
    APITestClient,
    AsyncAPITestClient,
)

# Factories
from django_matt.testing.factories import (
    BaseModelFactory,
    UserFactory,
    OrganizationFactory,
    TeamFactory,
    MembershipFactory,
)

# Assertions
from django_matt.testing.assertions import (
    assert_status,
    assert_json_equal,
    assert_contains_keys,
    assert_error_response,
    assert_validation_error,
    assert_not_found,
    assert_forbidden,
    assert_unauthorized,
    assert_created,
    assert_no_content,
)

# Fixtures
from django_matt.testing.fixtures import (
    get_api_client,
    get_authenticated_client,
    get_user,
    get_admin_user,
    get_organization,
    get_team,
)

__all__ = [
    # Client
    "APITestClient",
    "AsyncAPITestClient",
    # Factories
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
    # Fixtures
    "get_api_client",
    "get_authenticated_client",
    "get_user",
    "get_admin_user",
    "get_organization",
    "get_team",
]
