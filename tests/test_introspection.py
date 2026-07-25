from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

from django.test import RequestFactory

import pytest

from django_matt.introspection.checks import (
    auto_register,
    check_cache,
    check_database,
    check_email,
    check_storage,
)
from django_matt.introspection.middleware import HealthCheckMiddleware
from django_matt.introspection.registry import (
    ComponentInfo,
    ComponentStatus,
    HealthResult,
    InfraRegistry,
)
from django_matt.introspection.report import InfraReport, generate_report

# =============================================================================
# Registry Tests
# =============================================================================


class TestComponentInfo:
    def test_defaults(self):
        info = ComponentInfo(name="db", component_type="database")
        assert info.status == ComponentStatus.UNKNOWN
        assert info.version is None
        assert info.details == {}
        assert info.critical is True

    def test_all_fields(self):
        info = ComponentInfo(
            name="redis",
            component_type="cache",
            status=ComponentStatus.HEALTHY,
            version="7.0",
            latency_ms=1.5,
            details={"connections": 10},
            critical=False,
        )
        assert info.name == "redis"
        assert info.version == "7.0"
        assert info.latency_ms == 1.5
        assert info.critical is False


class TestInfraRegistry:
    def setup_method(self):
        self.registry = InfraRegistry()

    def test_register_and_list(self):
        async def noop():
            return ComponentInfo(name="test", component_type="test", status=ComponentStatus.HEALTHY)

        self.registry.register("test", "test", noop)
        assert "test" in self.registry.registered

    def test_unregister(self):
        async def noop():
            return ComponentInfo(name="test", component_type="test", status=ComponentStatus.HEALTHY)

        self.registry.register("test", "test", noop)
        self.registry.unregister("test")
        assert "test" not in self.registry.registered

    def test_unregister_nonexistent(self):
        self.registry.unregister("nope")  # should not raise

    def test_clear(self):
        async def noop():
            return ComponentInfo(name="a", component_type="t", status=ComponentStatus.HEALTHY)

        self.registry.register("a", "t", noop)
        self.registry.register("b", "t", noop)
        self.registry.clear()
        assert self.registry.registered == []

    @pytest.mark.asyncio
    async def test_health_check_all_healthy(self):
        async def healthy():
            return ComponentInfo(
                name="svc", component_type="service", status=ComponentStatus.HEALTHY
            )

        self.registry.register("svc1", "service", healthy)
        self.registry.register("svc2", "service", healthy)
        result = await self.registry.health_check()
        assert result.status == ComponentStatus.HEALTHY
        assert len(result.components) == 2
        assert all(c.latency_ms is not None for c in result.components.values())

    @pytest.mark.asyncio
    async def test_health_check_critical_unhealthy(self):
        async def unhealthy():
            return ComponentInfo(
                name="db", component_type="database", status=ComponentStatus.UNHEALTHY
            )

        self.registry.register("db", "database", unhealthy, critical=True)
        result = await self.registry.health_check()
        assert result.status == ComponentStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_health_check_noncritical_unhealthy(self):
        async def healthy():
            return ComponentInfo(
                name="db", component_type="database", status=ComponentStatus.HEALTHY
            )

        async def unhealthy():
            return ComponentInfo(
                name="email", component_type="email", status=ComponentStatus.UNHEALTHY
            )

        self.registry.register("db", "database", healthy, critical=True)
        self.registry.register("email", "email", unhealthy, critical=False)
        result = await self.registry.health_check()
        # non-critical unhealthy does not make overall unhealthy
        assert result.status == ComponentStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_health_check_degraded(self):
        async def degraded():
            return ComponentInfo(
                name="cache", component_type="cache", status=ComponentStatus.DEGRADED
            )

        self.registry.register("cache", "cache", degraded)
        result = await self.registry.health_check()
        assert result.status == ComponentStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_health_check_exception_in_check(self):
        async def exploding():
            raise RuntimeError("boom")

        self.registry.register("bad", "service", exploding, critical=False)
        result = await self.registry.health_check()
        assert result.components["bad"].status == ComponentStatus.UNHEALTHY
        assert "boom" in result.components["bad"].error

    @pytest.mark.asyncio
    async def test_health_check_empty_registry(self):
        result = await self.registry.health_check()
        assert result.status == ComponentStatus.HEALTHY
        assert result.components == {}


# =============================================================================
# Health Check Tests
# =============================================================================


@pytest.mark.django_db
class TestCheckDatabase:
    @pytest.mark.asyncio
    async def test_database_healthy(self):
        info = await check_database()
        assert info.status == ComponentStatus.HEALTHY
        assert info.name == "database"
        assert "backend" in info.details


class TestCheckCache:
    @pytest.mark.asyncio
    async def test_cache_healthy(self):
        info = await check_cache()
        assert info.status == ComponentStatus.HEALTHY
        assert info.name == "cache"


class TestCheckEmail:
    @pytest.mark.asyncio
    async def test_email_locmem(self):
        info = await check_email()
        assert info.status == ComponentStatus.HEALTHY
        assert info.details.get("note") == "non-production backend"


class TestCheckStorage:
    @pytest.mark.asyncio
    async def test_storage_healthy(self):
        info = await check_storage()
        assert info.status == ComponentStatus.HEALTHY
        assert "backend" in info.details


# =============================================================================
# Auto-register
# =============================================================================


class TestAutoRegister:
    def test_auto_register(self):
        reg = InfraRegistry()
        auto_register(reg)
        assert "database" in reg.registered
        assert "cache" in reg.registered
        assert "storage" in reg.registered
        assert "email" in reg.registered


# =============================================================================
# Report Tests
# =============================================================================


