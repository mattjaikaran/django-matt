"""
Model factories for testing.

Uses factory_boy for generating test data.
"""

import uuid
from typing import Any, Dict, Optional, Type

try:
    import factory
    from factory.django import DjangoModelFactory
    FACTORY_BOY_AVAILABLE = True
except ImportError:
    FACTORY_BOY_AVAILABLE = False
    # Create stub classes when factory_boy is not installed
    class DjangoModelFactory:
        pass
    factory = None


class BaseModelFactory(DjangoModelFactory if FACTORY_BOY_AVAILABLE else object):
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
        if not FACTORY_BOY_AVAILABLE:
            raise ImportError("factory_boy is required for factories")
        
        items = cls.create_batch(size, **kwargs)
        return [cls._to_dict(item) for item in items]
    
    @staticmethod
    def _to_dict(instance) -> Dict[str, Any]:
        """Convert a model instance to a dictionary."""
        data = {}
        for field in instance._meta.fields:
            value = getattr(instance, field.name)
            if isinstance(value, uuid.UUID):
                value = str(value)
            data[field.name] = value
        return data


if FACTORY_BOY_AVAILABLE:
    from django.contrib.auth import get_user_model
    
    class UserFactory(BaseModelFactory):
        """
        Factory for creating test users.
        
        Example:
            user = UserFactory()
            admin = UserFactory(is_staff=True, is_superuser=True)
            users = UserFactory.create_batch(5)
        """
        
        class Meta:
            model = get_user_model()
            django_get_or_create = ("username",)
        
        username = factory.Sequence(lambda n: f"user{n}")
        email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
        password = factory.PostGenerationMethodCall("set_password", "testpass123")
        is_active = True
        is_staff = False
        is_superuser = False
        first_name = factory.Faker("first_name")
        last_name = factory.Faker("last_name")
        
        @classmethod
        def create_admin(cls, **kwargs):
            """Create an admin user."""
            return cls(is_staff=True, is_superuser=True, **kwargs)
        
        @classmethod
        def create_staff(cls, **kwargs):
            """Create a staff user."""
            return cls(is_staff=True, **kwargs)
    
    
    class OrganizationFactory(BaseModelFactory):
        """
        Factory for creating test organizations.
        
        Example:
            org = OrganizationFactory()
            org_with_name = OrganizationFactory(name="Acme Corp")
        """
        
        class Meta:
            model = "multitenancy.Organization"
            django_get_or_create = ("slug",)
        
        name = factory.Sequence(lambda n: f"Organization {n}")
        slug = factory.Sequence(lambda n: f"org-{n}")
        description = factory.Faker("paragraph")
        is_active = True
        
        @classmethod
        def _get_model_class(cls):
            """Dynamically get the model class."""
            try:
                from django_matt.multitenancy.models import Organization
                return Organization
            except ImportError:
                return None
    
    
    class TeamFactory(BaseModelFactory):
        """
        Factory for creating test teams.
        
        Example:
            team = TeamFactory(organization=org)
        """
        
        class Meta:
            model = "multitenancy.Team"
        
        organization = factory.SubFactory(OrganizationFactory)
        name = factory.Sequence(lambda n: f"Team {n}")
        slug = factory.Sequence(lambda n: f"team-{n}")
        description = factory.Faker("paragraph")
        is_default = False
        
        @classmethod
        def _get_model_class(cls):
            """Dynamically get the model class."""
            try:
                from django_matt.multitenancy.models import Team
                return Team
            except ImportError:
                return None
    
    
    class MembershipFactory(BaseModelFactory):
        """
        Factory for creating test memberships.
        
        Example:
            membership = MembershipFactory(organization=org, user=user, role="admin")
        """
        
        class Meta:
            model = "multitenancy.Membership"
        
        organization = factory.SubFactory(OrganizationFactory)
        user = factory.SubFactory(UserFactory)
        role = "member"
        
        @classmethod
        def _get_model_class(cls):
            """Dynamically get the model class."""
            try:
                from django_matt.multitenancy.models import Membership
                return Membership
            except ImportError:
                return None
        
        @classmethod
        def create_owner(cls, **kwargs):
            """Create an owner membership."""
            return cls(role="owner", **kwargs)
        
        @classmethod
        def create_admin(cls, **kwargs):
            """Create an admin membership."""
            return cls(role="admin", **kwargs)

else:
    # Stub factories when factory_boy is not installed
    class UserFactory:
        """Stub factory - install factory_boy for full functionality."""
        
        @classmethod
        def create(cls, **kwargs):
            raise ImportError("factory_boy is required: pip install factory_boy")
        
        @classmethod
        def create_batch(cls, size, **kwargs):
            raise ImportError("factory_boy is required: pip install factory_boy")
    
    class OrganizationFactory:
        """Stub factory - install factory_boy for full functionality."""
        
        @classmethod
        def create(cls, **kwargs):
            raise ImportError("factory_boy is required: pip install factory_boy")
    
    class TeamFactory:
        """Stub factory - install factory_boy for full functionality."""
        
        @classmethod
        def create(cls, **kwargs):
            raise ImportError("factory_boy is required: pip install factory_boy")
    
    class MembershipFactory:
        """Stub factory - install factory_boy for full functionality."""
        
        @classmethod
        def create(cls, **kwargs):
            raise ImportError("factory_boy is required: pip install factory_boy")
