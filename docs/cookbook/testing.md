# Testing Recipes

This cookbook covers testing patterns and best practices for django-matt APIs.

## Test Client Setup

### Basic Setup

```python
import pytest
from django_matt.testing import APITestClient, AsyncAPITestClient

@pytest.fixture
def client():
    """Sync test client."""
    from myapp.api import api
    return APITestClient(api)

@pytest.fixture
def async_client():
    """Async test client."""
    from myapp.api import api
    return AsyncAPITestClient(api)
```

### Authenticated Client

```python
from django_matt.testing import UserFactory

@pytest.fixture
def user(db):
    """Create a test user."""
    return UserFactory()

@pytest.fixture
def auth_client(client, user):
    """Client with authenticated user."""
    client.authenticate(user)
    return client

@pytest.fixture
def admin_client(client, db):
    """Client with admin user."""
    admin = UserFactory(is_staff=True, is_superuser=True)
    client.authenticate(admin)
    return client
```

## Testing Endpoints

### Basic CRUD Tests

```python
import pytest

class TestProductAPI:
    def test_list_products(self, client, product_factory):
        """Test listing products."""
        # Create test data
        products = [product_factory() for _ in range(3)]

        response = client.get("/api/products/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_create_product_authenticated(self, auth_client):
        """Test creating a product requires authentication."""
        response = auth_client.post("/api/products/", json={
            "name": "Test Product",
            "price": 29.99,
            "description": "A test product",
        })

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Product"
        assert data["price"] == 29.99

    def test_create_product_unauthenticated(self, client):
        """Test that unauthenticated users cannot create products."""
        response = client.post("/api/products/", json={
            "name": "Test Product",
            "price": 29.99,
        })

        assert response.status_code == 401

    def test_get_product(self, client, product_factory):
        """Test getting a single product."""
        product = product_factory(name="Specific Product")

        response = client.get(f"/api/products/{product.id}/")

        assert response.status_code == 200
        assert response.json()["name"] == "Specific Product"

    def test_get_product_not_found(self, client):
        """Test 404 for non-existent product."""
        response = client.get("/api/products/99999/")

        assert response.status_code == 404

    def test_update_product(self, auth_client, product_factory, user):
        """Test updating a product."""
        product = product_factory(owner=user)

        response = auth_client.put(f"/api/products/{product.id}/", json={
            "name": "Updated Name",
            "price": 39.99,
        })

        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    def test_delete_product(self, auth_client, product_factory, user):
        """Test deleting a product."""
        product = product_factory(owner=user)

        response = auth_client.delete(f"/api/products/{product.id}/")

        assert response.status_code == 204
```

### Testing Validation

```python
class TestProductValidation:
    def test_create_product_missing_name(self, auth_client):
        """Test validation error for missing name."""
        response = auth_client.post("/api/products/", json={
            "price": 29.99,
        })

        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any(e["loc"] == ["body", "name"] for e in errors)

    def test_create_product_invalid_price(self, auth_client):
        """Test validation error for negative price."""
        response = auth_client.post("/api/products/", json={
            "name": "Test",
            "price": -10,
        })

        assert response.status_code == 422

    def test_create_product_duplicate_sku(self, auth_client, product_factory):
        """Test conflict error for duplicate SKU."""
        product_factory(sku="ABC123")

        response = auth_client.post("/api/products/", json={
            "name": "Test",
            "price": 29.99,
            "sku": "ABC123",
        })

        assert response.status_code == 409
```

### Testing Permissions

```python
class TestProductPermissions:
    def test_owner_can_update(self, auth_client, product_factory, user):
        """Test that owners can update their products."""
        product = product_factory(owner=user)

        response = auth_client.put(f"/api/products/{product.id}/", json={
            "name": "Updated",
            "price": 10,
        })

        assert response.status_code == 200

    def test_non_owner_cannot_update(self, auth_client, product_factory):
        """Test that non-owners cannot update products."""
        other_user = UserFactory()
        product = product_factory(owner=other_user)

        response = auth_client.put(f"/api/products/{product.id}/", json={
            "name": "Updated",
            "price": 10,
        })

        assert response.status_code == 403

    def test_admin_can_update_any(self, admin_client, product_factory):
        """Test that admins can update any product."""
        product = product_factory()

        response = admin_client.put(f"/api/products/{product.id}/", json={
            "name": "Admin Updated",
            "price": 10,
        })

        assert response.status_code == 200
```

