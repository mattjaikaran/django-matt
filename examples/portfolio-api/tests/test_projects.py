import pytest


@pytest.mark.django_db
class TestProjects:
    def test_list_projects(self, client, sample_project):
        response = client.get("/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert any(p["slug"] == "test-project" for p in data["items"])

    def test_list_projects_filter_featured(self, client, sample_project):
        response = client.get("/api/projects?featured=true")
        assert response.status_code == 200
        for item in response.json()["items"]:
            assert item["featured"] is True

    def test_create_project_requires_auth(self, client):
        response = client.post(
            "/api/projects",
            data={
                "title": "New Project",
                "slug": "new-project",
                "description": "A brand new project",
            },
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_create_project(self, client, auth_headers):
        response = client.post(
            "/api/projects",
            data={
                "title": "New Project",
                "slug": "new-project",
                "description": "A brand new project",
                "tech_stack": ["Python"],
            },
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "New Project"
        assert data["slug"] == "new-project"

    def test_create_project_duplicate_slug(self, client, auth_headers, sample_project):
        response = client.post(
            "/api/projects",
            data={
                "title": "Duplicate",
                "slug": "test-project",
                "description": "Oops",
            },
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 422

    def test_get_project_by_slug(self, client, sample_project):
        response = client.get(f"/api/projects/{sample_project.slug}")
        assert response.status_code == 200
        assert response.json()["title"] == "Test Project"

    def test_get_project_not_found(self, client):
        response = client.get("/api/projects/does-not-exist")
        assert response.status_code == 404

    def test_update_project(self, client, auth_headers, sample_project):
        response = client.patch(
            f"/api/projects/{sample_project.slug}",
            data={"title": "Updated Title"},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Updated Title"

    def test_delete_project(self, client, auth_headers, sample_project):
        response = client.delete(
            f"/api/projects/{sample_project.slug}",
            **auth_headers,
        )
        assert response.status_code in (200, 204)

    def test_delete_project_requires_auth(self, client, sample_project):
        response = client.delete(f"/api/projects/{sample_project.slug}")
        assert response.status_code == 401
