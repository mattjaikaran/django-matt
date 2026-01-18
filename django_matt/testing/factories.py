"""
Model factories for testing.

Uses built-in factory system (no external dependencies).

Usage:
    from django_matt.testing.factories import UserFactory, OrganizationFactory

    # Create a user
    user = UserFactory.create()
    admin = UserFactory.create_admin()

    # Create with overrides
    user = UserFactory.create(username="testuser", is_staff=True)

    # Create batch
    users = UserFactory.create_batch(5)
"""

import uuid
from typing import Any

from django_matt.testing.generators import fake
from django_matt.testing.model_factory import (
    Field,
    ModelFactory,
    Sequence,
    SubFactory,
)


class BaseModelFactory(ModelFactory):
    """
    Base factory class with common utilities.

    Provides:
    - UUID generation
    - Timestamp handling
    - Batch creation helpers
    """

    class Meta:
        abstract = True

    @classmethod
    def create_batch_dict(cls, size: int, **kwargs) -> list:
        """Create a batch and return as list of dicts."""
        items = cls.create_batch(size, **kwargs)
        return [cls._to_dict(item) for item in items]

    @staticmethod
    def _to_dict(instance) -> dict[str, Any]:
        """Convert a model instance to a dictionary."""
        data = {}
        for field in instance._meta.fields:
            value = getattr(instance, field.name)
            if isinstance(value, uuid.UUID):
                value = str(value)
            data[field.name] = value
        return data


class UserFactory(BaseModelFactory):
    """
    Factory for creating test users.

    Example:
        user = UserFactory.create()
        admin = UserFactory.create(is_staff=True, is_superuser=True)
        users = UserFactory.create_batch(5)
    """

    class Meta:
        model = "auth.User"
        django_get_or_create = ("username",)

    username = Sequence(lambda n: f"user{n}")
    email = Field(lambda self: f"{self.username}@example.com")
    first_name = Field(lambda self: fake.first_name())
    last_name = Field(lambda self: fake.last_name())
    is_active = True
    is_staff = False
    is_superuser = False

    @classmethod
    def _post_create(cls, instance, **kwargs):
        """Set password after creation."""
        password = kwargs.get("password", "testpass123")
        instance.set_password(password)
        instance.save(update_fields=["password"])

    @classmethod
    def create(cls, **kwargs):
        """Create user with password handling."""
        password = kwargs.pop("password", "testpass123")
        instance = super().create(**kwargs)
        instance.set_password(password)
        instance.save(update_fields=["password"])
        return instance

    @classmethod
    def create_admin(cls, **kwargs):
        """Create an admin user."""
        return cls.create(is_staff=True, is_superuser=True, **kwargs)

    @classmethod
    def create_staff(cls, **kwargs):
        """Create a staff user."""
        return cls.create(is_staff=True, **kwargs)


class OrganizationFactory(BaseModelFactory):
    """
    Factory for creating test organizations.

    Example:
        org = OrganizationFactory.create()
        org_with_name = OrganizationFactory.create(name="Acme Corp")
    """

    class Meta:
        model = "multitenancy.Organization"
        django_get_or_create = ("slug",)

    name = Sequence(lambda n: f"Organization {n}")
    slug = Sequence(lambda n: f"org-{n}")
    description = Field(lambda self: fake.paragraph())
    is_active = True


class TeamFactory(BaseModelFactory):
    """
    Factory for creating test teams.

    Example:
        team = TeamFactory.create(organization=org)
    """

    class Meta:
        model = "multitenancy.Team"

    organization = SubFactory(OrganizationFactory)
    name = Sequence(lambda n: f"Team {n}")
    slug = Sequence(lambda n: f"team-{n}")
    description = Field(lambda self: fake.paragraph())
    is_default = False


class MembershipFactory(BaseModelFactory):
    """
    Factory for creating test memberships.

    Example:
        membership = MembershipFactory.create(organization=org, user=user, role="admin")
    """

    class Meta:
        model = "multitenancy.Membership"

    organization = SubFactory(OrganizationFactory)
    user = SubFactory(UserFactory)
    role = "member"

    @classmethod
    def create_owner(cls, **kwargs):
        """Create an owner membership."""
        return cls.create(role="owner", **kwargs)

    @classmethod
    def create_admin(cls, **kwargs):
        """Create an admin membership."""
        return cls.create(role="admin", **kwargs)


# API Key factory (if api_keys module is available)
class APIKeyFactory(BaseModelFactory):
    """
    Factory for creating test API keys.

    Example:
        api_key = APIKeyFactory.create(user=user)
    """

    class Meta:
        model = "api_keys.APIKey"

    user = SubFactory(UserFactory)
    name = Sequence(lambda n: f"API Key {n}")
    is_active = True


__all__ = [
    "APIKeyFactory",
    "BaseModelFactory",
    "MembershipFactory",
    "OrganizationFactory",
    "TeamFactory",
    "UserFactory",
]
