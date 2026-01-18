# API Versioning

Support multiple API versions simultaneously.

## Versioning Schemes

### URL Path Versioning (Recommended)

```
/api/v1/users/
/api/v2/users/
```

```python
from django_matt.versioning import URLPathVersioning

api = MattAPI(versioning_class=URLPathVersioning)
```

### Header Versioning

```
X-API-Version: 2
```

```python
from django_matt.versioning import HeaderVersioning

api = MattAPI(versioning_class=HeaderVersioning)
```

### Accept Header Versioning

```
Accept: application/json; version=2
```

```python
from django_matt.versioning import AcceptHeaderVersioning

api = MattAPI(versioning_class=AcceptHeaderVersioning)
```

### Query Parameter Versioning

```
/api/users/?version=2
```

```python
from django_matt.versioning import QueryParameterVersioning

api = MattAPI(versioning_class=QueryParameterVersioning)
```

## VersionedAPI

Manage multiple API versions:

```python
from django_matt.versioning import VersionedAPI

versioned_api = VersionedAPI(
    title="My API",
    default_version="2",
    allowed_versions=["1", "2"],
)

# Register version-specific routes
@versioned_api.get("/users", versions=["1", "2"])
async def list_users(request):
    if request.version == "1":
        return {"users": [...]}  # V1 format
    return {"data": {"users": [...]}}  # V2 format
```

## Version Decorators

### @version

Specify supported versions:

```python
from django_matt.versioning import version

@api.get("/users")
@version("1", "2")
async def list_users(request):
    ...
```

### @deprecated

Mark endpoints as deprecated:

```python
from django_matt.versioning import deprecated

@api.get("/old-endpoint")
@deprecated(message="Use /new-endpoint instead", sunset="2024-06-01")
async def old_endpoint(request):
    ...
```

Response includes deprecation headers:

```
Deprecation: true
Sunset: Sat, 01 Jun 2024 00:00:00 GMT
Link: </new-endpoint>; rel="successor-version"
```

### @min_version / @max_version

Version constraints:

```python
from django_matt.versioning import min_version, max_version

@api.get("/new-feature")
@min_version("2")
async def new_feature(request):
    # Only available in v2+
    ...

@api.get("/legacy-feature")
@max_version("1")
async def legacy_feature(request):
    # Only available in v1
    ...
```

## VersionedRouter

Group endpoints by version:

```python
from django_matt.versioning import VersionedRouter

v1_router = VersionedRouter(version="1")
v2_router = VersionedRouter(version="2")

@v1_router.get("/users")
async def list_users_v1(request):
    return {"users": [...]}

@v2_router.get("/users")
async def list_users_v2(request):
    return {"data": {"users": [...]}, "meta": {...}}

api.include_router(v1_router, prefix="/v1")
api.include_router(v2_router, prefix="/v2")
```

## Middleware

```python
# settings.py
MIDDLEWARE = [
    "django_matt.versioning.VersioningMiddleware",
]

DJANGO_MATT = {
    "VERSIONING": {
        "SCHEME": "url",  # or "header", "accept", "query"
        "DEFAULT_VERSION": "2",
        "ALLOWED_VERSIONS": ["1", "2", "3"],
        "HEADER_NAME": "X-API-Version",
        "QUERY_PARAM": "version",
    },
}
```

## Accessing Version

```python
@api.get("/users")
async def list_users(request):
    version = request.version  # "1", "2", etc.

    if version == "1":
        return v1_response()
    elif version == "2":
        return v2_response()
```

## Version-Specific Schemas

```python
from django_matt import Schema

class UserResponseV1(Schema):
    id: int
    email: str

class UserResponseV2(Schema):
    id: int
    email: str
    profile: dict
    meta: dict

@api.get("/users/{id}")
async def get_user(request, id: int):
    user = await User.objects.aget(id=id)

    if request.version == "1":
        return UserResponseV1(id=user.id, email=user.email)
    return UserResponseV2(
        id=user.id,
        email=user.email,
        profile=user.profile,
        meta={"created_at": user.created_at},
    )
```

## Best Practices

1. **Use URL path versioning** - Most explicit and cache-friendly
2. **Support multiple versions** - Give clients time to migrate
3. **Document breaking changes** - Clear changelog per version
4. **Set sunset dates** - Communicate deprecation timeline
5. **Version schemas** - Different response formats per version