class TestInfraReport:
    def test_report_model(self):
        report = InfraReport(
            timestamp=time.time(),
            framework_version="0.1.0",
            python_version="3.12.0",
            django_version="5.2",
            platform="linux",
        )
        assert report.framework_version == "0.1.0"
        assert report.enabled_modules == []

    @pytest.mark.asyncio
    @pytest.mark.django_db
    async def test_generate_report(self):
        report = await generate_report()
        assert report.framework_version
        assert report.python_version
        assert report.django_version
        assert "django_matt" in report.installed_apps


# =============================================================================
# Middleware Tests
# =============================================================================


class TestHealthCheckMiddleware:
    def setup_method(self):
        self.factory = RequestFactory()
        self.get_response = MagicMock(return_value=MagicMock(status_code=200))
        self.middleware = HealthCheckMiddleware(self.get_response)

    def test_short_circuits_health(self):
        request = self.factory.get("/health/")
        response = self.middleware(request)
        assert response.status_code == 200
        self.get_response.assert_not_called()

    def test_short_circuits_live(self):
        request = self.factory.get("/health/live/")
        response = self.middleware(request)
        assert response.status_code == 200
        import orjson

        data = orjson.loads(response.content)
        assert data["alive"] is True

    def test_passes_through_other_paths(self):
        request = self.factory.get("/api/users/")
        self.middleware(request)
        self.get_response.assert_called_once_with(request)

    def test_passes_through_health_subpaths(self):
        request = self.factory.get("/health/detailed/")
        self.middleware(request)
        self.get_response.assert_called_once_with(request)


# =============================================================================
# Endpoint Tests
# =============================================================================


class TestEndpoints:
    @pytest.mark.asyncio
    async def test_health_view_ok(self):
        from django_matt.introspection.endpoints import health_view

        reg = InfraRegistry()

        async def healthy():
            return ComponentInfo(
                name="db", component_type="database", status=ComponentStatus.HEALTHY
            )

        reg.register("db", "database", healthy)

        with patch("django_matt.introspection.endpoints.registry", reg):
            request = RequestFactory().get("/health/")
            response = await health_view(request)
            assert response.status_code == 200
            import orjson

            data = orjson.loads(response.content)
            assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_view_unhealthy(self):
        from django_matt.introspection.endpoints import health_view

        reg = InfraRegistry()

        async def bad():
            return ComponentInfo(
                name="db", component_type="database", status=ComponentStatus.UNHEALTHY
            )

        reg.register("db", "database", bad, critical=True)

        with patch("django_matt.introspection.endpoints.registry", reg):
            request = RequestFactory().get("/health/")
            response = await health_view(request)
            assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_health_detailed_requires_auth(self):
        from django_matt.introspection.endpoints import health_detailed_view

        request = RequestFactory().get("/health/detailed/")
        request.user = MagicMock(is_authenticated=False)
        response = await health_detailed_view(request)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_health_detailed_authenticated(self):
        from django_matt.introspection.endpoints import health_detailed_view

        reg = InfraRegistry()

        async def healthy():
            return ComponentInfo(
                name="db", component_type="database", status=ComponentStatus.HEALTHY
            )

        reg.register("db", "database", healthy)

        with patch("django_matt.introspection.endpoints.registry", reg):
            request = RequestFactory().get("/health/detailed/")
            request.user = MagicMock(is_authenticated=True)
            response = await health_detailed_view(request)
            assert response.status_code == 200
            import orjson

            data = orjson.loads(response.content)
            assert "components" in data
            assert "db" in data["components"]

    @pytest.mark.asyncio
    async def test_health_ready_all_critical_ok(self):
        from django_matt.introspection.endpoints import health_ready_view

        reg = InfraRegistry()

        async def healthy():
            return ComponentInfo(
                name="db", component_type="database", status=ComponentStatus.HEALTHY
            )

        reg.register("db", "database", healthy, critical=True)

        with patch("django_matt.introspection.endpoints.registry", reg):
            request = RequestFactory().get("/health/ready/")
            response = await health_ready_view(request)
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_ready_critical_down(self):
        from django_matt.introspection.endpoints import health_ready_view

        reg = InfraRegistry()

        async def bad():
            return ComponentInfo(
                name="db", component_type="database", status=ComponentStatus.UNHEALTHY
            )

        reg.register("db", "database", bad, critical=True)

        with patch("django_matt.introspection.endpoints.registry", reg):
            request = RequestFactory().get("/health/ready/")
            response = await health_ready_view(request)
            assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_health_live(self):
        from django_matt.introspection.endpoints import health_live_view

        request = RequestFactory().get("/health/live/")
        response = await health_live_view(request)
        assert response.status_code == 200
        import orjson

        data = orjson.loads(response.content)
        assert data["alive"] is True

    @pytest.mark.asyncio
    @pytest.mark.django_db
    async def test_info_view(self):
        from django_matt.introspection.endpoints import info_view

        request = RequestFactory().get("/_info/")
        response = await info_view(request)
        assert response.status_code == 200
        import orjson

        data = orjson.loads(response.content)
        assert "framework_version" in data
        assert "python_version" in data

    def test_get_health_urls(self):
        from django_matt.introspection.endpoints import get_health_urls

        urls = get_health_urls()
        assert len(urls) == 5
        names = [u.name for u in urls]
        assert "introspection-health" in names
        assert "introspection-health-detailed" in names
        assert "introspection-health-ready" in names
        assert "introspection-health-live" in names
        assert "introspection-info" in names

    def test_get_health_urls_custom_prefix(self):
        from django_matt.introspection.endpoints import get_health_urls

        urls = get_health_urls(prefix="status")
        patterns = [u.pattern.describe() for u in urls]
        assert any("status" in p for p in patterns)
