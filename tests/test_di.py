"""
Tests for the Dependency Injection module in Django Matt.
"""

from unittest.mock import MagicMock

import pytest
from django.test import RequestFactory, TestCase

from django_matt.di import (
    CircularDependencyError,
    Container,
    Depends,
    DependencyMarker,
    Scoped,
    ServiceDescriptor,
    ServiceLifetime,
    ServiceNotFoundError,
    Singleton,
    Transient,
    container,
)
from django_matt.di.depends import resolve_dependencies


# =============================================================================
# Test Service Classes
# =============================================================================


class EmailService:
    """Simple service for testing."""

    def send(self, to: str, subject: str):
        pass


class DatabaseService:
    """Simple database service for testing."""

    def query(self, sql: str):
        pass


class UserService:
    """Service with dependencies for testing."""

    def __init__(self, email: EmailService, db: DatabaseService):
        self.email = email
        self.db = db


class ConfigService:
    """Service that can be created via factory."""

    def __init__(self, env: str = "production"):
        self.env = env


class ServiceA:
    """Service for circular dependency testing."""

    def __init__(self, b: "ServiceB"):
        self.b = b


class ServiceB:
    """Service for circular dependency testing."""

    def __init__(self, a: ServiceA):
        self.a = a


# =============================================================================
# ServiceLifetime Tests
# =============================================================================


class TestServiceLifetime(TestCase):
    """Tests for ServiceLifetime enum."""

    def test_singleton_value(self):
        """Test SINGLETON enum value."""
        self.assertEqual(ServiceLifetime.SINGLETON.value, "singleton")
        self.assertEqual(Singleton, ServiceLifetime.SINGLETON)

    def test_scoped_value(self):
        """Test SCOPED enum value."""
        self.assertEqual(ServiceLifetime.SCOPED.value, "scoped")
        self.assertEqual(Scoped, ServiceLifetime.SCOPED)

    def test_transient_value(self):
        """Test TRANSIENT enum value."""
        self.assertEqual(ServiceLifetime.TRANSIENT.value, "transient")
        self.assertEqual(Transient, ServiceLifetime.TRANSIENT)


# =============================================================================
# ServiceDescriptor Tests
# =============================================================================


class TestServiceDescriptor(TestCase):
    """Tests for ServiceDescriptor."""

    def test_basic_descriptor(self):
        """Test basic descriptor creation."""
        desc = ServiceDescriptor(
            service_type=EmailService,
            lifetime=ServiceLifetime.SINGLETON,
        )
        self.assertEqual(desc.service_type, EmailService)
        self.assertEqual(desc.implementation, EmailService)
        self.assertEqual(desc.lifetime, ServiceLifetime.SINGLETON)

    def test_descriptor_with_implementation(self):
        """Test descriptor with different implementation."""

        class IEmailService:
            pass

        desc = ServiceDescriptor(
            service_type=IEmailService,
            implementation=EmailService,
        )
        self.assertEqual(desc.service_type, IEmailService)
        self.assertEqual(desc.implementation, EmailService)

    def test_descriptor_with_instance(self):
        """Test descriptor with pre-registered instance."""
        instance = EmailService()
        desc = ServiceDescriptor(
            service_type=EmailService,
            instance=instance,
        )
        self.assertEqual(desc._instance, instance)

    def test_descriptor_repr(self):
        """Test descriptor string representation."""
        desc = ServiceDescriptor(
            service_type=EmailService,
            lifetime=ServiceLifetime.SINGLETON,
        )
        repr_str = repr(desc)
        self.assertIn("EmailService", repr_str)
        self.assertIn("singleton", repr_str)


# =============================================================================
# ServiceNotFoundError Tests
# =============================================================================


class TestServiceNotFoundError(TestCase):
    """Tests for ServiceNotFoundError."""

    def test_error_message(self):
        """Test error message includes service type."""
        error = ServiceNotFoundError(EmailService)
        self.assertIn("EmailService", str(error))
        self.assertEqual(error.service_type, EmailService)


# =============================================================================
# CircularDependencyError Tests
# =============================================================================


class TestCircularDependencyError(TestCase):
    """Tests for CircularDependencyError."""

    def test_error_message(self):
        """Test error message includes dependency chain."""
        error = CircularDependencyError([ServiceA, ServiceB, ServiceA])
        self.assertIn("ServiceA", str(error))
        self.assertIn("ServiceB", str(error))
        self.assertIn("->", str(error))
        self.assertEqual(error.chain, [ServiceA, ServiceB, ServiceA])


# =============================================================================
# Container Tests
# =============================================================================


