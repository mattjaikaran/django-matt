"""Test fixtures for {{ project_name }}."""

import pytest
import pytest_asyncio
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def api_client():
    from django.test import AsyncClient

    return AsyncClient()


@pytest_asyncio.fixture
async def test_user(db):
    user = await User.objects.acreate_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )
    return user
