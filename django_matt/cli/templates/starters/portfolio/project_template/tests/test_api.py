"""Smoke tests for the portfolio API."""

from django.test import AsyncClient
import pytest


@pytest.mark.django_db
class TestProjectAPI:
    async def test_list_projects(self, client):
        response = await client.get("/api/projects/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_create_project_requires_auth(self, client):
        response = await client.post(
            "/api/projects/",
            data={"title": "Test", "slug": "test", "description": "desc"},
            content_type="application/json",
        )
        assert response.status_code == 401

    async def test_create_and_get_project(self, auth_client):
        client, admin = auth_client
        resp = await client.post(
            "/api/projects/",
            data={"title": "My Project", "slug": "my-project", "description": "A project"},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "My Project"

        # Public read
        public = await AsyncClient().get(f"/api/projects/{data['slug']}")
        assert public.status_code == 200


@pytest.mark.django_db
class TestContactAPI:
    async def test_submit_contact(self, client):
        response = await client.post(
            "/api/contact/",
            data={
                "name": "John",
                "email": "john@example.com",
                "message": "Hello!",
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    async def test_list_messages_requires_auth(self, client):
        response = await client.get("/api/contact/")
        assert response.status_code == 401
