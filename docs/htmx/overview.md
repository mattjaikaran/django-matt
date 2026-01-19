# HTMX Integration

Django Matt provides comprehensive HTMX integration for building dynamic, modern web applications with minimal JavaScript.

## Overview

```mermaid
flowchart LR
    subgraph "Request"
        HX[HTMX Request<br/>HX-Request header]
        STD[Standard Request<br/>Full page]
    end

    subgraph "Middleware"
        MW[HtmxMiddleware<br/>request.htmx]
    end

    subgraph "View"
        DEC[Decorators<br/>@htmx_view]
        RESP[Response Helpers<br/>HtmxResponse]
    end

    subgraph "Response"
        PART[Partial HTML<br/>Component only]
        FULL[Full Page<br/>Complete HTML]
    end

    HX --> MW --> DEC --> PART
    STD --> MW --> DEC --> FULL
    DEC --> RESP
```

## Quick Start

### Setup

```python
# settings.py
MIDDLEWARE = [
    ...
    'django_matt.htmx.HtmxMiddleware',
]

TEMPLATES = [{
    ...
    'OPTIONS': {
        'context_processors': [
            ...
            'django_matt.htmx.htmx_context_processor',
        ],
    },
}]
```

### Basic Usage

```python
from django_matt.htmx import htmx_view, HtmxResponse

@htmx_view(
    template="users/list.html",
    partial_template="users/partials/list.html"
)
def user_list(request):
    users = User.objects.all()
    return {"users": users}
    # HTMX request -> renders partial
    # Normal request -> renders full template
```

```html
<!-- templates/users/list.html -->
{% load htmx_tags %}
<html>
<head>{% htmx_script %}</head>
<body {% htmx_csrf %}>
    <div id="user-list">
        {% include "users/partials/list.html" %}
    </div>
</body>
</html>

<!-- templates/users/partials/list.html -->
{% for user in users %}
    <div class="user" hx-get="/users/{{ user.id }}" hx-swap="outerHTML">
        {{ user.name }}
    </div>
{% endfor %}
```

## Request Detection

### Using Middleware

```python
def my_view(request):
    if request.htmx:
        # HTMX request
        return render(request, "partial.html", context)
    else:
        # Normal request
        return render(request, "full.html", context)
```

### Request Properties

```python
from django_matt.htmx import (
    is_htmx_request,
    is_htmx_boosted,
    get_htmx_target,
    get_htmx_trigger,
)

def my_view(request):
    if is_htmx_request(request):
        target = get_htmx_target(request)     # HX-Target header
        trigger = get_htmx_trigger(request)   # HX-Trigger header
        print(f"Updating {target} triggered by {trigger}")
```

### HtmxDetails Object

```python
def my_view(request):
    htmx = request.htmx  # HtmxDetails object

    htmx.request          # True if HTMX request
    htmx.boosted          # True if hx-boost request
    htmx.target           # Target element ID
    htmx.trigger          # Trigger element ID
    htmx.trigger_name     # Trigger element name
    htmx.prompt           # hx-prompt value
    htmx.current_url      # HX-Current-URL header
    htmx.history_restore  # True if history restore
```

## Decorators

### @htmx_view

Automatic template switching:

```python
from django_matt.htmx import htmx_view

@htmx_view(
    template="products/list.html",
    partial_template="products/partials/list.html",
)
def product_list(request):
    return {"products": Product.objects.all()}
```

### @htmx_partial

Mark view as partial-only:

```python
from django_matt.htmx import htmx_partial

@htmx_partial
def search_results(request):
    query = request.GET.get("q", "")
    results = Product.objects.filter(name__icontains=query)
    return render(request, "products/partials/results.html", {"results": results})
```

### @htmx_only

Restrict view to HTMX requests only:

```python
from django_matt.htmx import htmx_only

@htmx_only
def delete_item(request, id):
    Item.objects.get(id=id).delete()
    return HttpResponse("")  # 200 OK, removes element
```

