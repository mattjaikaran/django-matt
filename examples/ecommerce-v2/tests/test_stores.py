import pytest


@pytest.mark.django_db
class TestStores:
    def test_create_store(self, client, auth_headers):
        response = client.post(
            "/api/stores",
            data={"name": "My Shop", "slug": "my-shop", "description": "A cool shop"},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Shop"
        assert data["slug"] == "my-shop"

    def test_list_stores(self, client, store):
        response = client.get("/api/stores")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    def test_get_store(self, client, store):
        response = client.get(f"/api/stores/{store.id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Test Store"

    def test_update_store(self, client, auth_headers, store):
        response = client.patch(
            f"/api/stores/{store.id}",
            data={"name": "Updated Store"},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Store"

    def test_update_store_not_owner(self, client, other_user, store):
        # Login as other user
        login_resp = client.post(
            "/api/auth/login",
            data={"email": other_user.email, "password": "testpass123"},
            content_type="application/json",
        )
        headers = {"HTTP_AUTHORIZATION": f"Bearer {login_resp.json()['access_token']}"}
        response = client.patch(
            f"/api/stores/{store.id}",
            data={"name": "Hijacked"},
            content_type="application/json",
            **headers,
        )
        assert response.status_code == 403
