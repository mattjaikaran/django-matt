# Pagination & Filtering

Page-number, limit-offset, cursor pagination; filter backends; search; ordering.

---

## Pagination

### PageNumberPagination

Query params: `?page=2&page_size=25`

```python
from django_matt.pagination import PageNumberPagination

class UserListView(APIController):
    prefix = "/users"

    @get("/")
    @jwt_required
    async def list_users(self, request):
        pagination = PageNumberPagination(page_size=25)
        qs = User.objects.all()
        page_qs = await pagination.apaginate_queryset(qs, request)
        items = [UserSchema.from_orm(u) async for u in page_qs]
        return pagination.get_paginated_response(items)
```

Response:

```json
{
  "items": [...],
  "total": 150,
  "page": 2,
  "page_size": 25,
  "pages": 6,
  "has_next": true,
  "has_previous": true
}
```

### LimitOffsetPagination

Query params: `?limit=25&offset=50`

```python
from django_matt.pagination import LimitOffsetPagination

pagination = LimitOffsetPagination(page_size=25)
qs = await pagination.apaginate_queryset(Post.objects.all(), request)
items = [PostSchema.from_orm(p) async for p in qs]
return pagination.get_paginated_response(items)
```

Response adds `limit` and `offset` instead of `page`.

### CursorPagination

Stable pagination for live feeds and infinite scroll. Query params: `?cursor=<opaque>&page_size=25`

```python
from django_matt.pagination import CursorPagination

pagination = CursorPagination(
    page_size=25,
    ordering="-created_at",   # field(s) to cursor on
)
qs = await pagination.apaginate_queryset(Event.objects.all(), request)
items = [EventSchema.from_orm(e) async for e in qs]
return pagination.get_paginated_response(items)
```

Response:

```json
{
  "items": [...],
  "page_size": 25,
  "next_cursor": "eyJpZCI6MTI1fQ",
  "previous_cursor": "eyJpZCI6MTAwfQ",
  "has_next": true,
  "has_previous": true
}
```

### Bypass pagination

Any paginator can be skipped:

```http
GET /users/?no_page=1
# or
GET /users/
X-No-Pagination: true
```

Returns a plain list capped at `max_unpaginated` (default 10 000).

---

## Filtering

### DjangoFilterBackend (auto-filter)

Declare `filter_fields` and the backend generates `?field=value` filters:

```python
from django_matt.filtering import DjangoFilterBackend

class UserListView(APIController):
    prefix = "/users"
    filter_fields = ["email", "is_active", "role"]
    filter_backends = [DjangoFilterBackend()]

    @get("/")
    async def list(self, request):
        qs = User.objects.all()
        for backend in self.filter_backends:
            qs = backend.filter_queryset(request, qs, self)
        ...
```

Supports Django ORM lookups in query params:

```
GET /users/?email__icontains=alice
GET /users/?created_at__gte=2024-01-01
GET /users/?role__in=admin,manager
```

### FilterSet (declarative)

```python
from django_matt.filtering import FilterSet, CharFilter, BooleanFilter, DateFilter

class UserFilter(FilterSet):
    email = CharFilter(lookup_expr="icontains")
    is_active = BooleanFilter()
    joined_after = DateFilter(field_name="date_joined", lookup_expr="gte")

    class Meta:
        model = User
        fields = ["email", "is_active"]

class UserListView(APIController):
    filterset_class = UserFilter
    filter_backends = [DjangoFilterBackend()]

    @get("/")
    async def list(self, request):
        qs = User.objects.all()
        for backend in self.filter_backends:
            qs = backend.filter_queryset(request, qs, self)
        ...
```

### Filter types

| Class | Use case |
|-------|----------|
| `CharFilter` | Text, default `icontains` |
| `IntegerFilter` | Integer equality |
| `BooleanFilter` | `true/1/yes` → True |
| `DateFilter` / `DateTimeFilter` | Date comparisons |
| `UUIDFilter` | UUID fields |
| `ChoiceFilter` | Fixed set of values |
| `MultipleChoiceFilter` | Comma-separated IN |
| `InFilter` | Comma-separated IN (generic) |
| `RangeFilter` | `?price_min=10&price_max=50` |
| `ModelChoiceFilter` | FK lookups |

---

## Search

```python
from django_matt.filtering import SearchBackend

class PostListView(APIController):
    search_fields = ["title", "content", "^author__username"]
    #   no prefix  → icontains
    #   ^field     → istartswith
    #   =field     → iexact
    #   @field     → PostgreSQL full-text search
    #   $field     → iregex
    filter_backends = [SearchBackend()]
```

```
GET /posts/?search=django rest
```

### PostgreSQL full-text search

```python
from django_matt.filtering import PostgresSearchBackend

class ArticleListView(APIController):
    search_fields = ["title", "body"]
    filter_backends = [PostgresSearchBackend(search_type="websearch")]
```

Adds a `search_rank` annotation and orders by relevance.

---

## Ordering

```python
from django_matt.filtering import OrderingBackend

class UserListView(APIController):
    ordering_fields = ["email", "date_joined", "last_name"]
    ordering = "-date_joined"   # default ordering
    filter_backends = [OrderingBackend()]
```

```
GET /users/?ordering=-date_joined,email
```

Prefix with `-` for descending. Relation traversal (`author__name`) is supported when the field is in `ordering_fields`.

---

## Combining All Backends

```python
from django_matt.filtering import DjangoFilterBackend, SearchBackend, OrderingBackend
from django_matt.pagination import CursorPagination

class PostListView(APIController):
    prefix = "/posts"

    filter_fields = ["status", "author"]
    search_fields = ["title", "@body"]
    ordering_fields = ["created_at", "title"]
    ordering = "-created_at"

    filter_backends = [DjangoFilterBackend(), SearchBackend(), OrderingBackend()]

    @get("/")
    async def list(self, request):
        qs = Post.objects.select_related("author").all()

        for backend in self.filter_backends:
            qs = backend.filter_queryset(request, qs, self)

        pagination = CursorPagination(page_size=20, ordering="-created_at")
        page_qs = await pagination.apaginate_queryset(qs, request)
        items = [PostSchema.from_orm(p) async for p in page_qs]
        return pagination.get_paginated_response(items)
```

---

## External Search Engines

### Elasticsearch

```python
from django_matt.filtering import ElasticsearchEngine, SearchEngineBackend

engine = ElasticsearchEngine(
    hosts=["http://localhost:9200"],
    index_name="articles",
)

# Index documents
engine.index([{"id": 1, "title": "...", "content": "..."}])

# Use in view
class ArticleListView(APIController):
    filter_backends = [SearchEngineBackend(engine=engine)]
```

### Meilisearch

```python
from django_matt.filtering import MeilisearchEngine

engine = MeilisearchEngine(
    url="http://localhost:7700",
    api_key=env("MEILI_KEY"),
    index_name="articles",
)

engine.update_settings({"searchableAttributes": ["title", "content"]})
engine.index(documents)

results = engine.search("django", limit=20)
```
