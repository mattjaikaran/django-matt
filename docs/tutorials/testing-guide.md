# Testing Your Django Matt App

Set up pytest, use the sync and async test clients, write controller and
ViewSet tests, use the built-in factory and data-generator system, test
auth flows, and verify webhook signatures.

## Prerequisites

- A Django Matt project with at least one controller or ViewSet
- `uv add pytest pytest-asyncio pytest-django`

## 1. Test Setup

### pytest configuration

```ini
# pyproject.toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings"
asyncio_mode = "auto"
python_files = ["tests/*.py", "tests/**/*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

### conftest.py

```python
# tests/conftest.py
import pytest
from django_matt.testing import (
    APITestClient,
    AsyncAPITestClient,
    UserFactory,
)


@pytest.fixture
def api_client():
    """Sync test client."""
    return APITestClient()


@pytest.fixture
def async_client():
    """Async test client."""
    return AsyncAPITestClient()


@pytest.fixture
def user(db):
    """Create a test user."""
    return UserFactory.create()


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return UserFactory.create(is_staff=True, is_superuser=True)


@pytest.fixture
def authenticated_client(api_client, user):
    """Client with a user already authenticated."""
    api_client.force_authenticate(user)
    return api_client
```

## 2. APITestClient

`APITestClient` extends Django's `Client` with JWT helpers and
`request.auser()` support.

### force_authenticate

```python
from django_matt.testing import APITestClient

client = APITestClient()
client.force_authenticate(user)

# All subsequent requests include the JWT Authorization header
# AND set request.user + request.auser() on every request
response = client.get("/api/posts/")
assert response.status_code == 200
```

### Parse JSON responses

```python
response = client.get("/api/posts/")
data = client.json(response)  # orjson.loads(response.content)
assert "items" in data
```

### Organization/tenant context

```python
client.set_organization(org)
# Adds X-Organization-ID header to all requests
response = client.get("/api/projects/")
```

### POST with JSON body

```python
response = client.post(
    "/api/posts/",
    data={"title": "Test", "slug": "test", "body": "Hello"},
    content_type="application/json",
)
assert response.status_code == 201
```

## 3. AsyncAPITestClient

`AsyncAPITestClient` is the standard test client for Django Matt.  All
controllers are async by default, so prefer this client over the sync
`APITestClient` for controller tests.

```python
import pytest
from django_matt.testing import AsyncAPITestClient


@pytest.mark.asyncio
async def test_list_posts(async_client, user):
    # force_authenticate is async — it calls acreate_access_token() internally
    await async_client.force_authenticate(user)
    response = await async_client.get("/api/posts/")
    assert response.status_code == 200
    data = async_client.json(response)
    assert "items" in data
```

`AsyncAPITestClient` extends Django's `AsyncClient`.  `force_authenticate`
calls `acreate_access_token()` (the async token factory) so it is safe to
`await` inside any `async def` test.

For tests that need a pre-authenticated client from a fixture, authenticate
inside an `async` fixture:

```python
@pytest.fixture
async def authenticated_async_client(async_client, user):
    await async_client.force_authenticate(user)
    return async_client
```

## 4. Testing Controllers

### Basic CRUD tests

```python
# tests/test_posts.py
import pytest
from django_matt.testing import APITestClient, UserFactory
from blog.models import Post


@pytest.fixture
def post(db, user):
    return Post.objects.create(
        title="Test Post",
        slug="test-post",
        body="Test body",
        author=user,
    )


