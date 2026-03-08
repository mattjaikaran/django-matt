"""
Decorators for multi-tenancy access control.

Provides decorators to enforce tenant context and permissions in views/controllers.
All decorators detect async vs sync views via inspect.iscoroutinefunction and wrap
accordingly, matching the pattern used in auth/decorators/jwt.py.
"""

import inspect
from collections.abc import Callable
from functools import wraps

from django.http import HttpRequest, JsonResponse

from django_matt.multitenancy.middleware import get_current_tenant
from django_matt.multitenancy.models import MembershipRole


def _get_organization(request: HttpRequest):
    """Helper to get organization from request or context."""
    organization = get_current_tenant()
    if not organization:
        organization = getattr(request, "organization", None)
    return organization


def requires_organization(func: Callable) -> Callable:
    """
    Decorator that requires an organization context to be set.

    Supports both async and sync view functions.

    Usage:
        @requires_organization
        async def my_view(request):
            org = request.organization
            ...

        @requires_organization
        def my_view(request):
            org = request.organization
            ...
    """
    if inspect.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(self_or_request, *args, **kwargs):
            # Handle both function-based (request first) and method-based (self first) views
            request = self_or_request if isinstance(self_or_request, HttpRequest) else (
                args[0] if args and isinstance(args[0], HttpRequest) else self_or_request
            )
            organization = _get_organization(request)
            if not organization:
                return JsonResponse(
                    {"error": "Organization context required"},
                    status=400,
                )
            return await func(self_or_request, *args, **kwargs)
        return async_wrapper
    else:
        @wraps(func)
        def sync_wrapper(self_or_request, *args, **kwargs):
            request = self_or_request if isinstance(self_or_request, HttpRequest) else (
                args[0] if args and isinstance(args[0], HttpRequest) else self_or_request
            )
            organization = _get_organization(request)
            if not organization:
                return JsonResponse(
                    {"error": "Organization context required"},
                    status=400,
                )
            return func(self_or_request, *args, **kwargs)
        return sync_wrapper


def requires_org_membership(func: Callable) -> Callable:
    """
    Decorator that requires the user to be a member of the current organization.

    Supports both async and sync view functions.

    Usage:
        @requires_org_membership
        async def my_view(request):
            # User is guaranteed to be a member of request.organization
            ...
    """
    if inspect.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(self_or_request, *args, **kwargs):
            request = self_or_request if isinstance(self_or_request, HttpRequest) else (
                args[0] if args and isinstance(args[0], HttpRequest) else self_or_request
            )
            if not request.user.is_authenticated:
                return JsonResponse(
                    {"error": "Authentication required"},
                    status=401,
                )

            organization = _get_organization(request)
            if not organization:
                return JsonResponse(
                    {"error": "Organization context required"},
                    status=400,
                )

            from django_matt.multitenancy.models import Membership

            is_member = await Membership.objects.filter(
                organization=organization,
                user=request.user,
            ).aexists()

            if not is_member:
                return JsonResponse(
                    {"error": "You are not a member of this organization"},
                    status=403,
                )

            return await func(self_or_request, *args, **kwargs)
        return async_wrapper
    else:
        @wraps(func)
        def sync_wrapper(self_or_request, *args, **kwargs):
            request = self_or_request if isinstance(self_or_request, HttpRequest) else (
                args[0] if args and isinstance(args[0], HttpRequest) else self_or_request
            )
            if not request.user.is_authenticated:
                return JsonResponse(
                    {"error": "Authentication required"},
                    status=401,
                )

            organization = _get_organization(request)
            if not organization:
                return JsonResponse(
                    {"error": "Organization context required"},
                    status=400,
                )

            if not organization.is_member(request.user):
                return JsonResponse(
                    {"error": "You are not a member of this organization"},
                    status=403,
                )

            return func(self_or_request, *args, **kwargs)
        return sync_wrapper


