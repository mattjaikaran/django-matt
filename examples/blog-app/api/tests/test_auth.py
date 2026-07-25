import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestAuthAPI:
    def test_register_user(self, client):
        response = client.post(
            "/api/auth/signup",
            data={
                "email": "newuser@example.com",
                "username": "newuser",
                "password": "securepass123",
            },
            content_type="application/json",
        )
        assert response.status_code in (200, 201)
        assert User.objects.filter(email="newuser@example.com").exists()

    def test_login_valid(self, client, db):
        User.objects.create_user(
            username="logintest",
            email="login@example.com",
            password="testpass123",
        )
        response = client.post(
            "/api/auth/login",
            data={"email": "login@example.com", "password": "testpass123"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert "access" in data

    def test_login_invalid_credentials(self, client, db):
        response = client.post(
            "/api/auth/login",
            data={"email": "nobody@example.com", "password": "wrong"},
            content_type="application/json",
        )
        assert response.status_code in (400, 401, 403)

    def test_me_requires_auth(self, client):
        response = client.get("/api/auth/me")
        assert response.status_code in (401, 403)
