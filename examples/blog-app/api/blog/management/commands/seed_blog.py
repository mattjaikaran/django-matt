"""Seed the database with realistic sample blog content."""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

TAGS = [
    "python",
    "django",
    "web-development",
    "api",
    "tutorial",
    "open-source",
    "react",
    "typescript",
]
CATEGORIES = [
    {"name": "Engineering", "description": "Technical deep-dives and architecture posts"},
    {"name": "Tutorials", "description": "Step-by-step guides"},
    {"name": "Announcements", "description": "Product and library news"},
    {"name": "Career", "description": "Dev career advice"},
]

POSTS = [
    {
        "title": "Building a Full-Stack Blog with Django-Matt and React",
        "content": """# Building a Full-Stack Blog with Django-Matt and React

django-matt makes it remarkably easy to stand up a production-quality API. In this post we'll walk through building this very blog backend from scratch.

## Prerequisites

- Python 3.12+
- Node.js 20+ / Bun
- PostgreSQL 16+

## Setting up the project

First, install django-matt:

```bash
uv add django-matt
```

Then scaffold your API controller:

```python
class PostController(APIController):
    prefix = "/posts"
    tags = ["Posts"]

    async def list_posts(self) -> list[PostListResponse]:
        return [PostListResponse.model_validate(p)
                async for p in Post.objects.filter(status="published")]
```

It really is that simple. The framework handles OpenAPI generation, async execution, and JWT auth automatically.

## Full-text search

PostgreSQL full-text search is built in:

```python
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

qs = Post.objects.annotate(
    rank=SearchRank(SearchVector("title", "content"), SearchQuery(q))
).filter(rank__gt=0.01).order_by("-rank")
```

## Next steps

Head over to the [django-matt docs](https://docs.django-matt.dev) to learn about JWT auth, pagination, file uploads, and more.
""",
        "excerpt": "A step-by-step walkthrough of building a full-stack blog with django-matt and React+Vite.",
        "category": "Tutorials",
        "tags": ["django", "python", "react", "tutorial"],
        "featured": True,
    },
    {
        "title": "Why We Built Django-Matt",
        "content": """# Why We Built Django-Matt

The Django REST ecosystem has a fragmentation problem. A typical Django API project pulls in:

- `djangorestframework` for views and serializers
- `djangorestframework-simplejwt` for JWT auth
- `django-ninja` for async + Pydantic schemas
- `dj-stripe` for billing
- `django-channels` for WebSockets
- `celery` + `django-celery-beat` for tasks

Each package has its own configuration, its own conventions, its own quirks. Django-matt consolidates all of this into one cohesive library with a single, coherent API.

## Key design decisions

**Async-first** — Every controller method is async by default. Sync is the fallback.

**Pydantic v2** — Schemas are real Pydantic models, not DRF serializers. You get validation, OpenAPI generation, and TypeScript codegen for free.

**Zero magic** — There's no metaclass wizardry or hidden ORM monkey-patching. What you write is what runs.

## What's next

Check out the [quickstart guide](https://docs.django-matt.dev) to get running in under 5 minutes.
""",
        "excerpt": "The Django REST ecosystem is fragmented. Django-matt fixes that by consolidating 6+ packages into one cohesive library.",
        "category": "Announcements",
        "tags": ["django", "python", "open-source"],
        "featured": False,
    },
    {
        "title": "JWT Authentication Deep Dive",
        "content": """# JWT Authentication Deep Dive

Django-matt ships with JWT authentication batteries included. Here's everything you need to know.

## Basic setup

```python
DJANGO_MATT = {
    "JWT_SECRET_KEY": env("JWT_SECRET_KEY"),
    "JWT_ACCESS_TOKEN_LIFETIME_MINUTES": 60,
    "JWT_REFRESH_TOKEN_LIFETIME_DAYS": 7,
}
```

## Protecting endpoints

```python
from django_matt.auth import jwt_required

class UserController(APIController):
    prefix = "/users"

    @jwt_required
    async def me(self, request) -> UserResponse:
        return UserResponse.model_validate(request.user)
```

## Token refresh

The frontend should refresh the access token before it expires. Here's a minimal Axios interceptor:

```typescript
axiosInstance.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const { data } = await axios.post('/api/auth/refresh', {
        refresh: localStorage.getItem('refresh_token'),
      });
      localStorage.setItem('access_token', data.access);
      error.config.headers.Authorization = `Bearer ${data.access}`;
      return axiosInstance(error.config);
    }
    return Promise.reject(error);
  }
);
```

## Role-based access

```python
@requires_role("admin")
async def admin_only(self, request) -> dict:
    return {"message": "Admin access granted"}
```
""",
        "excerpt": "Everything you need to know about JWT authentication in django-matt — setup, protecting endpoints, token refresh, and RBAC.",
        "category": "Engineering",
        "tags": ["django", "api", "python"],
        "featured": False,
    },
    {
        "title": "Type-Safe APIs: Generating TypeScript from Django-Matt",
        "content": """# Type-Safe APIs: Generating TypeScript from Django-Matt

One of django-matt's killer features is the `sync_types` CLI command, which generates TypeScript interfaces, Zod schemas, and React Query hooks directly from your Pydantic schemas.

## Running the generator

```bash
python manage.py sync_types --target typescript --output ../frontend/src/types
```

This produces:

```typescript
// Auto-generated. Do not edit.
export interface PostListResponse {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  coverImageUrl: string | null;
  author: AuthorSummary;
  status: 'draft' | 'published' | 'archived';
  viewCount: number;
  readingTimeMinutes: number;
  createdAt: string;
  updatedAt: string;
}
```

## Zod schemas

With `--format zod`:

```typescript
export const PostListResponseSchema = z.object({
  id: z.string().uuid(),
  title: z.string(),
  // ...
});
```

## React Query hooks

With `--format react-query`:

```typescript
export function usePostList(params?: PostListParams) {
  return useQuery({
    queryKey: ['posts', params],
    queryFn: () => api.get<PaginatedPostsResponse>('/api/posts', { params }),
  });
}
```

This is how we keep the frontend in sync with the backend without a separate GraphQL layer.
""",
        "excerpt": "Use sync_types to generate TypeScript interfaces, Zod schemas, and React Query hooks from your Django-Matt Pydantic schemas.",
        "category": "Engineering",
        "tags": ["typescript", "react", "api", "python"],
        "featured": False,
    },
    {
        "title": "Deploying Django-Matt to Fly.io",
        "content": """# Deploying Django-Matt to Fly.io

Fly.io is one of the easiest platforms for deploying async Django applications. Here's the full walkthrough.

## Prerequisites

```bash
brew install flyctl
fly auth login
```

## Dockerfile

Django-matt works well with a minimal Docker setup:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install uv
COPY pyproject.toml .
RUN uv sync --no-dev
COPY . .
CMD ["uv", "run", "uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
```

## fly.toml

```toml
app = "my-blog-api"
primary_region = "lax"

[build]

[http_service]
  internal_port = 8000
  force_https = true

[[vm]]
  size = "shared-cpu-1x"
```

## Deploy

```bash
fly launch
fly postgres create
fly secrets set SECRET_KEY=$(openssl rand -hex 32)
fly deploy
```

That's it. Your blog API is live in under 5 minutes.
""",
        "excerpt": "Step-by-step guide to deploying a django-matt API to Fly.io with PostgreSQL.",
        "category": "Tutorials",
        "tags": ["django", "python", "web-development"],
        "featured": False,
    },
]


