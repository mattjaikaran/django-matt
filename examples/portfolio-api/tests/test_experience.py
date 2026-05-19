import pytest


@pytest.mark.django_db
class TestExperience:
    def test_list_experience(self, client, sample_experience):
        response = client.get("/api/experience")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert any(e["company"] == "Test Corp" for e in data["items"])

    def test_list_experience_no_auth_required(self, client, sample_experience):
        # No auth headers — should still return 200
        response = client.get("/api/experience")
        assert response.status_code == 200

    def test_create_experience_requires_auth(self, client):
        response = client.post(
            "/api/experience",
            data={
                "company": "New Co",
                "role": "Engineer",
                "start_date": "2023-01-01",
                "description": "Did stuff",
            },
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_create_experience(self, client, auth_headers):
        response = client.post(
            "/api/experience",
            data={
                "company": "New Co",
                "role": "Staff Engineer",
                "location": "Remote",
                "start_date": "2023-06-01",
                "is_current": True,
                "description": "Built great things.",
                "tech_used": ["Python", "Rust"],
                "order": 1,
            },
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["company"] == "New Co"
        assert data["role"] == "Staff Engineer"
        assert data["is_current"] is True

    def test_get_experience(self, client, sample_experience):
        response = client.get(f"/api/experience/{sample_experience.id}")
        assert response.status_code == 200
        assert response.json()["company"] == "Test Corp"

    def test_get_experience_not_found(self, client):
        response = client.get("/api/experience/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    def test_update_experience(self, client, auth_headers, sample_experience):
        response = client.patch(
            f"/api/experience/{sample_experience.id}",
            data={"role": "Principal Engineer"},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["role"] == "Principal Engineer"

    def test_delete_experience(self, client, auth_headers, sample_experience):
        response = client.delete(
            f"/api/experience/{sample_experience.id}",
            **auth_headers,
        )
        assert response.status_code in (200, 204)
