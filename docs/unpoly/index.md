# Unpoly Integration

Server-side helpers for Unpoly -- progressive enhancement framework for server-rendered HTML. Middleware for request detection, decorators for fragment targeting, layer control, and validation handling.

## Quick Start

```python
# settings.py
MIDDLEWARE = [
    ...
    "django_matt.unpoly.UnpolyMiddleware",
]

# views.py
def my_view(request):
    if request.up:
        # Unpoly request -- render only the targeted fragment
        return render(request, "partials/content.html", context)
    # Full page request
    return render(request, "full_page.html", context)
```

## Configuration

```python
# settings.py (optional)
MATT_UNPOLY = {
    "VERSION": None,  # Asset version for cache busting
}
```

## Key Features

### UnpolyMiddleware

Parses `X-Up-*` request headers and annotates `request.up` with an `UnpolyDetails` object:

```python
MIDDLEWARE = ["django_matt.unpoly.UnpolyMiddleware"]
```

The middleware:
1. Parses `X-Up-Target`, `X-Up-Mode`, `X-Up-Validate`, and other Unpoly headers
2. Sets `X-Up-Location` and `X-Up-Method` on responses
3. Handles version mismatch detection
4. Preserves Unpoly headers through redirect chains
5. Adds `Vary: X-Up-Target` for correct caching

Access Unpoly details in views:

```python
def my_view(request):
    if request.up:                          # Truthy if Unpoly request
        target = request.up.target          # CSS selector being targeted
        mode = request.up.mode              # Layer mode (root, modal, drawer, etc.)
        is_validating = request.up.is_validating  # True during field validation
```

### Decorators

**@up_target** -- Set default target selector:

```python
from django_matt.unpoly import up_target

@up_target(".main-content")
def my_view(request):
    return render(request, "page.html")
```

**@up_layer** -- Set the layer mode:

```python
from django_matt.unpoly import up_layer

@up_layer("modal")
def edit_user(request, user_id):
    return render(request, "users/edit.html")
```

**@up_fail_target** -- Set the failure target selector:

```python
from django_matt.unpoly import up_fail_target

@up_fail_target(".error-container")
def create_item(request):
    ...
```

**@up_only** -- Restrict to Unpoly requests only (returns 422 otherwise):

```python
from django_matt.unpoly import up_only

@up_only
def partial_widget(request):
    return render(request, "partials/widget.html")
```

**@up_validate** -- Restrict to Unpoly validation requests:

```python
from django_matt.unpoly import up_validate

@up_validate
def validate_email(request):
    email = request.POST.get("email", "")
    if User.objects.filter(email=email).exists():
        return HttpResponse('<span class="error">Taken</span>')
    return HttpResponse('<span class="ok">Available</span>')
```

**@vary_on_unpoly** -- Add `Vary: X-Up-Target` header for cache separation:

```python
from django_matt.unpoly import vary_on_unpoly

@vary_on_unpoly
def my_view(request):
    if request.up:
        return render(request, "partial.html")
    return render(request, "full.html")
```

## Practical Example

A CRUD interface with Unpoly modals and inline validation:

```python
from django_matt.unpoly import up_target, up_layer, up_validate, vary_on_unpoly

@vary_on_unpoly
@up_target(".user-list")
def users_index(request):
    users = User.objects.all()
    if request.up:
        return render(request, "users/_list.html", {"users": users})
    return render(request, "users/index.html", {"users": users})

@up_layer("modal")
def users_create(request):
    if request.method == "POST":
        form = UserForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("/users/")
    else:
        form = UserForm()
    return render(request, "users/form.html", {"form": form})

@up_validate
def validate_username(request):
    username = request.POST.get("username", "")
    if len(username) < 3:
        return HttpResponse('<span class="error">Too short</span>')
    if User.objects.filter(username=username).exists():
        return HttpResponse('<span class="error">Already taken</span>')
    return HttpResponse('<span class="ok">Available</span>')
```

```html
<!-- users/form.html -->
<form up-submit up-layer="parent" up-target=".user-list">
    <input name="username" up-validate="/validate-username/" />
    <button type="submit">Create User</button>
</form>
```
