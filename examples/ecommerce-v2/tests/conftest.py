import pytest
from django.test import Client

from apps.catalog.models import Category, Product
from apps.stores.models import Store
from apps.users.models import User


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="test@example.com",
        username="testuser",
        password="testpass123",
        first_name="Test",
        last_name="User",
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        email="other@example.com",
        username="otheruser",
        password="testpass123",
    )


@pytest.fixture
def store(user):
    return Store.objects.create(
        owner=user,
        name="Test Store",
        slug="test-store",
        description="A test store",
    )


@pytest.fixture
def category(db):
    return Category.objects.create(
        name="Electronics",
        slug="electronics",
    )


@pytest.fixture
def product(store, category):
    return Product.objects.create(
        store=store,
        category=category,
        name="Test Product",
        slug="test-product",
        description="A great product",
        price="29.99",
    )


@pytest.fixture
def auth_headers(client, user):
    response = client.post(
        "/api/auth/login",
        data={"email": user.email, "password": "testpass123"},
        content_type="application/json",
    )
    token = response.json()["access_token"]
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}
