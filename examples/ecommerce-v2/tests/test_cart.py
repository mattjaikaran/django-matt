import pytest


@pytest.mark.django_db
class TestCart:
    def test_get_cart(self, client, auth_headers):
        response = client.get("/api/cart", **auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["item_count"] == 0

    def test_add_to_cart(self, client, auth_headers, product):
        response = client.post(
            "/api/cart/items",
            data={"product_id": str(product.id), "quantity": 2},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 201

        # Verify cart
        cart_resp = client.get("/api/cart", **auth_headers)
        assert cart_resp.json()["item_count"] == 1

    def test_update_cart_item(self, client, auth_headers, product):
        # Add item
        add_resp = client.post(
            "/api/cart/items",
            data={"product_id": str(product.id), "quantity": 1},
            content_type="application/json",
            **auth_headers,
        )
        item_id = add_resp.json()["id"]

        # Update quantity
        response = client.patch(
            f"/api/cart/items/{item_id}",
            data={"quantity": 5},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 200

    def test_remove_cart_item(self, client, auth_headers, product):
        # Add item
        add_resp = client.post(
            "/api/cart/items",
            data={"product_id": str(product.id), "quantity": 1},
            content_type="application/json",
            **auth_headers,
        )
        item_id = add_resp.json()["id"]

        # Remove
        response = client.delete(f"/api/cart/items/{item_id}", **auth_headers)
        assert response.status_code == 204

    def test_clear_cart(self, client, auth_headers, product):
        # Add item
        client.post(
            "/api/cart/items",
            data={"product_id": str(product.id), "quantity": 1},
            content_type="application/json",
            **auth_headers,
        )

        # Clear
        response = client.delete("/api/cart", **auth_headers)
        assert response.status_code == 204

        # Verify empty
        cart_resp = client.get("/api/cart", **auth_headers)
        assert cart_resp.json()["item_count"] == 0