## Testing Authentication

### JWT Authentication Tests

```python
class TestAuthentication:
    def test_login_success(self, client, user):
        """Test successful login."""
        user.set_password("testpass123")
        user.save()

        response = client.post("/api/auth/login", json={
            "email": user.email,
            "password": "testpass123",
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_invalid_credentials(self, client, user):
        """Test login with wrong password."""
        response = client.post("/api/auth/login", json={
            "email": user.email,
            "password": "wrongpassword",
        })

        assert response.status_code == 401

    def test_protected_endpoint_with_token(self, client, user):
        """Test accessing protected endpoint with valid token."""
        user.set_password("testpass123")
        user.save()

        # Login
        login_response = client.post("/api/auth/login", json={
            "email": user.email,
            "password": "testpass123",
        })
        token = login_response.json()["access_token"]

        # Access protected endpoint
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert response.json()["email"] == user.email

    def test_token_refresh(self, client, user):
        """Test refreshing access token."""
        user.set_password("testpass123")
        user.save()

        # Login
        login_response = client.post("/api/auth/login", json={
            "email": user.email,
            "password": "testpass123",
        })
        refresh_token = login_response.json()["refresh_token"]

        # Refresh
        response = client.post("/api/auth/refresh", json={
            "refresh_token": refresh_token,
        })

        assert response.status_code == 200
        assert "access_token" in response.json()
```

## Async Testing

### Async Test Client

```python
import pytest

@pytest.mark.asyncio
class TestAsyncEndpoints:
    async def test_list_products_async(self, async_client, product_factory):
        """Test listing products asynchronously."""
        products = [await product_factory.acreate() for _ in range(3)]

        response = await async_client.get("/api/products/")

        assert response.status_code == 200
        assert len(response.json()) == 3

    async def test_concurrent_requests(self, async_client, product_factory):
        """Test handling concurrent requests."""
        import asyncio

        product = await product_factory.acreate()

        # Make concurrent requests
        responses = await asyncio.gather(*[
            async_client.get(f"/api/products/{product.id}/")
            for _ in range(10)
        ])

        # All should succeed
        assert all(r.status_code == 200 for r in responses)
```

## Factories

### Model Factories

```python
import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model

User = get_user_model()


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    username = factory.Sequence(lambda n: f"user{n}")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_active = True

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        if extracted:
            self.set_password(extracted)
        else:
            self.set_password("defaultpass123")


class ProductFactory(DjangoModelFactory):
    class Meta:
        model = "products.Product"

    name = factory.Faker("product_name")
    description = factory.Faker("paragraph")
    price = factory.Faker("pydecimal", left_digits=3, right_digits=2, positive=True)
    sku = factory.Sequence(lambda n: f"SKU-{n:05d}")
    stock = factory.Faker("random_int", min=0, max=100)
    owner = factory.SubFactory(UserFactory)


class OrderFactory(DjangoModelFactory):
    class Meta:
        model = "orders.Order"

    user = factory.SubFactory(UserFactory)
    status = "pending"
    total = factory.LazyAttribute(lambda o: sum(
        item.price * item.quantity for item in o.items.all()
    ) if hasattr(o, 'items') else 0)

    @factory.post_generation
    def items(self, create, extracted, **kwargs):
        if extracted:
            for item in extracted:
                OrderItemFactory(order=self, **item)
```

### Using Factories in Tests

