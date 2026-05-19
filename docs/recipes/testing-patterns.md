# Testing Patterns

Async tests, JWT fixtures, model factories, custom assertions, and real-database integration.

---

## Setup

```python
# pytest.ini / pyproject.toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings"
asyncio_mode = "auto"
```

```bash
uv run pytest tests/ -x -q
uv run pytest tests/test_users.py -v      # single file
uv run pytest tests/ --cov=django_matt    # coverage
```

No DB mocks — integration tests always hit the real database via NullPool.

---

## APITestClient

### Sync

```python
from django_matt.testing.client import APITestClient

class TestUserAPI:
    @pytest.mark.django_db
    def test_list_users(self):
        user = UserFactory.create()
        client = APITestClient()
        client.force_authenticate(user)        # auto-generates JWT

        response = client.get("/api/users/")
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_create_user(self):
        admin = UserFactory.create_admin()
        client = APITestClient()
        client.force_authenticate(admin)

        response, data = client.post_json("/api/users/", data={
            "email": "bob@example.com",
            "username": "bob",
        })
        assert response.status_code == 201
        assert data["email"] == "bob@example.com"
```

### Async

```python
from django_matt.testing.client import AsyncAPITestClient

class TestPostAPI:
    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_create_post(self):
        user = await UserFactory.acreate()
        client = AsyncAPITestClient()
        await client.force_authenticate(user)

        response, data = await client.post_json("/api/posts/", data={
            "title": "Hello World",
            "content": "First post.",
        })
        assert response.status_code == 201
        assert data["title"] == "Hello World"
```

### Multi-tenant client

```python
client = APITestClient()
client.force_authenticate(user)
client.set_organization(org)   # adds X-Organization-ID header

response = client.get("/api/projects/")
```

### Available methods

```python
client.get(path, **kwargs)
client.post(path, data=None, **kwargs)
client.put(path, data=None, **kwargs)
client.patch(path, data=None, **kwargs)
client.delete(path, **kwargs)

# JSON shorthand — returns (response, parsed_data)
response, data = client.get_json(path)
response, data = client.post_json(path, data={...})
response, data = client.put_json(path, data={...})
response, data = client.patch_json(path, data={...})
```

---

## Model Factories

Built-in replacement for factory-boy (no external dep):

```python
from django_matt.testing.model_factory import (
    ModelFactory, Field, Sequence, SubFactory, LazyAttribute, PostGeneration
)

class UserFactory(ModelFactory):
    class Meta:
        model = "auth.User"
        django_get_or_create = ("username",)

    username = Sequence(lambda n: f"user{n}")
    email = Field(lambda self: f"{self.username}@example.com")
    is_active = True

class PostFactory(ModelFactory):
    class Meta:
        model = "blog.Post"

    title = Sequence(lambda n: f"Post {n}")
    author = SubFactory(UserFactory)
    status = "draft"
```

### Factory operations

```python
# Single instance
user = UserFactory.create()          # saved to DB
user = UserFactory.build()           # unsaved

# Batch
users = UserFactory.create_batch(5)

# Overrides
admin = UserFactory.create(is_staff=True, username="admin")

# Async
user = await UserFactory.acreate()
```

### Pre-built factories

```python
from django_matt.testing.factories import (
    UserFactory,
    OrganizationFactory,
    TeamFactory,
    MembershipFactory,
)

admin      = UserFactory.create_admin()      # is_staff=True
staff      = UserFactory.create_staff()
org        = OrganizationFactory.create(name="Acme")
owner_mem  = MembershipFactory.create_owner()
```

---

## JWT Fixtures

```python
from django_matt.auth import create_token_pair, acreate_token_pair

@pytest.fixture
def user(db):
    return UserFactory.create()

@pytest.fixture
def auth_client(user):
    client = APITestClient()
    client.force_authenticate(user)   # JWT generated automatically
    return client

@pytest.fixture
def tokens(user):
    return create_token_pair(user)

# Async fixture
@pytest.fixture
async def async_tokens(user):
    return await acreate_token_pair(user)
```

---

## Custom Assertions

