import pytest


@pytest.mark.django_db
class TestReviews:
    def test_create_review(self, client, auth_headers, product):
        response = client.post(
            f"/api/products/{product.id}/reviews",
            data={
                "product_id": str(product.id),
                "rating": 5,
                "title": "Great product!",
                "body": "Really loved it.",
            },
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["rating"] == 5
        assert data["title"] == "Great product!"

    def test_list_reviews(self, client, auth_headers, product):
        # Create a review first
        client.post(
            f"/api/products/{product.id}/reviews",
            data={"product_id": str(product.id), "rating": 4, "title": "Good"},
            content_type="application/json",
            **auth_headers,
        )

        response = client.get(f"/api/products/{product.id}/reviews")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    def test_review_summary(self, client, auth_headers, product):
        client.post(
            f"/api/products/{product.id}/reviews",
            data={"product_id": str(product.id), "rating": 5, "title": "Perfect"},
            content_type="application/json",
            **auth_headers,
        )

        response = client.get(f"/api/products/{product.id}/reviews/summary")
        assert response.status_code == 200
        data = response.json()
        assert "average_rating" in data
        assert "total_reviews" in data

    def test_duplicate_review(self, client, auth_headers, product):
        # First review
        client.post(
            f"/api/products/{product.id}/reviews",
            data={"product_id": str(product.id), "rating": 4, "title": "Good"},
            content_type="application/json",
            **auth_headers,
        )
        # Duplicate
        response = client.post(
            f"/api/products/{product.id}/reviews",
            data={"product_id": str(product.id), "rating": 3, "title": "Changed mind"},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 400
