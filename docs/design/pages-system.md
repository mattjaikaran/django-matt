# Django Matt Pages - Design Document

> A modern, type-safe alternative to Inertia.js built on django-matt's codegen system.

**Status**: Design Phase
**Author**: Claude + Matt
**Date**: January 2026

---

## Executive Summary

`django_matt.pages` is a server-driven SPA system that addresses the limitations of Inertia.js while leveraging django-matt's existing codegen infrastructure for end-to-end type safety.

**Key differentiators:**
- End-to-end type safety (Django models → TypeScript props automatically)
- Hybrid mode (same endpoint serves JSON API or page response)
- Props delivered via `<script>` tag (not data attributes) for better performance
- Streaming SSR support for React 19+
- Schema-driven forms with automatic validation
- Real-time WebSocket integration
- Progressive enhancement (works without JS)

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Design Goals](#design-goals)
3. [Architecture Overview](#architecture-overview)
4. [Core Components](#core-components)
5. [API Design](#api-design)
6. [Hybrid Mode](#hybrid-mode)
7. [Type Safety Pipeline](#type-safety-pipeline)
8. [SSR & Streaming](#ssr-streaming)
9. [Form Handling](#form-handling)
10. [Real-time Integration](#real-time-integration)
11. [Error Handling](#error-handling)
12. [Client Adapters](#client-adapters)
13. [Progressive Enhancement](#progressive-enhancement)
14. [Migration from Inertia](#migration-from-inertia)
15. [Implementation Plan](#implementation-plan)

---

## Problem Statement

### Inertia.js Limitations

| Issue | Impact |
|-------|--------|
| **Props in `data-page` attribute** | Large JSON payloads cause slow parsing, DOM bloat |
| **No automatic type safety** | Manual TypeScript interfaces drift from backend |
| **`renderToString` only** | No React 19 Suspense/streaming support |
| **Page responses only** | Can't reuse endpoints for mobile API |
| **Manual component creation** | No code generation from models |
| **Basic form handling** | No schema-driven validation |
| **No real-time story** | Polling or separate WebSocket setup |
| **Maintenance concerns** | Slow development, stale PRs |

### Our Opportunity

We already have:
- **Codegen system** that generates React/Svelte/Solid components from Django models
- **Content negotiation** middleware for format switching
- **WebSocket support** for real-time updates
- **Pydantic schemas** for validation
- **Type generation** (TypeScript interfaces, Zod schemas)

We can unify these into a cohesive server-driven SPA system.

---

## Design Goals

### Must Have
1. **End-to-end type safety** - Zero manual TypeScript maintenance
2. **Hybrid API/Page mode** - Same endpoint serves both
3. **Performance** - Props in script tags, streaming support
4. **Developer experience** - Simple decorators, minimal boilerplate
5. **Framework agnostic** - React, Svelte, Solid, Vue support

### Should Have
1. **Progressive enhancement** - Server-rendered HTML fallback
2. **Real-time integration** - WebSocket-powered live updates
3. **Schema-driven forms** - Validation from Pydantic/Django models
4. **Error boundaries** - Graceful error handling

### Nice to Have
1. **Offline support** - Service worker integration
2. **Prefetching** - Intelligent link prefetching
3. **Transitions** - View transition API support

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Django Matt Pages                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Request    │───▶│  Middleware  │───▶│    View      │      │
│  │              │    │  (detect     │    │  (@page)     │      │
│  │ - Browser    │    │   mode)      │    │              │      │
│  │ - XHR+Header │    │              │    │              │      │
│  │ - API client │    │              │    │              │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                 │                │
│                                                 ▼                │
│                                          ┌──────────────┐       │
│                                          │ PageResponse │       │
│                                          │              │       │
│                                          │ - component  │       │
│                                          │ - props      │       │
│                                          │ - shared     │       │
│                                          │ - meta       │       │
│                                          └──────────────┘       │
│                                                 │                │
│                      ┌──────────────────────────┼────────┐      │
│                      │                          │        │      │
│                      ▼                          ▼        ▼      │
│               ┌────────────┐            ┌─────────┐ ┌─────────┐ │
│               │ Full HTML  │            │Page JSON│ │ API JSON│ │
│               │ (initial)  │            │ (XHR)   │ │ (mobile)│ │
│               └────────────┘            └─────────┘ └─────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

Response Modes:
─────────────────────────────────────────────────────────────────
1. Full HTML    - First visit, SEO crawlers, no-JS fallback
2. Page JSON    - SPA navigation (X-Page header)
3. API JSON     - Mobile apps, external clients (Accept: application/json)
```

---

## Core Components

### Module Structure

```
django_matt/
└── pages/
    ├── __init__.py          # Public API exports
    ├── decorators.py        # @page, @layout decorators
    ├── response.py          # PageResponse, PageData classes
    ├── middleware.py        # PageMiddleware (request mode detection)
    ├── context.py           # Shared data, flash messages
    ├── rendering.py         # HTML shell, script injection
    ├── streaming.py         # SSR streaming support
    ├── forms.py             # Schema-driven form helpers
    ├── errors.py            # Error pages, boundaries
    ├── assets.py            # Asset versioning, manifest
    ├── testing.py           # Test utilities
    └── adapters/
        ├── __init__.py
        ├── react.py         # React client adapter generator
        ├── svelte.py        # Svelte client adapter generator
        ├── solid.py         # Solid client adapter generator
        └── vue.py           # Vue client adapter generator
```

### Key Classes

```python
# response.py

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel

@dataclass
class PageData:
    """The page object sent to the client."""
    component: str                          # Component name
    props: Dict[str, Any]                   # Page props
    url: str                                # Current URL
    version: str                            # Asset version hash
    shared: Dict[str, Any] = field(default_factory=dict)  # Shared data
    errors: Dict[str, list] = field(default_factory=dict) # Validation errors
    flash: list = field(default_factory=list)             # Flash messages

    # Metadata
    title: Optional[str] = None             # Page title
    meta: Dict[str, str] = field(default_factory=dict)    # Meta tags

    # Advanced
    clear_history: bool = False             # Clear browser history
    encrypt_history: bool = False           # Encrypt history state
    preserve_scroll: bool = False           # Preserve scroll position

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSON response."""
        return {
            "component": self.component,
            "props": self.props,
            "url": self.url,
            "version": self.version,
            "shared": self.shared,
            "errors": self.errors,
            "flash": self.flash,
            "title": self.title,
            "meta": self.meta,
            "clearHistory": self.clear_history,
            "encryptHistory": self.encrypt_history,
            "preserveScroll": self.preserve_scroll,
        }


class PageResponse:
    """
    Response that renders as HTML (initial) or JSON (XHR).

    Usage:
        return PageResponse("UserList", props={"users": users})
    """

    def __init__(
        self,
        component: str,
        props: Dict[str, Any] = None,
        *,
        shared: Dict[str, Any] = None,
        title: str = None,
        meta: Dict[str, str] = None,
        status: int = 200,
        headers: Dict[str, str] = None,
    ):
        self.component = component
        self.props = props or {}
        self.shared = shared or {}
        self.title = title
        self.meta = meta or {}
        self.status = status
        self.headers = headers or {}

    def render(self, request) -> HttpResponse:
        """Render based on request mode."""
        mode = get_request_mode(request)

        if mode == RequestMode.PAGE_XHR:
            return self._render_page_json(request)
        elif mode == RequestMode.API:
            return self._render_api_json(request)
        else:
            return self._render_full_html(request)
```

---

## API Design

### The `@page` Decorator

```python
from django_matt.pages import page

# Simple usage - function returns props dict
@page("UserList")
def user_list(request):
    users = User.objects.all()
    return {"users": users}  # Serialized automatically

# With options
@page("UserDetail", title="User Profile")
def user_detail(request, id: int):
    user = get_object_or_404(User, id=id)
    return {"user": user}

# Async support
@page("Dashboard")
async def dashboard(request):
    stats = await get_dashboard_stats()
    return {"stats": stats}

# With Pydantic schema for type safety
class UserListProps(BaseModel):
    users: list[UserSchema]
    total_count: int

@page("UserList", props_schema=UserListProps)
def user_list(request):
    users = User.objects.all()
    return UserListProps(users=users, total_count=users.count())
```

### The `@layout` Decorator

```python
from django_matt.pages import layout, page

# Define a layout that wraps pages
@layout("DashboardLayout")
def dashboard_layout(request):
    """Shared data for all dashboard pages."""
    return {
        "user": request.user,
        "notifications": get_notifications(request.user),
        "nav_items": get_nav_items(request.user),
    }

# Pages use the layout
@page("Dashboard", layout=dashboard_layout)
def dashboard(request):
    return {"stats": get_stats()}

@page("Settings", layout=dashboard_layout)
def settings(request):
    return {"preferences": get_preferences(request.user)}
```

### Explicit PageResponse

```python
from django_matt.pages import PageResponse, redirect_page

def user_create(request):
    if request.method == "POST":
        form = UserForm(request.POST)
        if form.is_valid():
            user = form.save()
            return redirect_page("UserDetail", id=user.id)

        # Return with validation errors
        return PageResponse(
            "UserCreate",
            props={"form_data": request.POST},
            errors=form.errors,
            status=422,
        )

    return PageResponse("UserCreate")

# Redirect helper
def logout(request):
    auth_logout(request)
    return redirect_page("Login", flash="You have been logged out")
```

### Class-Based Views

```python
from django_matt.pages import PageView, PageViewSet

class UserDetailView(PageView):
    component = "UserDetail"

    def get_props(self, request, id: int):
        user = get_object_or_404(User, id=id)
        return {"user": user}

    def get_title(self, request, id: int):
        user = get_object_or_404(User, id=id)
        return f"{user.name} - Profile"


# Full CRUD ViewSet
class UserViewSet(PageViewSet):
    model = User
    components = {
        "list": "UserList",
        "detail": "UserDetail",
        "create": "UserCreate",
        "edit": "UserEdit",
    }
    # Components auto-generated if not specified!
```

---

## Hybrid Mode

### Same Endpoint, Multiple Formats

The killer feature: one endpoint serves pages AND API.

```python
from django_matt.pages import page
from django_matt.core import api

@api.get("/users")
@page("UserList")
def user_list(request):
    """
    This endpoint serves THREE formats:

    1. Browser visit → Full HTML with React/Svelte component
    2. X-Page: true header → Page JSON for SPA navigation
    3. Accept: application/json → Pure JSON API for mobile
    """
    users = User.objects.all()
    return {"users": users}
```

### Request Mode Detection

```python
# middleware.py

from enum import Enum

class RequestMode(Enum):
    FULL_HTML = "full_html"      # Initial browser visit
    PAGE_XHR = "page_xhr"        # SPA navigation (X-Page header)
    API = "api"                  # JSON API (Accept: application/json)
    SSR = "ssr"                  # Server-side rendering request


def get_request_mode(request) -> RequestMode:
    """Determine how to respond based on request headers."""

    # Check for explicit API request
    accept = request.headers.get("Accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return RequestMode.API

    # Check for page XHR (SPA navigation)
    if request.headers.get("X-Page") == "true":
        return RequestMode.PAGE_XHR

    # Check for SSR request (from Node.js SSR server)
    if request.headers.get("X-SSR") == "true":
        return RequestMode.SSR

    # Default: full HTML
    return RequestMode.FULL_HTML
```

### Response Format Comparison

```python
# Same view, different responses:

# 1. FULL_HTML - Initial browser visit
"""
<!DOCTYPE html>
<html>
<head>
  <title>Users</title>
  <link rel="stylesheet" href="/static/app.css">
</head>
<body>
  <div id="app"></div>
  <script type="application/json" id="page-data">
    {"component":"UserList","props":{"users":[...]},"url":"/users"}
  </script>
  <script type="module" src="/static/app.js"></script>
</body>
</html>
"""

# 2. PAGE_XHR - SPA navigation (X-Page: true)
"""
{
  "component": "UserList",
  "props": {"users": [...]},
  "url": "/users",
  "version": "abc123",
  "shared": {"user": {...}},
  "title": "Users"
}
"""

# 3. API - Mobile/external (Accept: application/json)
"""
{
  "users": [
    {"id": 1, "email": "alice@example.com", "name": "Alice"},
    {"id": 2, "email": "bob@example.com", "name": "Bob"}
  ]
}
"""
```

---

## Type Safety Pipeline

### End-to-End Flow

```
Django Model          Pydantic Schema         TypeScript          Component
────────────────────────────────────────────────────────────────────────────

class User:           class UserSchema:       interface User {     interface Props {
  email: str    ───▶    email: str      ───▶    email: string  ───▶   users: User[]
  name: str             name: str               name: string        }
  created_at            created_at              createdAt: string
                                                                    function UserList(
                                                                      { users }: Props
                                                                    ) { ... }
```

### Generated Types

```python
# codegen automatically generates:

# 1. TypeScript interfaces (from Django models)
# generated/types/user.ts
"""
export interface User {
  id: number;
  email: string;
  name: string;
  createdAt: string;
}
"""

# 2. Page props interfaces (from @page decorator)
# generated/pages/UserList.props.ts
"""
export interface UserListProps {
  users: User[];
}
"""

# 3. Zod schemas for runtime validation
# generated/schemas/user.ts
"""
export const UserSchema = z.object({
  id: z.number(),
  email: z.string().email(),
  name: z.string(),
  createdAt: z.string(),
});

export const UserListPropsSchema = z.object({
  users: z.array(UserSchema),
});
"""
```

### View Type Checking

```python
# Optional: Pydantic schemas for view type safety

from django_matt.pages import page, PageProps
from myapp.schemas import UserSchema

class UserListProps(PageProps):
    users: list[UserSchema]
    total_count: int
    page: int = 1

@page("UserList", props=UserListProps)
def user_list(request):
    users = User.objects.all()[:20]
    # IDE knows this must return UserListProps-compatible dict
    return {
        "users": users,
        "total_count": User.objects.count(),
        "page": 1,
    }
```

---

## SSR & Streaming

### Streaming Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Django    │────▶│  Node SSR   │────▶│   Browser   │
│   (props)   │     │  (render)   │     │  (hydrate)  │
└─────────────┘     └─────────────┘     └─────────────┘
      │                    │                   │
      │   Props JSON       │   Streaming HTML  │
      │   ──────────▶      │   ─────────────▶  │
      │                    │                   │
      │                    │   Suspense chunks │
      │                    │   ─────────────▶  │
```

### Streaming Response

```python
# streaming.py

from django.http import StreamingHttpResponse

class StreamingPageResponse(StreamingHttpResponse):
    """
    Streams HTML with Suspense boundaries.

    Uses renderToReadableStream (React 19) or equivalent.
    """

    def __init__(self, component: str, props: dict, **kwargs):
        self.component = component
        self.props = props
        super().__init__(self._stream_content(), **kwargs)

    def _stream_content(self):
        # 1. Stream initial shell
        yield self._render_shell_start()

        # 2. Stream page data script
        yield self._render_page_data()

        # 3. Stream Suspense fallbacks (resolved by client)
        for chunk in self._stream_suspense_chunks():
            yield chunk

        # 4. Stream closing tags
        yield self._render_shell_end()
```

### SSR Server Integration

```python
# For full SSR, we can integrate with a Node.js process

# settings.py
PAGES_SSR = {
    "enabled": True,
    "server": "http://localhost:3001",  # Node SSR server
    "timeout": 5000,  # ms
    "fallback": "client",  # Fall back to client rendering on error
}

# The SSR server receives props and returns HTML
# django_matt provides a reference Node.js SSR server
```

---

## Form Handling

### Schema-Driven Forms

```python
# forms.py

from django_matt.pages import PageForm
from pydantic import BaseModel, EmailStr

class UserCreateInput(BaseModel):
    email: EmailStr
    name: str
    password: str

    class Config:
        # Generates Zod schema for client-side validation
        generate_zod = True

@page("UserCreate")
def user_create(request):
    if request.method == "POST":
        # Validates against Pydantic schema
        form = PageForm(UserCreateInput, request.POST)

        if form.is_valid():
            user = User.objects.create(**form.validated_data)
            return redirect_page("UserDetail", id=user.id)

        # Errors automatically match client-side Zod schema
        return PageResponse(
            "UserCreate",
            props={"values": form.data},
            errors=form.errors,  # {field: [messages]}
        )

    return PageResponse("UserCreate")
```

### Generated Form Component

```tsx
// Auto-generated form with validation
// generated/components/UserCreateForm.tsx

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { UserCreateInputSchema } from "../schemas/user";
import { usePage, usePageForm } from "@django-matt/react";

export function UserCreateForm() {
  const { errors, values } = usePage<UserCreateProps>();

  const form = useForm({
    resolver: zodResolver(UserCreateInputSchema),
    defaultValues: values,
    errors: errors,  // Server errors merged in
  });

  const submit = usePageForm();  // Handles submission + navigation

  return (
    <form onSubmit={form.handleSubmit(submit)}>
      <input {...form.register("email")} />
      {form.formState.errors.email && (
        <span>{form.formState.errors.email.message}</span>
      )}

      <input {...form.register("name")} />
      <input type="password" {...form.register("password")} />

      <button type="submit" disabled={form.formState.isSubmitting}>
        Create User
      </button>
    </form>
  );
}
```

---

## Real-time Integration

### WebSocket-Powered Live Updates

```python
# Integrate with django_matt.websockets

from django_matt.pages import page, live
from django_matt.websockets import broadcast

@page("Dashboard")
@live("dashboard:{user.id}")  # Subscribe to WebSocket channel
def dashboard(request):
    return {"stats": get_stats(request.user)}

# When data changes, push update
def on_stats_updated(user_id: int):
    stats = get_stats_for_user(user_id)
    broadcast(
        f"dashboard:{user_id}",
        {"type": "props_update", "props": {"stats": stats}}
    )
```

### Client-Side Live Updates

```tsx
// Auto-reconnecting WebSocket integration

import { usePage, useLiveUpdates } from "@django-matt/react";

function Dashboard() {
  const { stats } = usePage<DashboardProps>();

  // Automatically updates when server pushes new props
  useLiveUpdates();

  return <StatsDisplay stats={stats} />;
}
```

---

## Error Handling

### Error Pages

```python
# errors.py

from django_matt.pages import error_page

@error_page(404)
def not_found(request, exception):
    return {"message": "Page not found"}

@error_page(500)
def server_error(request):
    return {"message": "Something went wrong"}

@error_page(403)
def forbidden(request, exception):
    return {"message": "You don't have permission"}
```

### Error Boundaries

```tsx
// Client-side error boundary integration

import { PageErrorBoundary } from "@django-matt/react";

function App() {
  return (
    <PageErrorBoundary
      fallback={({ error, reset }) => (
        <div>
          <h1>Something went wrong</h1>
          <button onClick={reset}>Try again</button>
        </div>
      )}
    >
      <PageRenderer />
    </PageErrorBoundary>
  );
}
```

---

## Client Adapters

### React Adapter

```tsx
// @django-matt/react

import { createPageApp, usePage, usePageForm, Link } from "@django-matt/react";

// Initialize app
const app = createPageApp({
  // Component resolver
  resolve: (name) => import(`./pages/${name}.tsx`),

  // Layout wrapper
  layout: ({ children, shared }) => (
    <AppLayout user={shared.user}>
      {children}
    </AppLayout>
  ),
});

// Mount
app.mount(document.getElementById("app"));

// Hooks
function UserList() {
  const { users } = usePage<UserListProps>();
  const navigate = usePageNavigate();

  return (
    <div>
      {users.map(user => (
        <Link href={`/users/${user.id}`} key={user.id}>
          {user.name}
        </Link>
      ))}
    </div>
  );
}
```

### Svelte Adapter

```svelte
<!-- @django-matt/svelte -->
<script>
  import { page, Link } from "@django-matt/svelte";

  // Reactive page data
  $: ({ users } = $page.props);
</script>

{#each users as user}
  <Link href="/users/{user.id}">{user.name}</Link>
{/each}
```

### Solid Adapter

```tsx
// @django-matt/solid

import { usePage, Link } from "@django-matt/solid";

function UserList() {
  const page = usePage<UserListProps>();

  return (
    <For each={page().users}>
      {(user) => (
        <Link href={`/users/${user.id}`}>{user.name}</Link>
      )}
    </For>
  );
}
```

---

## Progressive Enhancement

### No-JS Fallback

```python
# When JavaScript is disabled, render full HTML

@page("UserList")
def user_list(request):
    users = User.objects.all()
    return {"users": users}

# Template for no-JS fallback
# templates/pages/UserList.html
"""
{% extends "base.html" %}
{% block content %}
<h1>Users</h1>
<ul>
  {% for user in props.users %}
    <li>
      <a href="{% url 'user_detail' user.id %}">
        {{ user.name }}
      </a>
    </li>
  {% endfor %}
</ul>
{% endblock %}
"""
```

### Configuration

```python
# settings.py

PAGES = {
    "progressive": True,  # Enable no-JS fallback
    "fallback_templates": "pages/",  # Template directory
}
```

---

## Migration from Inertia

### Compatibility Layer

```python
# For projects migrating from inertia-django

from django_matt.pages.compat import inertia

# Works like inertia-django
@inertia("UserList")
def user_list(request):
    return {"users": User.objects.all()}

# Gradually migrate to native API
from django_matt.pages import page

@page("UserList")
def user_list(request):
    return {"users": User.objects.all()}
```

### Header Compatibility

```python
# Support both X-Inertia and X-Page headers during migration

PAGES = {
    "legacy_headers": True,  # Accept X-Inertia header
}
```

---

## Implementation Plan

### Phase 1: Core Foundation
- [ ] `PageResponse` class
- [ ] `@page` decorator
- [ ] `PageMiddleware` (mode detection)
- [ ] HTML shell rendering
- [ ] Props serialization (script tag injection)
- [ ] Asset versioning

### Phase 2: Hybrid Mode
- [ ] Content negotiation integration
- [ ] API response mode
- [ ] Request mode detection
- [ ] Format-specific serialization

### Phase 3: Type Safety
- [ ] Props schema validation
- [ ] Codegen integration (generate props types)
- [ ] Zod schema generation for forms
- [ ] IDE support (type hints)

### Phase 4: Client Adapters
- [ ] React adapter (@django-matt/react)
- [ ] Svelte adapter (@django-matt/svelte)
- [ ] Solid adapter (@django-matt/solid)
- [ ] Vue adapter (@django-matt/vue)

### Phase 5: Advanced Features
- [ ] Streaming SSR support
- [ ] WebSocket live updates
- [ ] Form handling helpers
- [ ] Error boundaries
- [ ] Progressive enhancement

### Phase 6: Developer Experience
- [ ] CLI codegen command updates
- [ ] Hot reload integration
- [ ] DevTools browser extension
- [ ] Documentation

---

## Configuration Reference

```python
# settings.py

PAGES = {
    # Core
    "root_template": "pages/base.html",    # HTML shell template
    "root_element": "app",                  # Mount point ID

    # Assets
    "manifest": "static/manifest.json",     # Vite/webpack manifest
    "version": None,                        # Manual version (auto if None)

    # SSR
    "ssr": {
        "enabled": False,
        "server": "http://localhost:3001",
        "timeout": 5000,
    },

    # Hybrid mode
    "hybrid": {
        "enabled": True,                    # Enable API mode
        "api_header": "Accept",             # Header to check
    },

    # Progressive enhancement
    "progressive": {
        "enabled": False,
        "templates": "pages/fallback/",
    },

    # Real-time
    "live": {
        "enabled": False,
        "websocket_url": "/ws/pages/",
    },

    # Compatibility
    "legacy_headers": False,                # Support X-Inertia header
}
```

---

## Example Application

### Complete CRUD Example

```python
# views.py

from django_matt.pages import page, redirect_page, PageResponse
from django_matt.pages.forms import PageForm
from myapp.models import Post
from myapp.schemas import PostCreateInput, PostUpdateInput

@page("PostList", title="Blog Posts")
def post_list(request):
    posts = Post.objects.select_related("author").all()
    return {"posts": posts}

@page("PostDetail")
def post_detail(request, slug: str):
    post = get_object_or_404(Post, slug=slug)
    return {
        "post": post,
        "comments": post.comments.all(),
    }

@page("PostCreate", title="New Post")
def post_create(request):
    if request.method == "POST":
        form = PageForm(PostCreateInput, request.POST)
        if form.is_valid():
            post = Post.objects.create(
                author=request.user,
                **form.validated_data
            )
            return redirect_page("PostDetail", slug=post.slug)

        return PageResponse(
            "PostCreate",
            props={"values": form.data},
            errors=form.errors,
            status=422,
        )

    return PageResponse("PostCreate")

@page("PostEdit", title="Edit Post")
def post_edit(request, slug: str):
    post = get_object_or_404(Post, slug=slug, author=request.user)

    if request.method == "POST":
        form = PageForm(PostUpdateInput, request.POST)
        if form.is_valid():
            for key, value in form.validated_data.items():
                setattr(post, key, value)
            post.save()
            return redirect_page("PostDetail", slug=post.slug)

        return PageResponse(
            "PostEdit",
            props={"post": post, "values": form.data},
            errors=form.errors,
            status=422,
        )

    return PageResponse("PostEdit", props={"post": post})


def post_delete(request, slug: str):
    post = get_object_or_404(Post, slug=slug, author=request.user)

    if request.method == "DELETE":
        post.delete()
        return redirect_page("PostList", flash="Post deleted")

    return PageResponse("PostDelete", props={"post": post})
```

### URL Configuration

```python
# urls.py

from django.urls import path
from myapp import views

urlpatterns = [
    path("posts/", views.post_list, name="post_list"),
    path("posts/new/", views.post_create, name="post_create"),
    path("posts/<slug:slug>/", views.post_detail, name="post_detail"),
    path("posts/<slug:slug>/edit/", views.post_edit, name="post_edit"),
    path("posts/<slug:slug>/delete/", views.post_delete, name="post_delete"),
]
```

---

## Comparison Summary

| Feature | Inertia.js | django_matt.pages |
|---------|------------|-------------------|
| Props delivery | `data-page` attribute | `<script>` tag |
| Type safety | Manual | Auto-generated |
| Hybrid API mode | No | Yes |
| Streaming SSR | No | Yes |
| Form validation | Manual | Schema-driven |
| Real-time | Separate | Integrated |
| Codegen | No | Yes |
| Framework support | React, Vue, Svelte | React, Vue, Svelte, Solid |
| Progressive enhancement | Limited | Full |

---

## Open Questions

1. **Naming**: `django_matt.pages` vs `django_matt.spa` vs `django_matt.frontend`?
2. **Client packages**: Publish as `@django-matt/react` or bundle with main package?
3. **Vue support**: Include Vue adapter or focus on React/Svelte/Solid?
4. **SSR server**: Provide reference Node.js server or just document protocol?
5. **Prefetching**: Automatic link prefetching or opt-in?

---

## References

- [Inertia.js](https://inertiajs.com/)
- [Inertia.js Protocol](https://inertiajs.com/the-protocol)
- [inertia-django](https://inertiajs.github.io/inertia-django/)
- [Remix](https://remix.run/) - Similar server-first approach
- [Next.js App Router](https://nextjs.org/docs/app) - React Server Components
- [SvelteKit](https://kit.svelte.dev/) - Svelte's full-stack framework
