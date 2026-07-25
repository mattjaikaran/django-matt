"""
Tenant context middleware for multi-tenant applications.

Provides middleware to automatically resolve and set the current tenant
(organization) context for each request.
"""

from __future__ import annotations

import contextvars
from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse

if TYPE_CHECKING:
    from django_matt.multitenancy.models import Organization

# Thread-local storage for current tenant
_current_tenant: contextvars.ContextVar[Optional[Organization]] = contextvars.ContextVar(
    "current_tenant", default=None
)
_current_organization: contextvars.ContextVar[Optional[Organization]] = contextvars.ContextVar(
    "current_organization", default=None
)


def get_current_tenant() -> Optional[Organization]:
    """
    Get the current tenant (organization) from context.

    Returns:
        The current Organization or None if not set
    """
    return _current_tenant.get()


def get_current_organization() -> Optional[Organization]:
    """
    Alias for get_current_tenant().

    Returns:
        The current Organization or None if not set
    """
    return _current_organization.get()


def set_current_tenant(organization: Optional[Organization]) -> None:
    """
    Set the current tenant (organization) in context.

    Args:
        organization: The Organization to set as current tenant
    """
    _current_tenant.set(organization)
    _current_organization.set(organization)


def clear_current_tenant() -> None:
    """Clear the current tenant from context."""
    _current_tenant.set(None)
    _current_organization.set(None)


class TenantMiddleware:
    """
    Synchronous middleware to resolve tenant from request.

    Tenant can be resolved from:
    1. Request header (X-Organization-ID or X-Organization-Slug)
    2. URL path parameter (org_slug in URL)
    3. Session (if user has a default organization)
    4. User's first organization (fallback)

    Usage:
        MIDDLEWARE = [
            ...
            'django_matt.multitenancy.TenantMiddleware',
        ]

    Settings:
        TENANT_HEADER_ID: Header name for organization ID (default: 'X-Organization-ID')
        TENANT_HEADER_SLUG: Header name for organization slug (default: 'X-Organization-Slug')
        TENANT_URL_KWARG: URL kwarg for organization slug (default: 'org_slug')
        TENANT_SESSION_KEY: Session key for storing organization ID (default: 'current_organization_id')
        TENANT_REQUIRED_PATHS: List of path prefixes that require tenant context (default: [])
        TENANT_EXEMPT_PATHS: List of path prefixes exempt from tenant requirement (default: ['/auth/', '/health/'])
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

        # Load settings
        self.header_id = getattr(settings, "TENANT_HEADER_ID", "X-Organization-ID")
        self.header_slug = getattr(settings, "TENANT_HEADER_SLUG", "X-Organization-Slug")
        self.url_kwarg = getattr(settings, "TENANT_URL_KWARG", "org_slug")
        self.session_key = getattr(settings, "TENANT_SESSION_KEY", "current_organization_id")
        self.required_paths = getattr(settings, "TENANT_REQUIRED_PATHS", [])
        self.exempt_paths = getattr(settings, "TENANT_EXEMPT_PATHS", ["/auth/", "/health/"])

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Import here to avoid circular imports
        from django_matt.multitenancy.models import Membership, Organization

        organization = None

        # Try to resolve tenant from various sources
        organization = self._resolve_from_header(request, Organization)

        if not organization:
            organization = self._resolve_from_url(request, Organization)

        if not organization:
            organization = self._resolve_from_session(request, Organization)

        if not organization and hasattr(request, "user") and request.user.is_authenticated:
            organization = self._resolve_from_user(request, Organization, Membership)

        # Set the tenant context
        set_current_tenant(organization)
        request.organization = organization
        request.tenant = organization

        # Check if tenant is required for this path
        if self._requires_tenant(request.path) and not organization:
            return JsonResponse(
                {"error": "Organization context required"},
                status=400,
            )

        try:
            response = self.get_response(request)
        finally:
            # Clear tenant context after request
            clear_current_tenant()

        return response

    def _resolve_from_header(self, request: HttpRequest, Organization) -> Optional[Organization]:
        """Resolve tenant from request headers."""
        from django.core.exceptions import ValidationError

        # Try ID header first
        org_id = request.headers.get(self.header_id)
        if org_id:
            try:
                return Organization.objects.filter(id=org_id, is_active=True).first()
            except (ValueError, ValidationError, Organization.DoesNotExist):
                pass

        # Try slug header
        org_slug = request.headers.get(self.header_slug)
        if org_slug:
            return Organization.objects.filter(slug=org_slug, is_active=True).first()

        return None

    def _resolve_from_url(self, request: HttpRequest, Organization) -> Optional[Organization]:
        """Resolve tenant from URL parameters."""
        if hasattr(request, "resolver_match") and request.resolver_match:
            org_slug = request.resolver_match.kwargs.get(self.url_kwarg)
            if org_slug:
                return Organization.objects.filter(slug=org_slug, is_active=True).first()
        return None

    def _resolve_from_session(self, request: HttpRequest, Organization) -> Optional[Organization]:
        """Resolve tenant from session."""
        if hasattr(request, "session"):
            org_id = request.session.get(self.session_key)
            if org_id:
                try:
                    return Organization.objects.filter(id=org_id, is_active=True).first()
                except (ValueError, Organization.DoesNotExist):
                    pass
        return None

    def _resolve_from_user(
        self, request: HttpRequest, Organization, Membership
    ) -> Optional[Organization]:
        """Resolve tenant from user's memberships."""
        membership = (
            Membership.objects.filter(user=request.user, organization__is_active=True)
            .select_related("organization")
            .first()
        )
        if membership:
            return membership.organization
        return None

    def _requires_tenant(self, path: str) -> bool:
        """Check if the request path requires tenant context."""
        # Check exempt paths first
        for exempt_path in self.exempt_paths:
            if path.startswith(exempt_path):
                return False

        # Check required paths
        for required_path in self.required_paths:
            if path.startswith(required_path):
                return True

        return False


