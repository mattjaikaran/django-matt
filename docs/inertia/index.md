# Inertia.js Integration

Server-side Inertia.js adapter for Django. Build single-page apps with React, Vue, or Svelte without a separate API layer. Supports partial reloads, lazy props, deferred props, SSR, shared data, and asset versioning.

## Quick Start

```python
# settings.py
MIDDLEWARE = [
    ...
    "django_matt.inertia.InertiaMiddleware",
]

# views.py
from django_matt.inertia import inertia

def dashboard(request):
    return inertia(request, "Dashboard/Index", {
        "stats": get_stats(),
        "user": {"name": request.user.get_full_name()},
    })
```

## Configuration

```python
# settings.py
MATT_INERTIA = {
    "ROOT_TEMPLATE": "base.html",       # Django template wrapping the app
    "VERSION": None,                      # Asset version (string, callable, or None)
    "SSR_ENABLED": False,                 # Enable server-side rendering
    "SSR_URL": "http://localhost:13714",  # SSR server URL
}
```

The root template should include the Inertia app div:

```html
<!-- base.html -->
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    {% for tag in ssr_head %}{{ tag|safe }}{% endfor %}
</head>
<body>
    {% if ssr_body %}
        <div id="app" data-page='{{ page }}'>{{ ssr_body|safe }}</div>
    {% else %}
        <div id="app" data-page='{{ page }}'></div>
    {% endif %}
    <script src="/static/js/app.js"></script>
</body>
</html>
```

## Key Features

### inertia() Response Function

The core response function handles both Inertia XHR requests and full page loads:

```python
from django_matt.inertia import inertia

def users_list(request):
    return inertia(request, "Users/Index", {
        "users": list(User.objects.values("id", "name", "email")),
        "filters": request.GET.dict(),
    })
```

- **Inertia request** (has `X-Inertia` header): returns `InertiaResponse` (JSON with `X-Inertia: true` header)
- **Full page load**: renders the root template with page data embedded in `data-page`

### Prop Wrappers

Control when and how props are loaded:

```python
from django_matt.inertia import inertia, lazy, defer, merge

def dashboard(request):
    return inertia(request, "Dashboard", {
        # Always included on full page load
        "stats": get_quick_stats(),

        # Only included when explicitly requested in partial reload
        "detailed_report": lazy(lambda: generate_report()),

        # Loaded after initial page render (client fetches separately)
        "notifications": defer(lambda: get_notifications(), group="sidebar"),

        # Deep-merged with existing client data on partial reload
        "filters": merge({"status": "active"}),
    })
```

| Wrapper | Behavior |
|---------|----------|
| `lazy(callable)` | Only evaluated when specifically requested via `X-Inertia-Partial-Data` |
| `defer(callable, group)` | Skipped on initial load; client fetches per group after render |
| `merge(data)` | Deep-merged with existing client-side data |

### InertiaMiddleware

Handles the Inertia protocol:

```python
# Sync
MIDDLEWARE = ["django_matt.inertia.InertiaMiddleware"]

# Async (ASGI)
MIDDLEWARE = ["django_matt.inertia.AsyncInertiaMiddleware"]
```

The middleware:
1. Detects `X-Inertia` header and annotates `request._inertia = True`
2. On version mismatch (GET requests): responds with 409 + `X-Inertia-Location`
3. Converts 302 redirects to 303 for PUT/PATCH/DELETE (Inertia spec requirement)

### Shared Data

Share data across all Inertia responses:

```python
from django_matt.inertia.share import share

# In middleware or view
share(request, "auth", {
    "user": {"name": request.user.get_full_name()} if request.user.is_authenticated else None,
})
share(request, "flash", request.session.pop("flash", {}))
```

Shared data is merged into every Inertia response's props.

### Class-Based Views

```python
from django_matt.inertia.views import InertiaView

class DashboardView(InertiaView):
    component = "Dashboard/Index"

    def get_props(self, request, **kwargs):
        return {
            "stats": get_stats(),
            "user": request.user.email,
        }

# urls.py
urlpatterns = [
    path("dashboard/", DashboardView.as_view()),
]
```

### Function View Decorator

```python
from django_matt.inertia.views import inertia_view

@inertia_view("Dashboard/Index")
def dashboard(request):
    return {"stats": get_stats(), "user": request.user.email}

# Return None for empty props
@inertia_view("About")
def about(request):
    return None

# Return HttpResponse directly for redirects
@inertia_view("Settings")
def settings(request):
    if not request.user.is_authenticated:
        return redirect("/login")
    return {"email": request.user.email}
```

### SSR (Server-Side Rendering)

Enable SSR for SEO and initial load performance:

```python
# settings.py
MATT_INERTIA = {
    "SSR_ENABLED": True,
    "SSR_URL": "http://localhost:13714",
}
```

The SSR module sends the page data to a Node.js SSR server and includes the rendered HTML in the initial response. Falls back to client-side rendering on SSR failure.

### Testing

```python
from django_matt.inertia.testing import InertiaTestCase

class TestDashboard(InertiaTestCase):
    def test_dashboard_returns_inertia_response(self):
        response = self.inertia_get("/dashboard/")
        self.assert_component(response, "Dashboard/Index")
        self.assert_has_prop(response, "stats")
```

## Practical Example

A CRUD resource with Inertia:

```python
from django_matt.inertia import inertia, lazy
from django_matt.inertia.views import inertia_view

@inertia_view("Users/Index")
def users_index(request):
    users = list(User.objects.values("id", "name", "email", "created_at"))
    return {
        "users": users,
        "filters": request.GET.dict(),
    }

@inertia_view("Users/Show")
def users_show(request, pk):
    user = User.objects.filter(pk=pk).values().first()
    return {
        "user": user,
        "activity": lazy(lambda: get_user_activity(pk)),
    }

def users_store(request):
    form = UserForm(request.POST)
    if form.is_valid():
        form.save()
        return redirect("/users")
    # Inertia handles validation errors via shared data
    return inertia(request, "Users/Create", {"errors": form.errors})

def users_destroy(request, pk):
    User.objects.filter(pk=pk).delete()
    return redirect("/users")
```