class TestContainer(TestCase):
    """Tests for Container."""

    def setUp(self):
        """Set up test container."""
        self.container = Container()

    def test_register_and_resolve(self):
        """Test basic registration and resolution."""
        self.container.register(EmailService)

        instance = self.container.resolve(EmailService)
        self.assertIsInstance(instance, EmailService)

    def test_register_with_lifetime(self):
        """Test registration with lifetime."""
        self.container.register(EmailService, lifetime=Singleton)

        self.assertTrue(self.container.is_registered(EmailService))

    def test_register_with_implementation(self):
        """Test registration with different implementation."""

        class IService:
            pass

        self.container.register(IService, EmailService)

        instance = self.container.resolve(IService)
        self.assertIsInstance(instance, EmailService)

    def test_register_instance(self):
        """Test registering an existing instance."""
        instance = EmailService()
        self.container.register_instance(instance, EmailService)

        resolved = self.container.resolve(EmailService)
        self.assertIs(resolved, instance)

    def test_register_factory(self):
        """Test registration with factory function."""

        def create_config():
            return ConfigService(env="test")

        self.container.register_factory(ConfigService, create_config)

        instance = self.container.resolve(ConfigService)
        self.assertEqual(instance.env, "test")

    def test_singleton_returns_same_instance(self):
        """Test singleton lifetime returns same instance."""
        self.container.register(EmailService, lifetime=Singleton)

        instance1 = self.container.resolve(EmailService)
        instance2 = self.container.resolve(EmailService)

        self.assertIs(instance1, instance2)

    def test_transient_returns_new_instance(self):
        """Test transient lifetime returns new instance."""
        self.container.register(EmailService, lifetime=Transient)

        instance1 = self.container.resolve(EmailService)
        instance2 = self.container.resolve(EmailService)

        self.assertIsNot(instance1, instance2)

    def test_scoped_within_scope(self):
        """Test scoped lifetime within a scope."""
        self.container.register(EmailService, lifetime=Scoped)

        with self.container.create_scope() as scope:
            instance1 = scope.resolve(EmailService)
            instance2 = scope.resolve(EmailService)
            self.assertIs(instance1, instance2)

    def test_scoped_different_scopes(self):
        """Test scoped lifetime across different scopes."""
        self.container.register(EmailService, lifetime=Scoped)

        with self.container.create_scope() as scope1:
            instance1 = scope1.resolve(EmailService)

        with self.container.create_scope() as scope2:
            instance2 = scope2.resolve(EmailService)

        self.assertIsNot(instance1, instance2)

    def test_resolve_with_dependencies(self):
        """Test resolving service with dependencies."""
        self.container.register(EmailService, lifetime=Singleton)
        self.container.register(DatabaseService, lifetime=Singleton)
        self.container.register(UserService, lifetime=Singleton)

        instance = self.container.resolve(UserService)

        self.assertIsInstance(instance, UserService)
        self.assertIsInstance(instance.email, EmailService)
        self.assertIsInstance(instance.db, DatabaseService)

    def test_service_not_found_error(self):
        """Test error when service not registered."""
        with self.assertRaises(ServiceNotFoundError) as ctx:
            self.container.resolve(EmailService)

        self.assertEqual(ctx.exception.service_type, EmailService)

    def test_circular_dependency_error(self):
        """Test error on circular dependencies."""
        self.container.register(ServiceA, lifetime=Singleton)
        self.container.register(ServiceB, lifetime=Singleton)

        with self.assertRaises(CircularDependencyError):
            self.container.resolve(ServiceA)

    def test_try_resolve_returns_none(self):
        """Test try_resolve returns None for unregistered service."""
        result = self.container.try_resolve(EmailService)
        self.assertIsNone(result)

    def test_try_resolve_returns_instance(self):
        """Test try_resolve returns instance for registered service."""
        self.container.register(EmailService)

        result = self.container.try_resolve(EmailService)
        self.assertIsInstance(result, EmailService)

    def test_is_registered(self):
        """Test is_registered method."""
        self.assertFalse(self.container.is_registered(EmailService))

        self.container.register(EmailService)

        self.assertTrue(self.container.is_registered(EmailService))

    def test_contains(self):
        """Test __contains__ method."""
        self.assertNotIn(EmailService, self.container)

        self.container.register(EmailService)

        self.assertIn(EmailService, self.container)

    def test_get_descriptor(self):
        """Test get_descriptor method."""
        self.container.register(EmailService, lifetime=Singleton)

        desc = self.container.get_descriptor(EmailService)
        self.assertIsNotNone(desc)
        self.assertEqual(desc.service_type, EmailService)
        self.assertEqual(desc.lifetime, Singleton)

    def test_get_descriptor_not_found(self):
        """Test get_descriptor returns None for unregistered."""
        desc = self.container.get_descriptor(EmailService)
        self.assertIsNone(desc)

    def test_clear(self):
        """Test clear method removes all registrations."""
        self.container.register(EmailService, lifetime=Singleton)
        self.container.resolve(EmailService)  # Create singleton

        self.container.clear()

        self.assertFalse(self.container.is_registered(EmailService))

    def test_chaining(self):
        """Test method chaining."""
        result = (
            self.container.register(EmailService, lifetime=Singleton)
            .register(DatabaseService, lifetime=Singleton)
        )

        self.assertIs(result, self.container)
        self.assertTrue(self.container.is_registered(EmailService))
        self.assertTrue(self.container.is_registered(DatabaseService))

    def test_repr(self):
        """Test container string representation."""
        self.container.register(EmailService)
        self.container.register(DatabaseService)

        repr_str = repr(self.container)
        self.assertIn("Container", repr_str)
        self.assertIn("2", repr_str)