```python
from django_matt.testing.assertions import (
    assert_status,
    assert_json_equal,
    assert_contains_keys,
    assert_error_response,
    assert_validation_error,
    assert_not_found,
    assert_forbidden,
    assert_unauthorized,
    assert_created,
    assert_no_content,
    assert_query_count,
)

def test_get_user(auth_client):
    response = auth_client.get("/api/users/1/")
    assert_status(response, 200)
    assert_contains_keys(response, ["id", "email", "roles"])

def test_unauthorized():
    client = APITestClient()
    response = client.get("/api/users/")
    assert_unauthorized(response)

def test_not_found(auth_client):
    response = auth_client.get("/api/users/99999/")
    assert_not_found(response)

def test_validation(auth_client):
    response = auth_client.post("/api/users/", data={})
    assert_validation_error(response, field="email")

def test_query_count(auth_client):
    # Ensure no N+1 queries
    response = auth_client.get("/api/posts/")
    assert_query_count(response, num_queries=2)
```

---

## Fixtures from `django_matt.testing.fixtures`

```python
from django_matt.testing.fixtures import (
    get_api_client,
    get_authenticated_client,
    get_user,
    get_admin_user,
    get_organization,
    get_team,
)

@pytest.fixture
def client():
    return get_api_client()

@pytest.fixture
def auth_client(db):
    user = get_user()
    return get_authenticated_client(user)

@pytest.fixture
def org(db):
    return get_organization(name="Test Org")
```

---

## Fake Data Generator

Built-in faker (no external dep, deterministic with seed):

```python
from django_matt.testing.generators import fake

fake.seed(42)   # deterministic output

name  = fake.name()           # "John Doe"
email = fake.email()          # "john@example.com"
text  = fake.paragraph()
date  = fake.date()
uuid  = fake.uuid()
phone = fake.phone_number()
url   = fake.url()

# Locale
fake.set_locale("de_DE")
german_name = fake.name()
```

---

## Full Test Example

```python
import pytest
from django_matt.testing.client import AsyncAPITestClient
from django_matt.testing.factories import UserFactory, OrganizationFactory, MembershipFactory
from django_matt.testing.assertions import assert_status, assert_contains_keys, assert_forbidden

@pytest.mark.django_db
class TestProjectAPI:
    async def test_list_projects_requires_auth(self):
        client = AsyncAPITestClient()
        response = await client.get("/api/projects/")
        assert response.status_code == 401

    async def test_list_projects(self):
        user = await UserFactory.acreate()
        org = await OrganizationFactory.acreate()
        await MembershipFactory.acreate(user=user, organization=org, role="member")

        client = AsyncAPITestClient()
        await client.force_authenticate(user)
        client.set_organization(org)

        response, data = await client.get_json("/api/projects/")
        assert_status(response, 200)
        assert "items" in data

    async def test_create_project_forbidden_for_viewer(self):
        user = await UserFactory.acreate()
        org = await OrganizationFactory.acreate()
        await MembershipFactory.acreate(user=user, organization=org, role="viewer")

        client = AsyncAPITestClient()
        await client.force_authenticate(user)
        client.set_organization(org)

        response = await client.post("/api/projects/", data={"name": "New"})
        assert_forbidden(response)
```

---

## Async Test Patterns

```python
# Use pytest.mark.asyncio (or asyncio_mode="auto" in config)
@pytest.mark.django_db
@pytest.mark.asyncio
async def test_async_endpoint():
    user = await UserFactory.acreate()
    client = AsyncAPITestClient()
    await client.force_authenticate(user)
    response = await client.get("/api/me/")
    assert response.status_code == 200

# Async fixtures
@pytest.fixture
async def org(db):
    return await OrganizationFactory.acreate(name="Test")
```

---

## Real Database (No Mocks)

Tests always hit the real database — never mock ORM calls. Use transactions for isolation:

```python
# pyproject.toml — use NullPool to avoid connection pool issues in tests
[tool.pytest.ini_options]
# DATABASE_URL should point to a test DB or use pytest-django's --reuse-db

# Correct: test DB setup
@pytest.fixture(scope="session")
def django_db_setup(django_test_environment, django_db_blocker):
    with django_db_blocker.unblock():
        from django.test.utils import setup_test_environment
        setup_test_environment()
```

Use `@pytest.mark.django_db(transaction=True)` when testing code that relies on `on_commit` hooks.