class Command(BaseCommand):
    help = "Seed the database with sample blog data"

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Clear existing data first")

    def handle(self, *args, **options):
        from blog.comments.models import Comment
        from blog.posts.models import Category, Post, Tag
        from blog.users.models import AuthorProfile, User

        if options["clear"]:
            self.stdout.write("Clearing existing data...")
            Comment.objects.all().delete()
            Post.objects.all().delete()
            Tag.objects.all().delete()
            Category.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()

        # Author
        author, _ = User.objects.get_or_create(
            email="author@example.com",
            defaults={
                "username": "jsmith",
                "first_name": "Jane",
                "last_name": "Smith",
                "is_staff": True,
            },
        )
        if _:
            author.set_password("password123")
            author.save()
            AuthorProfile.objects.get_or_create(
                user=author,
                defaults={
                    "bio": "Senior engineer and open-source enthusiast. Writes about Python, Django, and web development.",
                    "twitter": "jsmith",
                    "github": "jsmith",
                    "location": "San Francisco, CA",
                },
            )
            self.stdout.write(f"  Created author: {author.email} / password123")

        # Tags
        tags = {}
        for name in TAGS:
            tag, _ = Tag.objects.get_or_create(name=name, defaults={"slug": slugify(name)})
            tags[name] = tag
            if _:
                self.stdout.write(f"  Created tag: {name}")

        # Categories
        cats = {}
        for cat_data in CATEGORIES:
            cat, _ = Category.objects.get_or_create(
                name=cat_data["name"],
                defaults={
                    "slug": slugify(cat_data["name"]),
                    "description": cat_data["description"],
                },
            )
            cats[cat_data["name"]] = cat
            if _:
                self.stdout.write(f"  Created category: {cat_data['name']}")

        # Posts
        for post_data in POSTS:
            slug = slugify(post_data["title"])
            if Post.objects.filter(slug=slug).exists():
                self.stdout.write(f"  Skipping existing post: {post_data['title']}")
                continue

            post = Post.objects.create(
                title=post_data["title"],
                slug=slug,
                content=post_data["content"],
                excerpt=post_data["excerpt"],
                author=author,
                category=cats.get(post_data["category"]),
                status="published",
                featured=post_data.get("featured", False),
                published_at=timezone.now(),
            )
            post.tags.set([tags[t] for t in post_data["tags"] if t in tags])
            self.stdout.write(f"  Created post: {post.title}")

            # Sample comments
            Comment.objects.create(
                post=post,
                author_name="Reader One",
                author_email="reader1@example.com",
                content="Great post! Really helpful, thanks for writing this up.",
                is_approved=True,
            )

        self.stdout.write(self.style.SUCCESS("\nSeed complete!"))
        self.stdout.write("  API docs: http://localhost:8000/api/docs")
        self.stdout.write("  RSS feed: http://localhost:8000/feed/rss/")
        self.stdout.write("  Admin:    http://localhost:8000/admin/")
        self.stdout.write("  Login:    author@example.com / password123")
