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
        data = response.json()
        assert data["email"] == "new@example.com"
        assert data["username"] == "newuser"

    def test_register_duplicate_email(self, client, user):
        response = client.post(
            "/api/auth/register",
            data={
                "email": user.email,
                "username": "different",
                "password": "securepass123",
            },
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_login(self, client, user):
        response = client.post(
            "/api/auth/login",
            data={"email": user.email, "password": "testpass123"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_invalid_credentials(self, client, user):
        response = client.post(
            "/api/auth/login",
            data={"email": user.email, "password": "wrongpass"},
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_me(self, client, user, auth_headers):
        response = client.get("/api/auth/me", **auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == user.email

    def test_me_unauthenticated(self, client):
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_update_me(self, client, user, auth_headers):
        response = client.patch(
            "/api/auth/me",
            data={"first_name": "Updated", "bio": "Hello world"},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Updated"
        assert data["bio"] == "Hello world"

    def test_change_password(self, client, user, auth_headers):
        response = client.post(
            "/api/auth/change-password",
            data={
                "current_password": "testpass123",
                "new_password": "newpass12345",
            },
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 200

        # Login with new password
        response = client.post(
            "/api/auth/login",
            data={"email": user.email, "password": "newpass12345"},
            content_type="application/json",
        )
        assert response.status_code == 200
