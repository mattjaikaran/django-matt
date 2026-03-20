import pytest


@pytest.mark.django_db
class TestOrganizations:
    def test_create_organization(self, client, user, auth_headers):
        response = client.post(
            "/api/organizations",
            data={"name": "New Org", "slug": "new-org"},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Org"
        assert data["slug"] == "new-org"

    def test_list_organizations(self, client, user, auth_headers, membership):
        response = client.get("/api/organizations", **auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["role"] == "owner"

    def test_get_organization(self, client, user, auth_headers, organization, membership):
        response = client.get(
            f"/api/organizations/{organization.id}",
            **auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Test Org"

    def test_update_organization(self, client, user, auth_headers, organization, membership):
        response = client.patch(
            f"/api/organizations/{organization.id}",
            data={"name": "Updated Org"},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Org"

    def test_delete_organization(self, client, user, auth_headers, organization, membership):
        response = client.delete(
            f"/api/organizations/{organization.id}",
            **auth_headers,
        )
        assert response.status_code == 204

    def test_list_members(self, client, user, auth_headers, organization, membership):
        response = client.get(
            f"/api/organizations/{organization.id}/members",
            **auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["role"] == "owner"
