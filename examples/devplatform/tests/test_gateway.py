import pytest

from apps.gateway.models import RequestLog


@pytest.mark.django_db
class TestGateway:
    def test_list_request_logs(self, client, auth_headers, organization, membership, project):
        # Create some logs
        RequestLog.objects.create(
            project=project,
            method="GET",
            path="/api/users",
            status_code=200,
            response_time_ms=45,
        )
        RequestLog.objects.create(
            project=project,
            method="POST",
            path="/api/users",
            status_code=201,
            response_time_ms=120,
        )

        response = client.get(
            f"/api/organizations/{organization.id}/projects/{project.id}/logs",
            **auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    def test_filter_logs_by_method(self, client, auth_headers, organization, membership, project):
        RequestLog.objects.create(
            project=project, method="GET", path="/test", status_code=200, response_time_ms=10
        )
        RequestLog.objects.create(
            project=project, method="POST", path="/test", status_code=201, response_time_ms=20
        )

        response = client.get(
            f"/api/organizations/{organization.id}/projects/{project.id}/logs?method=GET",
            **auth_headers,
        )
        assert response.status_code == 200
        for item in response.json()["items"]:
            assert item["method"] == "GET"

    def test_error_logs(self, client, auth_headers, organization, membership, project):
        RequestLog.objects.create(
            project=project, method="GET", path="/ok", status_code=200, response_time_ms=10
        )
        RequestLog.objects.create(
            project=project,
            method="GET",
            path="/fail",
            status_code=500,
            response_time_ms=5,
            error_message="Internal error",
        )

        response = client.get(
            f"/api/organizations/{organization.id}/projects/{project.id}/logs/errors",
            **auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status_code"] == 500
