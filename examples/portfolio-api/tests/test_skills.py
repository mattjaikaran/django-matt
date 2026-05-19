import pytest


@pytest.mark.django_db
class TestSkills:
    def test_list_skills(self, client, sample_skill):
        response = client.get("/api/skills")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    def test_list_skills_filter_by_category(self, client, sample_skill):
        response = client.get("/api/skills?category=backend")
        assert response.status_code == 200
        for item in response.json()["items"]:
            assert item["category"] == "backend"

    def test_list_skills_filter_no_match(self, client, sample_skill):
        response = client.get("/api/skills?category=mobile")
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_create_skill_requires_auth(self, client):
        response = client.post(
            "/api/skills",
            data={"name": "Go", "category": "backend", "level": 3},
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_create_skill(self, client, auth_headers):
        response = client.post(
            "/api/skills",
            data={"name": "Go", "category": "backend", "level": 3, "icon": "go", "order": 10},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Go"
        assert data["category"] == "backend"
        assert data["level"] == 3

    def test_get_skill(self, client, sample_skill):
        response = client.get(f"/api/skills/{sample_skill.id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Python"

    def test_get_skill_not_found(self, client):
        response = client.get("/api/skills/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    def test_update_skill(self, client, auth_headers, sample_skill):
        response = client.patch(
            f"/api/skills/{sample_skill.id}",
            data={"level": 4},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["level"] == 4

    def test_delete_skill(self, client, auth_headers, sample_skill):
        response = client.delete(f"/api/skills/{sample_skill.id}", **auth_headers)
        assert response.status_code in (200, 204)
