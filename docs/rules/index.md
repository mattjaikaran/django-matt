# Rules

Predicate-based composable authorization system. Build complex permission rules by combining simple boolean predicates with `&` (AND), `|` (OR), and `~` (NOT) operators.

## Quick Start

```python
from django_matt.rules import predicate

@predicate
def is_author(user, obj):
    return obj.author == user

@predicate
def is_editor(user, obj):
    return user.groups.filter(name="editors").exists()

# Compose predicates
can_edit = is_author | is_editor

# Test
can_edit.test(request.user, post)  # True/False
```

## Configuration

Register named rules for use with the permission backend:

```python
from django_matt.rules.permissions import add_rule

add_rule("posts.change", is_author | is_editor)
add_rule("posts.delete", is_author & is_admin)
add_rule("posts.publish", is_editor)
```

Enable the rules backend in Django settings:

```python
# settings.py
AUTHENTICATION_BACKENDS = [
    "django_matt.rules.backends.RulesBackend",
    "django.contrib.auth.backends.ModelBackend",
]
```

## Key Features

### Predicates

Predicates are lightweight callables that compose with boolean operators:

```python
from django_matt.rules import predicate

@predicate
def is_authenticated(user):
    return user.is_authenticated

@predicate
def is_staff(user):
    return user.is_staff

@predicate
def is_superuser(user):
    return user.is_superuser

@predicate
def is_owner(user, obj):
    return hasattr(obj, "owner") and obj.owner == user

# Compose with operators
can_view = is_authenticated
can_edit = is_owner | is_staff
can_delete = is_owner & is_staff
cannot_edit = ~can_edit  # NOT

# Evaluate
can_edit.test(user, post)  # True/False
can_edit(user, post)       # Shorthand for .test()
```

The `bind=True` parameter passes the predicate instance as the first argument (useful for per-request caching):

```python
@predicate(bind=True)
def has_permission(self, user, obj):
    if not hasattr(self, "_cache"):
        self._cache = {}
    if user.pk not in self._cache:
        self._cache[user.pk] = expensive_check(user)
    return self._cache[user.pk]
```

### Built-in Predicates

```python
from django_matt.rules.builtins import (
    is_authenticated,
    is_staff,
    is_superuser,
    is_active,
    is_group_member,
    always_allow,
    always_deny,
)

# Group membership
is_moderator = is_group_member("moderators")
can_moderate = is_authenticated & is_moderator
```

### Permission Registry

Register named rules and test them:

```python
from django_matt.rules.permissions import add_rule, remove_rule, test_rule, rule_exists

# Register
add_rule("posts.view", is_authenticated)
add_rule("posts.change", is_author | is_editor)
add_rule("posts.delete", is_author & is_staff)

# Test
test_rule("posts.change", user, post)  # True/False

# Check existence
rule_exists("posts.change")  # True

# Remove
remove_rule("posts.change")
```

### Decorators

**@permission_required** -- Check a named rule from the registry:

```python
from django_matt.rules.decorators import permission_required

@permission_required("posts.change")
def edit_post(request, pk):
    ...
# Raises PermissionDenied if rule fails
```

**@predicate_required** -- Check a predicate directly (no registry):

```python
from django_matt.rules.decorators import predicate_required

@predicate_required(is_owner | is_admin)
def delete_post(request, pk):
    ...
```

### Mixins

For class-based views:

```python
from django_matt.rules.mixins import PermissionRequiredMixin

class EditPostView(PermissionRequiredMixin, UpdateView):
    permission_required = "posts.change"
    model = Post

    def get_permission_object(self):
        return self.get_object()
```

### Authentication Backend

The `RulesBackend` integrates with Django's permission system:

```python
# settings.py
AUTHENTICATION_BACKENDS = [
    "django_matt.rules.backends.RulesBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Now user.has_perm() checks rules
user.has_perm("posts.change", post)  # Tests the registered rule
```

## Practical Example

A blog application with role-based permissions:

```python
from django_matt.rules import predicate
from django_matt.rules.builtins import is_authenticated, is_superuser
from django_matt.rules.permissions import add_rule

@predicate
def is_post_author(user, post):
    return post.author_id == user.pk

@predicate
def is_post_published(user, post):
    return post.status == "published"

@predicate
def is_in_same_org(user, post):
    return user.organization_id == post.organization_id

# Compose rules
can_view_post = is_post_published | is_post_author | is_superuser
can_edit_post = (is_post_author & is_in_same_org) | is_superuser
can_delete_post = is_post_author | is_superuser
can_publish_post = is_in_same_org & is_authenticated

# Register
add_rule("blog.view_post", can_view_post)
add_rule("blog.change_post", can_edit_post)
add_rule("blog.delete_post", can_delete_post)
add_rule("blog.publish_post", can_publish_post)
```

```python
# views.py
from django_matt.rules.decorators import permission_required

@permission_required("blog.change_post")
def edit_post(request, pk):
    post = get_object_or_404(Post, pk=pk)
    ...
```