class TestPostController:

    def test_list_posts(self, authenticated_client, post):
        response = authenticated_client.get("/api/posts/")
        assert response.status_code == 200
        data = authenticated_client.json(response)
        assert len(data["items"]) >= 1

    def test_get_post(self, authenticated_client, post):
        response = authenticated_client.get(f"/api/posts/{post.id}/")
        assert response.status_code == 200
        data = authenticated_client.json(response)
        assert data["title"] == "Test Post"

    def test_create_post(self, authenticated_client):
        response = authenticated_client.post(
            "/api/posts/",
            data={
                "title": "New Post",
                "slug": "new-post",
                "body": "New body",
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        data = authenticated_client.json(response)
        assert data["title"] == "New Post"
        assert Post.objects.filter(slug="new-post").exists()

    def test_update_post(self, authenticated_client, post):
        response = authenticated_client.patch(
            f"/api/posts/{post.id}/",
            data={"title": "Updated Title"},
            content_type="application/json",
        )
        assert response.status_code == 200
        post.refresh_from_db()
        assert post.title == "Updated Title"

    def test_delete_post(self, authenticated_client, post):
        response = authenticated_client.delete(f"/api/posts/{post.id}/")
        assert response.status_code == 200
        assert not Post.objects.filter(id=post.id).exists()
```

### Testing validation errors

```python
def test_create_post_missing_title(self, authenticated_client):
    response = authenticated_client.post(
        "/api/posts/",
        data={"slug": "no-title", "body": "Missing title"},
        content_type="application/json",
    )
    assert response.status_code == 422
    data = authenticated_client.json(response)
    assert data["detail"] == "Validation error"
    assert any(e["loc"] == ["title"] for e in data["errors"])
```

### Testing unauthorized access

```python
def test_create_post_unauthenticated(self, api_client):
    """Unauthenticated requests are rejected."""
    response = api_client.post(
        "/api/posts/",
        data={"title": "Nope"},
        content_type="application/json",
    )
    assert response.status_code in (401, 403)
```

## 5. Custom Assertions

`django_matt.testing.assertions` provides focused assertion helpers:

```python
from django_matt.testing import (
    assert_status,
    assert_created,
    assert_not_found,
    assert_unauthorized,
    assert_forbidden,
    assert_no_content,
    assert_validation_error,
    assert_contains_keys,
    assert_json_equal,
    assert_error_response,
    assert_query_count,
)


def test_assertion_helpers(authenticated_client, post):
    # Status code assertions (with response body in error messages)
    response = authenticated_client.get(f"/api/posts/{post.id}/")
    assert_status(response, 200)

    # Check JSON keys
    assert_contains_keys(response, ["id", "title", "body"])

    # Not found
    response = authenticated_client.get("/api/posts/nonexistent/")
    assert_not_found(response)

    # Query count assertion (N+1 detection)
    with assert_query_count(2):
        authenticated_client.get("/api/posts/")
```

## 6. Factory Patterns

### Built-in factories

```python
from django_matt.testing import UserFactory, OrganizationFactory, TeamFactory

# Create a user
user = UserFactory.create()
user = UserFactory.create(username="alice", is_staff=True)

# Batch creation
users = UserFactory.create_batch(10)

# Organization and team
org = OrganizationFactory.create(name="Acme Corp")
team = TeamFactory.create(organization=org)
```

### Custom factories

Build your own using the built-in `ModelFactory` system (no factory-boy
needed):

```python
# tests/factories.py
from django_matt.testing import ModelFactory, Field, Sequence, SubFactory, fake
from blog.models import Post


class PostFactory(ModelFactory):
    class Meta:
        model = Post

    title = Sequence(lambda n: f"Post {n}")
    slug = Sequence(lambda n: f"post-{n}")
    body = Field(lambda self: fake.paragraph())
    published = False
    author = SubFactory("tests.factories.UserFactory")
```

Use it in tests:

```python
from tests.factories import PostFactory


def test_list_published_posts(authenticated_client):
    PostFactory.create_batch(3, published=True)
    PostFactory.create_batch(2, published=False)

    response = authenticated_client.get("/api/posts/?published=true")
    data = authenticated_client.json(response)
    assert len(data["items"]) == 3
```

### Built-in data generators

`django_matt.testing.generators.fake` replaces Faker with a zero-dep
built-in:

```python
from django_matt.testing import fake

fake.email()         # "user42@example.com"
fake.name()          # "Alice Johnson"
fake.first_name()    # "Bob"
fake.last_name()     # "Smith"
fake.paragraph()     # "Lorem ipsum..."
fake.url()           # "https://example-42.com"
fake.uuid()          # "a1b2c3d4-..."
fake.phone_number()  # "+1-555-0142"
```

## 7. Testing Auth Flows

### Login and token flow

```python
def test_login_flow(api_client, user):
    # Login
    response = api_client.post(
        "/api/auth/login",
        data={"email": user.email, "password": "testpass123"},
        content_type="application/json",
    )
    assert_status(response, 200)
    data = api_client.json(response)
    assert "access" in data
    assert "refresh" in data

    # Use the token
    api_client.force_authenticate(token=data["access"])
    response = api_client.get("/api/auth/me")
    assert_status(response, 200)


def test_token_refresh(api_client, user):
    # Get initial tokens
    response = api_client.post(
        "/api/auth/login",
        data={"email": user.email, "password": "testpass123"},
        content_type="application/json",
    )
    tokens = api_client.json(response)

    # Refresh
    response = api_client.post(
        "/api/auth/refresh",
        data={"refresh": tokens["refresh"]},
        content_type="application/json",
    )
    assert_status(response, 200)
    new_tokens = api_client.json(response)
    assert "access" in new_tokens
```

### Role-based access

```python
from django_matt.testing import UserFactory


def test_admin_only_endpoint(api_client):
    regular_user = UserFactory.create()
    admin_user = UserFactory.create(is_staff=True, is_superuser=True)

    # Regular user is forbidden
    api_client.force_authenticate(regular_user)
    response = api_client.delete("/api/admin/users/1/")
    assert response.status_code in (403, 404)

    # Admin succeeds
    api_client.force_authenticate(admin_user)
    response = api_client.get("/api/admin/users/")
    assert_status(response, 200)
```

### Multi-tenant auth

```python
from django_matt.testing import UserFactory, OrganizationFactory, MembershipFactory


def test_tenant_isolation(api_client):
    org_a = OrganizationFactory.create(name="Org A")
    org_b = OrganizationFactory.create(name="Org B")
    user_a = UserFactory.create()
    user_b = UserFactory.create()
    MembershipFactory.create(user=user_a, organization=org_a, role="member")
    MembershipFactory.create(user=user_b, organization=org_b, role="member")

    # User A sees only Org A data
    api_client.force_authenticate(user_a)
    api_client.set_organization(org_a)
    response = api_client.get("/api/projects/")
    data = api_client.json(response)
    for project in data["items"]:
        assert project["organization_id"] == str(org_a.id)
```

## 8. Scenario-Based CRUD Testing

`CRUDScenario` and `CRUDTestCase` provide declarative, data-driven
tests with savepoint isolation:

```python
from django_matt.testing.crud import CRUDScenario, CRUDTestCase


def test_post_crud_scenarios(authenticated_client, post):
    scenarios = [
        CRUDScenario(
            method="GET",
            url="/api/posts/",
            expected_status=200,
            description="list posts returns 200",
        ),
        CRUDScenario(
            method="POST",
            url="/api/posts/",
            data={"title": "Scenario Post", "slug": "scenario", "body": "Hello"},
            expected_status=200,
            expected_body={"title": "Scenario Post"},
            description="create post returns the new post",
        ),
        CRUDScenario(
            method="GET",
            url=f"/api/posts/{post.id}/",
            expected_status=200,
            expected_body={"title": post.title},
            description="get single post by ID",
        ),
        CRUDScenario(
            method="PATCH",
            url=f"/api/posts/{post.id}/",
            data={"title": "Patched"},
            expected_status=200,
            expected_body={"title": "Patched"},
            description="patch updates only specified fields",
        ),
        CRUDScenario(
            method="DELETE",
            url=f"/api/posts/{post.id}/",
            expected_status=200,
            description="delete post succeeds",
        ),
    ]

    CRUDTestCase(scenarios=scenarios).run(authenticated_client)
```

### Auto-generate scenarios

```python
from django_matt.testing.crud import generate_crud_scenarios
from blog.views import PostViewSet


def test_auto_generated_scenarios(authenticated_client, post):
    scenarios = generate_crud_scenarios(PostViewSet)
    CRUDTestCase(scenarios=scenarios).run(authenticated_client)
```

## 9. Testing Webhooks

### Stripe webhook verification

```python
import hmac
import hashlib
import time


def test_stripe_webhook(api_client):
    payload = b'{"type": "checkout.session.completed", "data": {}}'
    timestamp = str(int(time.time()))
    secret = "whsec_test_secret"

    # Build Stripe signature
    signed_payload = f"{timestamp}.".encode() + payload
    signature = hmac.new(
        secret.encode(), signed_payload, hashlib.sha256
    ).hexdigest()
    header = f"t={timestamp},v1={signature}"

    response = api_client.post(
        "/api/billing/webhooks/stripe",
        data=payload,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE=header,
    )
    assert response.status_code == 200
```

### Event bus testing

```python
import pytest
from django_matt.events import get_event_bus, Event


class TestEvent(Event):
    __event_type__ = "test.event"
    value: str


@pytest.mark.asyncio
async def test_event_bus():
    bus = get_event_bus()
    received = []

    async def handler(event: TestEvent):
        received.append(event.value)

    bus.subscribe("test.event", handler)

    await bus.emit(TestEvent(value="hello"))

    assert received == ["hello"]

    # Cleanup
    bus.unsubscribe("test.event", handler)
```

## 10. Testing with CQRS

Use the in-memory test buses to isolate CQRS handlers:

```python
from django_matt.cqrs import (
    InMemoryCommandBus,
    InMemoryQueryBus,
    assert_command_dispatched,
    assert_query_dispatched,
)


@pytest.mark.asyncio
async def test_save_conversation_command():
    bus = InMemoryCommandBus()

    from ai.cqrs import SaveConversation
    from ai.handlers import SaveConversationHandler

    bus.register(SaveConversation, SaveConversationHandler())

    await bus.dispatch(SaveConversation(
        conversation_id="test-id",
        user_id=1,
        user_message="Hello",
        assistant_message="Hi there!",
    ))

    assert_command_dispatched(bus, SaveConversation)
```

## 11. Performance Testing

### N+1 query detection

```python
from django_matt.testing import assert_query_count


def test_no_n_plus_one(authenticated_client):
    PostFactory.create_batch(50)

    # List endpoint should use select_related/prefetch_related
    with assert_query_count(2):  # 1 for auth, 1 for posts
        response = authenticated_client.get("/api/posts/")
        assert_status(response, 200)
```

## 12. Complete conftest.py

```python
# tests/conftest.py
import pytest
from django_matt.testing import (
    APITestClient,
    AsyncAPITestClient,
    UserFactory,
    OrganizationFactory,
    MembershipFactory,
)
from blog.models import Post


@pytest.fixture
def api_client():
    return APITestClient()


@pytest.fixture
def async_client():
    return AsyncAPITestClient()


@pytest.fixture
def user(db):
    return UserFactory.create()


@pytest.fixture
def admin_user(db):
    return UserFactory.create(is_staff=True, is_superuser=True)


@pytest.fixture
def authenticated_client(api_client, user):
    api_client.force_authenticate(user)
    return api_client


@pytest.fixture
def org(db):
    return OrganizationFactory.create()


@pytest.fixture
def member(db, user, org):
    return MembershipFactory.create(user=user, organization=org, role="member")


@pytest.fixture
def post(db, user):
    return Post.objects.create(
        title="Test Post",
        slug="test-post",
        body="Test body content",
        author=user,
    )
```

Run the tests:

```bash
uv run pytest tests/ -x -q
uv run pytest tests/ --cov=blog -q   # with coverage
uv run pytest tests/test_posts.py -v  # verbose single file
```

## Next Steps

- [Build a REST API](build-a-rest-api.md) -- if you haven't already
- [Build a Multi-Tenant SaaS API](build-a-saas-app.md) -- test tenant isolation
- [Build an AI/LLM Streaming API](ai-streaming-api.md) -- test streaming endpoints