```python
@pytest.fixture
def product_factory(db):
    return ProductFactory


@pytest.fixture
def user_factory(db):
    return UserFactory


class TestProducts:
    def test_with_factory(self, client, product_factory):
        product = product_factory(
            name="Custom Product",
            price=99.99,
        )

        response = client.get(f"/api/products/{product.id}/")

        assert response.status_code == 200
        assert response.json()["name"] == "Custom Product"

    def test_batch_create(self, client, product_factory):
        products = product_factory.create_batch(10)

        response = client.get("/api/products/")

        assert len(response.json()) == 10
```

## Mocking External Services

### Mocking API Calls

```python
from unittest.mock import AsyncMock, patch

class TestPaymentIntegration:
    @patch("myapp.services.stripe.stripe.Charge.create")
    def test_process_payment(self, mock_charge, auth_client, order_factory):
        """Test payment processing with mocked Stripe."""
        mock_charge.return_value = {
            "id": "ch_test123",
            "status": "succeeded",
        }

        order = order_factory(status="pending", total=100)

        response = auth_client.post(f"/api/orders/{order.id}/pay", json={
            "payment_method": "pm_card_visa",
        })

        assert response.status_code == 200
        mock_charge.assert_called_once()

    @patch("myapp.services.email.send_email", new_callable=AsyncMock)
    async def test_send_confirmation_email(self, mock_email, async_client, order_factory):
        """Test email sending is triggered."""
        mock_email.return_value = True

        response = await async_client.post("/api/orders/", json={...})

        assert response.status_code == 201
        mock_email.assert_called_once()
```

### Mocking Database Queries

```python
from unittest.mock import patch, MagicMock

class TestWithMockedDB:
    @patch("myapp.models.Product.objects.filter")
    def test_search_with_mock(self, mock_filter, client):
        """Test search with mocked database."""
        mock_filter.return_value = MagicMock()
        mock_filter.return_value.__aiter__ = lambda self: iter([
            MagicMock(id=1, name="Product 1"),
            MagicMock(id=2, name="Product 2"),
        ])

        response = client.get("/api/products/search?q=test")

        mock_filter.assert_called()
```

## Performance Testing

### Response Time Testing

```python
import time

class TestPerformance:
    def test_list_products_performance(self, client, product_factory):
        """Test that listing products is fast."""
        # Create many products
        product_factory.create_batch(100)

        start = time.time()
        response = client.get("/api/products/")
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 0.5  # Should complete in under 500ms

    def test_search_performance(self, client, product_factory):
        """Test search performance."""
        product_factory.create_batch(1000)

        start = time.time()
        response = client.get("/api/products/search?q=test")
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 1.0  # Should complete in under 1 second
```

### Load Testing Setup

```python
# conftest.py
import pytest

@pytest.fixture(scope="session")
def load_test_data(django_db_setup, django_db_blocker):
    """Create large dataset for load testing."""
    with django_db_blocker.unblock():
        UserFactory.create_batch(100)
        ProductFactory.create_batch(1000)
        OrderFactory.create_batch(500)
```

## Test Utilities

### Custom Assertions

```python
from django_matt.testing import assert_status, assert_json_equal, assert_created

class TestWithAssertions:
    def test_create_product(self, auth_client):
        response = auth_client.post("/api/products/", json={
            "name": "Test",
            "price": 10,
        })

        assert_created(response)  # Asserts 201
        assert_json_equal(response.json(), {
            "name": "Test",
            "price": 10,
        }, ignore=["id", "created_at"])

    def test_get_product(self, client, product_factory):
        product = product_factory()

        response = client.get(f"/api/products/{product.id}/")

        assert_status(response, 200)
```

### Database Assertions

```python
from django_matt.testing import assert_count, assert_exists

class TestDatabaseState:
    def test_create_product(self, auth_client):
        response = auth_client.post("/api/products/", json={
            "name": "New Product",
            "price": 10,
        })

        assert_created(response)
        assert_count(Product, 1)
        assert_exists(Product, name="New Product")

    def test_delete_product(self, auth_client, product_factory, user):
        product = product_factory(owner=user)

        response = auth_client.delete(f"/api/products/{product.id}/")

        assert response.status_code == 204
        assert_count(Product, 0)  # Or assert soft delete
```
