import pytest
from django.test import AsyncClient


@pytest.fixture
async def client():
    return AsyncClient()


@pytest.fixture
async def user(db):
    from {{ project_name }}_app.users.models import User

    return await User.objects.acreate_user(
        username="testuser", email="test@example.com", password="testpass123"
    )


@pytest.fixture
async def auth_client(db, user):
    client = AsyncClient()
    client.force_login(user)
    return client, user


@pytest.fixture
async def published_post(db, user):
    from {{ project_name }}_app.posts.models import Post

    return await Post.objects.acreate(
        title="Test Post",
        slug="test-post",
        content="Hello world",
        excerpt="Test excerpt",
        status="published",
        author=user,
    )
