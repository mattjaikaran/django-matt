import pytest


@pytest.mark.django_db
class TestAuth:
    def test_register(self, client):
        response = client.post(
            "/api/auth/register",
            data={
                "email": "new@example.com",
                "username": "newuser",
                "password": "securepass123",
            },
            content_type="application/json",
        )
        assert response.status_code == 201
        assert response.json()["email"] == "new@example.com"

    def test_login(self, client, user):
        response = client.post(
            "/api/auth/login",
            data={"email": user.email, "password": "testpass123"},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_me(self, client, user, auth_headers):
        response = client.get("/api/auth/me", **auth_headers)
        assert response.status_code == 200
        assert response.json()["email"] == user.email
