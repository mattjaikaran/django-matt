import pytest


@pytest.mark.django_db
class TestProjects:
    def test_create_project(self, client, auth_headers, organization, membership):
        response = client.post(
            f"/api/organizations/{organization.id}/projects",
            data={"name": "My API", "slug": "my-api"},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My API"
        assert data["environment"] == "development"

    def test_list_projects(self, client, auth_headers, organization, membership, project):
        response = client.get(
            f"/api/organizations/{organization.id}/projects",
            **auth_headers,
        )
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_get_project(self, client, auth_headers, organization, membership, project):
        response = client.get(
            f"/api/organizations/{organization.id}/projects/{project.id}",
            **auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Test Project"


@pytest.mark.django_db
class TestAPIKeys:
    def test_create_api_key(self, client, auth_headers, organization, membership, project):
        response = client.post(
            f"/api/organizations/{organization.id}/projects/{project.id}/keys",
            data={"name": "Production Key", "scopes": ["read", "write"]},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Production Key"
        assert "full_key" in data  # Only returned on creation
        assert data["full_key"].startswith("sk_live_")

    def test_list_api_keys(self, client, auth_headers, organization, membership, project):
        # Create a key first
        client.post(
            f"/api/organizations/{organization.id}/projects/{project.id}/keys",
            data={"name": "Test Key"},
            content_type="application/json",
            **auth_headers,
        )
        response = client.get(
            f"/api/organizations/{organization.id}/projects/{project.id}/keys",
            **auth_headers,
        )
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_revoke_api_key(self, client, auth_headers, organization, membership, project):
        # Create a key
        create_resp = client.post(
            f"/api/organizations/{organization.id}/projects/{project.id}/keys",
            data={"name": "Temp Key"},
            content_type="application/json",
            **auth_headers,
        )
        key_id = create_resp.json()["id"]

        # Revoke it
        response = client.delete(
            f"/api/organizations/{organization.id}/projects/{project.id}/keys/{key_id}",
            **auth_headers,
        )
        assert response.status_code == 200