def requires_org_role(
    roles: str | list[str],
    any_role: bool = True,
) -> Callable:
    """
    Decorator that requires the user to have specific role(s) in the organization.

    Supports both async and sync view functions.

    Args:
        roles: Required role(s) - can be a single role or list
        any_role: If True, user must have ANY of the roles. If False, user must have ALL.

    Usage:
        @requires_org_role("admin")
        async def admin_only_view(request):
            ...

        @requires_org_role(["admin", "owner"])
        def admin_or_owner_view(request):
            ...
    """
    if isinstance(roles, str):
        roles = [roles]

    def decorator(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(self_or_request, *args, **kwargs):
                request = self_or_request if isinstance(self_or_request, HttpRequest) else (
                    args[0] if args and isinstance(args[0], HttpRequest) else self_or_request
                )
                if not request.user.is_authenticated:
                    return JsonResponse(
                        {"error": "Authentication required"},
                        status=401,
                    )

                organization = _get_organization(request)
                if not organization:
                    return JsonResponse(
                        {"error": "Organization context required"},
                        status=400,
                    )

                from django_matt.multitenancy.models import Membership

                membership = await Membership.objects.filter(
                    organization=organization,
                    user=request.user,
                ).afirst()

                if not membership:
                    return JsonResponse(
                        {"error": "You are not a member of this organization"},
                        status=403,
                    )

                user_role = membership.role
                has_role = user_role in roles

                if not has_role:
                    return JsonResponse(
                        {"error": f"Required role(s): {', '.join(roles)}"},
                        status=403,
                    )

                # Attach membership to request for convenience
                request.membership = membership

                return await func(self_or_request, *args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(self_or_request, *args, **kwargs):
                request = self_or_request if isinstance(self_or_request, HttpRequest) else (
                    args[0] if args and isinstance(args[0], HttpRequest) else self_or_request
                )
                if not request.user.is_authenticated:
                    return JsonResponse(
                        {"error": "Authentication required"},
                        status=401,
                    )

                organization = _get_organization(request)
                if not organization:
                    return JsonResponse(
                        {"error": "Organization context required"},
                        status=400,
                    )

                from django_matt.multitenancy.models import Membership

                membership = Membership.objects.filter(
                    organization=organization,
                    user=request.user,
                ).first()

                if not membership:
                    return JsonResponse(
                        {"error": "You are not a member of this organization"},
                        status=403,
                    )

                user_role = membership.role
                has_role = user_role in roles

                if not has_role:
                    return JsonResponse(
                        {"error": f"Required role(s): {', '.join(roles)}"},
                        status=403,
                    )

                # Attach membership to request for convenience
                request.membership = membership

                return func(self_or_request, *args, **kwargs)
            return sync_wrapper

    return decorator


def requires_org_admin(func: Callable) -> Callable:
    """
    Decorator that requires the user to be an admin or owner of the organization.

    Supports both async and sync view functions.

    Usage:
        @requires_org_admin
        async def admin_view(request):
            ...
    """
    return requires_org_role([MembershipRole.ADMIN.value, MembershipRole.OWNER.value])(func)


def requires_org_owner(func: Callable) -> Callable:
    """
    Decorator that requires the user to be an owner of the organization.

    Supports both async and sync view functions.

    Usage:
        @requires_org_owner
        async def owner_view(request):
            ...
    """
    return requires_org_role([MembershipRole.OWNER.value])(func)


def requires_min_org_role(min_role: str) -> Callable:
    """
    Decorator that requires the user to have at least a minimum role level.

    Role hierarchy: owner > admin > member > viewer

    Supports both async and sync view functions.

    Args:
        min_role: Minimum required role

    Usage:
        @requires_min_org_role("member")
        async def member_or_above_view(request):
            # Allows member, admin, or owner
            ...
    """

    def decorator(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(self_or_request, *args, **kwargs):
                request = self_or_request if isinstance(self_or_request, HttpRequest) else (
                    args[0] if args and isinstance(args[0], HttpRequest) else self_or_request
                )
                if not request.user.is_authenticated:
                    return JsonResponse(
                        {"error": "Authentication required"},
                        status=401,
                    )

                organization = _get_organization(request)
                if not organization:
                    return JsonResponse(
                        {"error": "Organization context required"},
                        status=400,
                    )

                from django_matt.multitenancy.models import Membership

                membership = await Membership.objects.filter(
                    organization=organization,
                    user=request.user,
                ).afirst()

                if not membership:
                    return JsonResponse(
                        {"error": "You are not a member of this organization"},
                        status=403,
                    )

                user_priority = MembershipRole.get_priority(membership.role)
                required_priority = MembershipRole.get_priority(min_role)

                if user_priority < required_priority:
                    return JsonResponse(
                        {"error": f"Minimum role required: {min_role}"},
                        status=403,
                    )

                request.membership = membership

                return await func(self_or_request, *args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(self_or_request, *args, **kwargs):
                request = self_or_request if isinstance(self_or_request, HttpRequest) else (
                    args[0] if args and isinstance(args[0], HttpRequest) else self_or_request
                )
                if not request.user.is_authenticated:
                    return JsonResponse(
                        {"error": "Authentication required"},
                        status=401,
                    )

                organization = _get_organization(request)
                if not organization:
                    return JsonResponse(
                        {"error": "Organization context required"},
                        status=400,
                    )

                from django_matt.multitenancy.models import Membership

                membership = Membership.objects.filter(
                    organization=organization,
                    user=request.user,
                ).first()

                if not membership:
                    return JsonResponse(
                        {"error": "You are not a member of this organization"},
                        status=403,
                    )

                user_priority = MembershipRole.get_priority(membership.role)
                required_priority = MembershipRole.get_priority(min_role)

                if user_priority < required_priority:
                    return JsonResponse(
                        {"error": f"Minimum role required: {min_role}"},
                        status=403,
                    )

                request.membership = membership

                return func(self_or_request, *args, **kwargs)
            return sync_wrapper

    return decorator


def requires_team_membership(team_param: str = "team_id") -> Callable:
    """
    Decorator that requires the user to be a member of the specified team.

    Supports both async and sync view functions.

    Args:
        team_param: Name of the URL parameter containing the team ID

    Usage:
        @requires_team_membership("team_id")
        async def team_view(request, team_id):
            # User is guaranteed to be a member of the team
            ...
    """

    def decorator(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(self_or_request, *args, **kwargs):
                request = self_or_request if isinstance(self_or_request, HttpRequest) else (
                    args[0] if args and isinstance(args[0], HttpRequest) else self_or_request
                )
                if not request.user.is_authenticated:
                    return JsonResponse(
                        {"error": "Authentication required"},
                        status=401,
                    )

                team_id = kwargs.get(team_param)
                if not team_id:
                    return JsonResponse(
                        {"error": "Team ID required"},
                        status=400,
                    )

                from django_matt.multitenancy.models import Team, TeamMembership

                team = await Team.objects.filter(id=team_id).afirst()
                if not team:
                    return JsonResponse(
                        {"error": "Team not found"},
                        status=404,
                    )

                team_membership = await TeamMembership.objects.filter(
                    team=team,
                    user=request.user,
                ).afirst()

                if not team_membership:
                    return JsonResponse(
                        {"error": "You are not a member of this team"},
                        status=403,
                    )

                request.team = team
                request.team_membership = team_membership

                return await func(self_or_request, *args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(self_or_request, *args, **kwargs):
                request = self_or_request if isinstance(self_or_request, HttpRequest) else (
                    args[0] if args and isinstance(args[0], HttpRequest) else self_or_request
                )
                if not request.user.is_authenticated:
                    return JsonResponse(
                        {"error": "Authentication required"},
                        status=401,
                    )

                team_id = kwargs.get(team_param)
                if not team_id:
                    return JsonResponse(
                        {"error": "Team ID required"},
                        status=400,
                    )

                from django_matt.multitenancy.models import Team, TeamMembership

                team = Team.objects.filter(id=team_id).first()
                if not team:
                    return JsonResponse(
                        {"error": "Team not found"},
                        status=404,
                    )

                team_membership = TeamMembership.objects.filter(
                    team=team,
                    user=request.user,
                ).first()

                if not team_membership:
                    return JsonResponse(
                        {"error": "You are not a member of this team"},
                        status=403,
                    )

                request.team = team
                request.team_membership = team_membership

                return func(self_or_request, *args, **kwargs)
            return sync_wrapper

    return decorator