### @vary_on_htmx

Add Vary header for caching:

```python
from django_matt.htmx import vary_on_htmx

@vary_on_htmx
def cached_view(request):
    # Different cache for HTMX vs normal requests
    return render(request, "template.html")
```

## Response Helpers

### HtmxResponse

Chainable response builder:

```python
from django_matt.htmx import HtmxResponse

def update_user(request, user_id):
    user = User.objects.get(id=user_id)
    user.name = request.POST.get("name")
    user.save()

    return (
        HtmxResponse(render_to_string("users/partials/user.html", {"user": user}))
        .trigger("userUpdated", {"id": user.id})        # Trigger client event
        .push_url(f"/users/{user.id}/")                 # Update browser URL
        .retarget("#user-card")                         # Change target element
        .reswap("outerHTML")                            # Change swap method
    )
```

### Response Methods

```python
response = HtmxResponse(content)

# URL manipulation
response.push_url("/new-url")              # Update URL (add to history)
response.replace_url("/new-url")           # Replace URL (no history)
response.refresh()                         # Full page refresh

# Targeting
response.retarget("#element-id")           # Change target
response.reswap("innerHTML")               # Change swap method
response.reselect(".selector")             # Select specific content

# Events
response.trigger("eventName")              # Trigger event after settle
response.trigger("event", {"key": "val"})  # With data
response.trigger_after_swap("event")       # Trigger after swap
response.trigger_after_settle("event")     # Trigger after settle
```

### HtmxTemplateResponse

```python
from django_matt.htmx import HtmxTemplateResponse

def my_view(request):
    return (
        HtmxTemplateResponse(request, "partial.html", {"data": data})
        .trigger("dataUpdated")
    )
```

### Special Responses

```python
from django_matt.htmx import (
    HtmxRedirectResponse,
    HtmxRefreshResponse,
    StopPolling,
)

# Client-side redirect
return HtmxRedirectResponse("/new-page/")

# Full page refresh
return HtmxRefreshResponse()

# Stop polling (for hx-trigger="every 2s")
return StopPolling()
```

## Components

### Infinite Scroll

```python
from django_matt.htmx import InfiniteScrollConfig, render_infinite_scroll_page

config = InfiniteScrollConfig(
    items_per_page=20,
    trigger_selector=".load-more",
    content_selector="#item-list",
)

def item_list(request):
    page = int(request.GET.get("page", 1))
    items = Item.objects.all()

    return render_infinite_scroll_page(
        request,
        items,
        config,
        page=page,
        partial_template="items/partials/list.html",
        full_template="items/list.html",
    )
```

```html
<!-- items/partials/list.html -->
{% for item in items %}
    <div class="item">{{ item.name }}</div>
{% endfor %}
{% if has_more %}
    <div class="load-more"
         hx-get="?page={{ next_page }}"
         hx-trigger="revealed"
         hx-swap="outerHTML">
        Loading...
    </div>
{% endif %}
```

### Search with Debounce

```python
from django_matt.htmx import SearchConfig, render_search_results

config = SearchConfig(
    debounce_ms=300,
    min_length=2,
    results_selector="#results",
)

def search(request):
    query = request.GET.get("q", "")
    results = Product.objects.filter(name__icontains=query)[:20]

    return render_search_results(
        request,
        results,
        config,
        template="products/partials/search_results.html",
    )
```

```html
<input type="search"
       name="q"
       hx-get="/search/"
       hx-trigger="input changed delay:300ms"
       hx-target="#results">
<div id="results"></div>
```

### Modals

```python
from django_matt.htmx import ModalConfig, open_modal, close_modal

config = ModalConfig(
    container_id="modal-container",
    backdrop=True,
    keyboard_close=True,
)

def show_edit_modal(request, id):
    item = Item.objects.get(id=id)
    return open_modal(
        request,
        "items/partials/edit_modal.html",
        {"item": item},
        config,
    )

def save_and_close(request, id):
    # Save logic...
    return close_modal(config)
```

