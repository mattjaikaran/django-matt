import pytest
from django.test import AsyncClient


@pytest.fixture
async def client():
    return AsyncClient()


@pytest.fixture
async def admin_user(db):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return await User.objects.acreate_superuser(
        username="admin", email="admin@example.com", password="adminpass123"
    )


@pytest.fixture
async def auth_client(db, admin_user):
    client = AsyncClient()
    client.force_login(admin_user)
    return client, admin_user
