"""
Django Matt Rules — predicate-based composable boolean authorization.

Provides django-rules style predicates that compose with ``&``, ``|``,
and ``~`` operators, a global permission registry, Django auth backend,
CBV mixins, view decorators, and integration with django-matt controllers.

Quick start::

    from django_matt.rules import predicate, add_perm, test_rule
    from django_matt.rules.builtins import is_authenticated, is_owner


    @predicate
    def is_author(user, obj):
        return obj.author_id == user.pk


    add_perm("posts.edit", is_author | is_owner)
    add_perm("posts.delete", is_author)

    # Test
    test_rule("posts.edit", request.user, post)

    # Use with django-matt controllers
    from django_matt.rules.integration import PredicatePermission


    class PostController(APIController):
        permission_classes = [PredicatePermission(is_author | is_owner)]
"""

from django_matt.rules.backends import RulesBackend
from django_matt.rules.builtins import (
    has_perm as has_perm_predicate,
)
from django_matt.rules.builtins import (
    is_active,
    is_authenticated,
    is_group_member,
    is_owner,
    is_staff,
    is_superuser,
)
from django_matt.rules.decorators import permission_required, predicate_required
from django_matt.rules.integration import PredicatePermission
from django_matt.rules.mixins import ObjectPermissionMixin, PermissionRequiredMixin
from django_matt.rules.permissions import (
    add_perm,
    clear,
    has_perm,
    perm_exists,
    remove_perm,
    test_rule,
)
from django_matt.rules.predicates import (
    Predicate,
    always_deny,
    always_false,
    always_true,
    predicate,
)

__all__ = [
    # Core
    "Predicate",
    "predicate",
    "always_true",
    "always_false",
    "always_deny",
    # Built-in predicates
    "is_authenticated",
    "is_superuser",
    "is_staff",
    "is_active",
    "is_owner",
    "is_group_member",
    "has_perm_predicate",
    # Registry
    "add_perm",
    "remove_perm",
    "has_perm",
    "perm_exists",
    "test_rule",
    "clear",
    # Decorators
    "permission_required",
    "predicate_required",
    # Mixins
    "PermissionRequiredMixin",
    "ObjectPermissionMixin",
    # Backend
    "RulesBackend",
    # Integration
    "PredicatePermission",
]
