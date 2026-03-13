import pytest

from apps.catalog.models import Inventory, Variant


@pytest.mark.django_db
class TestOrders:
    def test_create_order(self, client, auth_headers, product, store):
        # Create variant with inventory
        variant = Variant.objects.create(
            product=product, name="Default", sku="TEST-001", is_active=True
        )
        Inventory.objects.create(variant=variant, quantity=10)

        response = client.post(
            "/api/orders",
            data={
                "store_id": str(store.id),
                "shipping_address": "123 Main St",
                "items": [
                    {
                        "product_id": str(product.id),
                        "variant_id": str(variant.id),
                        "quantity": 2,
                    }
                ],
            },
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert len(data["items"]) == 1

    def test_list_orders(self, client, auth_headers):
        response = client.get("/api/orders", **auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_cancel_order(self, client, auth_headers, product, store):
        variant = Variant.objects.create(
            product=product, name="Default", sku="CANCEL-001", is_active=True
        )
        Inventory.objects.create(variant=variant, quantity=10)

        # Create order
        create_resp = client.post(
            "/api/orders",
            data={
                "store_id": str(store.id),
                "shipping_address": "456 Oak Ave",
                "items": [
                    {
                        "product_id": str(product.id),
                        "variant_id": str(variant.id),
                        "quantity": 1,
                    }
                ],
            },
            content_type="application/json",
            **auth_headers,
        )
        order_id = create_resp.json()["id"]

        # Cancel
        response = client.post(
            f"/api/orders/{order_id}/cancel",
            **auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