### Toasts

```python
from django_matt.htmx import ToastConfig, show_toast, add_toast_oob

config = ToastConfig(
    container_id="toast-container",
    duration_ms=5000,
    position="top-right",
)

def save_item(request):
    # Save logic...
    response = render(request, "items/partials/item.html", {"item": item})
    return add_toast_oob(
        response,
        "Item saved successfully!",
        level="success",
        config=config,
    )
```

### Out-of-Band Swaps

Update multiple elements:

```python
from django_matt.htmx import oob_swap, OobBuilder

def update_dashboard(request):
    # Build response with multiple OOB swaps
    builder = OobBuilder()
    builder.swap("#stats", render_to_string("partials/stats.html", stats))
    builder.swap("#chart", render_to_string("partials/chart.html", chart_data))
    builder.swap("#notifications", render_to_string("partials/notifications.html", notifs))

    return builder.response()

# Or use oob_swap helper
def save_item(request):
    content = render_to_string("items/partials/item.html", {"item": item})
    sidebar = render_to_string("partials/sidebar.html", {"count": new_count})

    return oob_swap(content, [
        ("#sidebar-count", sidebar, "innerHTML"),
    ])
```

## Template Tags

```html
{% load htmx_tags %}

<!-- Include HTMX script -->
{% htmx_script %}
{% htmx_script version="1.9.10" %}

<!-- CSRF setup for HTMX -->
{% htmx_csrf %}

<!-- Generate hx-* attributes -->
<button {% htmx_attrs get="/items/" target="#list" swap="innerHTML" %}>
    Load Items
</button>

<!-- Conditional based on HTMX request -->
{% if htmx %}
    <!-- Partial content -->
{% else %}
    <!-- Full page -->
{% endif %}
```

## Patterns

### Active Search

```html
<form hx-get="/search/" hx-target="#results" hx-trigger="submit, input changed delay:300ms from:find input">
    <input type="search" name="q" placeholder="Search...">
    <button type="submit">Search</button>
</form>
<div id="results">
    {% include "partials/search_results.html" %}
</div>
```

### Click to Edit

```html
<!-- Display mode -->
<div id="user-{{ user.id }}" hx-get="/users/{{ user.id }}/edit/" hx-swap="outerHTML">
    <span>{{ user.name }}</span>
    <button>Edit</button>
</div>

<!-- Edit mode (returned by /users/{id}/edit/) -->
<form id="user-{{ user.id }}"
      hx-put="/users/{{ user.id }}/"
      hx-swap="outerHTML">
    <input name="name" value="{{ user.name }}">
    <button type="submit">Save</button>
    <button hx-get="/users/{{ user.id }}/" hx-swap="outerHTML">Cancel</button>
</form>
```

### Lazy Loading

```html
<div hx-get="/expensive-content/"
     hx-trigger="revealed"
     hx-swap="outerHTML">
    <div class="skeleton">Loading...</div>
</div>
```

### Polling with Stop

```python
def status(request, task_id):
    task = Task.objects.get(id=task_id)

    if task.is_complete:
        return StopPolling()  # 286 status code

    return render(request, "tasks/partials/status.html", {"task": task})
```

```html
<div hx-get="/tasks/{{ task.id }}/status/"
     hx-trigger="every 2s"
     hx-swap="outerHTML">
    {{ task.status }}
</div>
```

## Best Practices

1. **Use partial templates** - Separate full pages from HTMX partials
2. **Leverage OOB swaps** - Update multiple elements in one request
3. **Debounce inputs** - Use `delay:300ms` for search/filter inputs
4. **Progressive enhancement** - Ensure pages work without JavaScript
5. **Use middleware** - Always add HtmxMiddleware for `request.htmx`
6. **Cache wisely** - Use `@vary_on_htmx` for cached views
7. **Handle errors** - Return appropriate error partials for HTMX requests
