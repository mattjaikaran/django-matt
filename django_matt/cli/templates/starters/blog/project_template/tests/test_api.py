"""Basic smoke tests for the blog API."""

import pytest


@pytest.mark.django_db
class TestAuthAPI:
    async def test_register_user(self, client):
        response = await client.post(
            "/api/auth/register",
            data={
                "username": "newuser",
                "email": "new@example.com",
                "password": "testpass123",
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert "access" in data
        assert "refresh" in data

    async def test_login(self, client, user):
        response = await client.post(
            "/api/auth/login",
            data={"email": "test@example.com", "password": "testpass123"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert "access" in data
        assert data["user"]["username"] == "testuser"

    async def test_login_invalid(self, client):
        response = await client.post(
            "/api/auth/login",
            data={"email": "nope@example.com", "password": "wrong"},
            content_type="application/json",
        )
        assert response.status_code == 401


@pytest.mark.django_db
class TestPostAPI:
    async def test_list_posts_public(self, client, published_post):
        response = await client.get("/api/posts/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    async def test_get_post(self, client, published_post):
        response = await client.get(f"/api/posts/{published_post.slug}")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Post"

    async def test_create_post_requires_auth(self, client):
        response = await client.post(
            "/api/posts/",
            data={"title": "Unauthorized", "content": "Should fail"},
            content_type="application/json",
        )
        assert response.status_code in (401, 403)

    async def test_my_posts_requires_auth(self, client):
        response = await client.get("/api/posts/my")
        assert response.status_code == 401

    async def test_list_tags(self, client):
        response = await client.get("/api/tags/")
        assert response.status_code == 200


@pytest.mark.django_db
class TestCommentAPI:
    async def test_create_comment(self, client, published_post):
        response = await client.post(
            f"/api/comments/?post={published_post.id}",
            data={
                "author_name": "Commenter",
                "author_email": "comment@example.com",
                "body": "Great post!",
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["body"] == "Great post!"
