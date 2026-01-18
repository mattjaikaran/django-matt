"""
pytest fixtures for common testing scenarios.

These fixtures can be used with pytest-django for testing Django Matt applications.

Usage:
    # In your conftest.py
    from django_matt.testing.fixtures import *

    # Or import specific fixtures
    from django_matt.testing.fixtures import get_api_client, get_user
"""

try:
    import pytest

    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False

    # Create a stub decorator
    class pytest:
        @staticmethod
        def fixture(*args, **kwargs):
            def decorator(func):
                return func

            return decorator


from django_matt.testing.client import APITestClient


def get_api_client() -> APITestClient:
    """
    Create and return an API test client.

    Usage:
        @pytest.fixture
        def api_client():
            return get_api_client()

    Returns:
        APITestClient instance
    """
    return APITestClient()


def get_authenticated_client(user) -> APITestClient:
    """
    Create and return an authenticated API test client.

    Args:
        user: User to authenticate as

    Usage:
        @pytest.fixture
        def auth_client(user):
            return get_authenticated_client(user)

    Returns:
        Authenticated APITestClient instance
    """
    client = APITestClient()
    client.force_authenticate(user)
    return client


def get_user(
    username: str = "testuser",
    email: str | None = None,
    password: str = "testpass123",
    is_staff: bool = False,
    is_superuser: bool = False,
    **kwargs,
):
    """
    Create and return a test user.

    Args:
        username: Username for the user
        email: Email address (defaults to username@example.com)
        password: Password for the user
        is_staff: Whether user is staff
        is_superuser: Whether user is superuser
        **kwargs: Additional user fields

    Usage:
        @pytest.fixture
        def user(db):
            return get_user()

    Returns:
        User instance
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()

    if email is None:
        email = f"{username}@example.com"

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        is_staff=is_staff,
        is_superuser=is_superuser,
        **kwargs,
    )

    return user


def get_admin_user(
    username: str = "admin",
    email: str = "admin@example.com",
    password: str = "adminpass123",
    **kwargs,
):
    """
    Create and return an admin user.

    Usage:
        @pytest.fixture
        def admin_user(db):
            return get_admin_user()

    Returns:
        Admin User instance
    """
    return get_user(
        username=username,
        email=email,
        password=password,
        is_staff=True,
        is_superuser=True,
        **kwargs,
    )


def get_organization(
    name: str = "Test Organization",
    slug: str = "test-org",
    **kwargs,
):
    """
    Create and return a test organization.

    Usage:
        @pytest.fixture
        def organization(db):
            return get_organization()

    Returns:
        Organization instance
    """
    try:
        from django_matt.multitenancy.models import Organization
    except ImportError:
        raise ImportError("Multitenancy models not available")

    org = Organization.objects.create(
        name=name,
        slug=slug,
        **kwargs,
    )

    return org


def get_team(
    organization,
    name: str = "Test Team",
    slug: str = "test-team",
    **kwargs,
):
    """
    Create and return a test team.

    Args:
        organization: Parent organization
        name: Team name
        slug: Team slug
        **kwargs: Additional team fields

    Usage:
        @pytest.fixture
        def team(db, organization):
            return get_team(organization)

    Returns:
        Team instance
    """
    try:
        from django_matt.multitenancy.models import Team
    except ImportError:
        raise ImportError("Multitenancy models not available")

    team = Team.objects.create(
        organization=organization,
        name=name,
        slug=slug,
        **kwargs,
    )

    return team


def get_membership(
    organization,
    user,
    role: str = "member",
    **kwargs,
):
    """
    Create and return a test membership.

    Args:
        organization: Organization to add user to
        user: User to add
        role: Role in the organization
        **kwargs: Additional membership fields

    Usage:
        @pytest.fixture
        def membership(db, organization, user):
            return get_membership(organization, user)

    Returns:
        Membership instance
    """
    try:
        from django_matt.multitenancy.models import Membership
    except ImportError:
        raise ImportError("Multitenancy models not available")

    membership = Membership.objects.create(
        organization=organization,
        user=user,
        role=role,
        **kwargs,
    )

    return membership


# pytest fixtures (when pytest is available)
if PYTEST_AVAILABLE:

    @pytest.fixture
    def api_client() -> APITestClient:
        """pytest fixture for API test client."""
        return get_api_client()

    @pytest.fixture
    def user(db):
        """pytest fixture for a regular user."""
        return get_user()

    @pytest.fixture
    def admin_user(db):
        """pytest fixture for an admin user."""
        return get_admin_user()

    @pytest.fixture
    def authenticated_client(api_client, user) -> APITestClient:
        """pytest fixture for an authenticated client."""
        api_client.force_authenticate(user)
        return api_client

    @pytest.fixture
    def admin_client(api_client, admin_user) -> APITestClient:
        """pytest fixture for an admin-authenticated client."""
        api_client.force_authenticate(admin_user)
        return api_client


# Additional helper functions


def create_test_token(user) -> str:
    """
    Create a JWT token for testing.

    Args:
        user: User to create token for

    Returns:
        JWT token string
    """
    try:
        from django_matt.auth import create_access_token

        return create_access_token(user)
    except ImportError:
        raise ImportError("JWT authentication not available")


def parse_json_response(response) -> dict:
    """
    Parse JSON from response.

    Args:
        response: HttpResponse object

    Returns:
        Parsed JSON data
    """
    import json

    return json.loads(response.content)


def get_response_data(response, key: str | None = None):
    """
    Get data from JSON response.

    Args:
        response: HttpResponse object
        key: Optional key to extract

    Returns:
        Response data or specific key value
    """
    data = parse_json_response(response)
    if key:
        return data.get(key)
    return data