# =============================================================================
# ScopedContainer Tests
# =============================================================================


class TestScopedContainer(TestCase):
    """Tests for ScopedContainer."""

    def setUp(self):
        """Set up test container."""
        self.container = Container()

    def test_context_manager(self):
        """Test scoped container as context manager."""
        self.container.register(EmailService, lifetime=Scoped)

        with self.container.create_scope() as scope:
            instance = scope.resolve(EmailService)
            self.assertIsInstance(instance, EmailService)

    def test_scope_cleanup(self):
        """Test scope cleans up after exit."""
        self.container.register(EmailService, lifetime=Scoped)

        with self.container.create_scope():
            pass

        # Outside scope, scoped should act as transient
        instance1 = self.container.resolve(EmailService)
        instance2 = self.container.resolve(EmailService)
        self.assertIsNot(instance1, instance2)


# =============================================================================
# Depends Tests
# =============================================================================


class TestDepends(TestCase):
    """Tests for Depends marker."""

    def setUp(self):
        """Set up test container."""
        self.container = Container()

    def test_depends_without_argument(self):
        """Test Depends() without argument."""
        depends = Depends()
        self.assertIsNone(depends.dependency)
        self.assertTrue(depends.use_cache)

    def test_depends_with_type(self):
        """Test Depends(Type)."""
        depends = Depends(EmailService)
        self.assertEqual(depends.dependency, EmailService)

    def test_depends_with_factory(self):
        """Test Depends(factory_function)."""

        def create_service():
            return EmailService()

        depends = Depends(create_service)
        self.assertEqual(depends.dependency, create_service)

    def test_depends_resolve_from_container(self):
        """Test Depends resolves from container."""
        self.container.register(EmailService, lifetime=Singleton)

        depends = Depends(EmailService)
        instance = depends.resolve(container=self.container)

        self.assertIsInstance(instance, EmailService)

    def test_depends_resolve_with_factory(self):
        """Test Depends resolves factory."""

        def create_config():
            return ConfigService(env="test")

        depends = Depends(create_config)
        instance = depends.resolve(container=self.container)

        self.assertEqual(instance.env, "test")

    def test_depends_resolve_uses_param_type(self):
        """Test Depends resolves from parameter type."""
        self.container.register(EmailService, lifetime=Singleton)

        depends = Depends()
        depends._param_type = EmailService

        instance = depends.resolve(container=self.container)
        self.assertIsInstance(instance, EmailService)

    def test_depends_repr(self):
        """Test Depends string representation."""
        depends = Depends(EmailService)
        self.assertIn("EmailService", repr(depends))

        depends_empty = Depends()
        self.assertEqual(repr(depends_empty), "Depends()")


# =============================================================================
# resolve_dependencies Tests
# =============================================================================


class TestResolveDependencies(TestCase):
    """Tests for resolve_dependencies function."""

    def setUp(self):
        """Set up test container."""
        self.test_container = Container()
        self.test_container.register(EmailService, lifetime=Singleton)

    def test_resolve_depends_marker(self):
        """Test resolving Depends markers."""

        def my_func(service: EmailService = Depends()):
            pass

        resolved = resolve_dependencies(
            my_func, container=self.test_container
        )

        self.assertIn("service", resolved)
        self.assertIsInstance(resolved["service"], EmailService)

    def test_resolve_skips_provided_kwargs(self):
        """Test skipping already-provided kwargs."""
        provided_service = EmailService()

        def my_func(service: EmailService = Depends()):
            pass

        resolved = resolve_dependencies(
            my_func,
            container=self.test_container,
            service=provided_service,
        )

        self.assertNotIn("service", resolved)

    def test_resolve_skips_self_cls(self):
        """Test skipping self and cls parameters."""

        class MyClass:
            def method(self, service: EmailService = Depends()):
                pass

        resolved = resolve_dependencies(
            MyClass.method, container=self.test_container
        )

        self.assertNotIn("self", resolved)

    def test_resolve_from_type_annotation(self):
        """Test resolving from type annotation when registered."""

        def my_func(service: EmailService):
            pass

        resolved = resolve_dependencies(
            my_func, container=self.test_container
        )

        self.assertIn("service", resolved)
        self.assertIsInstance(resolved["service"], EmailService)


# =============================================================================
# DependencyMarker Tests
# =============================================================================


class TestDependencyMarker(TestCase):
    """Tests for DependencyMarker base class."""

    def test_resolve_not_implemented(self):
        """Test base resolve raises NotImplementedError."""
        marker = DependencyMarker()

        with self.assertRaises(NotImplementedError):
            marker.resolve()


# =============================================================================
# Global Container Tests
# =============================================================================


class TestGlobalContainer(TestCase):
    """Tests for the global container instance."""

    def test_global_container_exists(self):
        """Test global container is available."""
        self.assertIsInstance(container, Container)

    def test_global_container_is_singleton(self):
        """Test global container is same instance."""
        from django_matt.di import container as c1
        from django_matt.di.container import container as c2

        self.assertIs(c1, c2)
