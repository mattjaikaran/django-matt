import pytest


@pytest.mark.django_db
class TestCategories:
    def test_list_categories(self, client, category):
        response = client.get("/api/categories")
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_create_category(self, client, auth_headers):
        response = client.post(
            "/api/categories",
            data={"name": "Books", "slug": "books"},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["name"] == "Books"


@pytest.mark.django_db
class TestProducts:
    def test_list_products(self, client, product):
        response = client.get("/api/products")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    def test_list_products_filter_category(self, client, product, category):
        response = client.get(f"/api/products?category={category.id}")
        assert response.status_code == 200
        for item in response.json()["items"]:
            assert item["category_id"] == str(category.id)

    def test_list_products_filter_price(self, client, product):
        response = client.get("/api/products?min_price=20&max_price=40")
        assert response.status_code == 200
        assert response.json()["total"] >= 1

    def test_list_products_search(self, client, product):
        response = client.get("/api/products?search=Test")
        assert response.status_code == 200
        assert response.json()["total"] >= 1

    def test_create_product(self, client, auth_headers, store, category):
        response = client.post(
            "/api/products",
            data={
                "store_id": str(store.id),
                "category_id": str(category.id),
                "name": "New Product",
                "slug": "new-product",
                "price": "49.99",
            },
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["name"] == "New Product"

    def test_get_product(self, client, product):
        response = client.get(f"/api/products/{product.id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Test Product"