class TenantMiddlewareAsync:
    """
    Async middleware to resolve tenant from request.

    Same functionality as TenantMiddleware but for async views.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response

        # Load settings
        self.header_id = getattr(settings, "TENANT_HEADER_ID", "X-Organization-ID")
        self.header_slug = getattr(settings, "TENANT_HEADER_SLUG", "X-Organization-Slug")
        self.url_kwarg = getattr(settings, "TENANT_URL_KWARG", "org_slug")
        self.session_key = getattr(settings, "TENANT_SESSION_KEY", "current_organization_id")
        self.required_paths = getattr(settings, "TENANT_REQUIRED_PATHS", [])
        self.exempt_paths = getattr(settings, "TENANT_EXEMPT_PATHS", ["/auth/", "/health/"])

    async def __call__(self, request: HttpRequest) -> HttpResponse:
        from django_matt.multitenancy.models import Membership, Organization

        organization = None

        # Resolve from header (sync operation on headers)
        organization = await self._resolve_from_header(request, Organization)

        if not organization:
            organization = await self._resolve_from_url(request, Organization)

        if not organization:
            organization = await self._resolve_from_session(request, Organization)

        if not organization and hasattr(request, "user"):
            # request.user.is_authenticated is a simple boolean property on a Django user
            # object — not a lazy attribute requiring DB access — safe to access directly.
            if request.user.is_authenticated:
                organization = await self._resolve_from_user(request, Organization, Membership)

        # Set the tenant context
        set_current_tenant(organization)
        request.organization = organization
        request.tenant = organization

        # Check if tenant is required
        if self._requires_tenant(request.path) and not organization:
            return JsonResponse(
                {"error": "Organization context required"},
                status=400,
            )

        try:
            response = await self.get_response(request)
        finally:
            clear_current_tenant()

        return response

    async def _resolve_from_header(
        self, request: HttpRequest, Organization
    ) -> Optional[Organization]:
        """Resolve tenant from request headers."""
        from django.core.exceptions import ValidationError

        org_id = request.headers.get(self.header_id)
        if org_id:
            try:
                return await Organization.objects.filter(id=org_id, is_active=True).afirst()
            except (ValueError, ValidationError, Organization.DoesNotExist):
                pass

        org_slug = request.headers.get(self.header_slug)
        if org_slug:
            return await Organization.objects.filter(slug=org_slug, is_active=True).afirst()

        return None

    async def _resolve_from_url(self, request: HttpRequest, Organization) -> Optional[Organization]:
        """Resolve tenant from URL parameters."""
        if hasattr(request, "resolver_match") and request.resolver_match:
            org_slug = request.resolver_match.kwargs.get(self.url_kwarg)
            if org_slug:
                return await Organization.objects.filter(slug=org_slug, is_active=True).afirst()
        return None

    async def _resolve_from_session(
        self, request: HttpRequest, Organization
    ) -> Optional[Organization]:
        """Resolve tenant from session."""
        if hasattr(request, "session"):
            org_id = request.session.get(self.session_key)
            if org_id:
                try:
                    return await Organization.objects.filter(id=org_id, is_active=True).afirst()
                except (ValueError, Organization.DoesNotExist):
                    pass
        return None

    async def _resolve_from_user(
        self, request: HttpRequest, Organization, Membership
    ) -> Optional[Organization]:
        """Resolve tenant from user's memberships."""
        membership = await (
            Membership.objects.filter(user=request.user, organization__is_active=True)
            .select_related("organization")
            .afirst()
        )
        return membership.organization if membership else None

    def _requires_tenant(self, path: str) -> bool:
        """Check if the request path requires tenant context."""
        for exempt_path in self.exempt_paths:
            if path.startswith(exempt_path):
                return False

        for required_path in self.required_paths:
            if path.startswith(required_path):
                return True

        return False


class TenantRequiredMixin:
    """
    Mixin for views/controllers that require tenant context.

    Usage:
        class MyController(TenantRequiredMixin, APIController):
            def get_queryset(self):
                return MyModel.objects.filter(organization=self.request.organization)
    """

    def get_organization(self) -> Organization:
        """Get the current organization from request."""
        org = getattr(self.request, "organization", None)
        if not org:
            raise ValueError("No organization context available")
        return org

    def get_tenant(self) -> Organization:
        """Alias for get_organization()."""
        return self.get_organization()
