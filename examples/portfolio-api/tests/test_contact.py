import pytest


@pytest.mark.django_db
class TestContact:
    def test_submit_contact_no_auth_required(self, client):
        response = client.post(
            "/api/contact",
            data={
                "name": "Jane Smith",
                "email": "jane@example.com",
                "subject": "Collaboration",
                "message": "Let's work together!",
            },
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Jane Smith"
        assert data["email"] == "jane@example.com"
        assert data["is_read"] is False

    def test_submit_contact_minimal(self, client):
        response = client.post(
            "/api/contact",
            data={
                "name": "Anonymous",
                "email": "anon@example.com",
                "message": "Hello!",
            },
            content_type="application/json",
        )
        assert response.status_code == 201
        assert response.json()["subject"] == ""

    def test_submit_contact_invalid_email(self, client):
        response = client.post(
            "/api/contact",
            data={
                "name": "Bad Email",
                "email": "not-an-email",
                "message": "Hi!",
            },
            content_type="application/json",
        )
        assert response.status_code == 422

    def test_list_messages_requires_auth(self, client):
        response = client.get("/api/contact")
        assert response.status_code == 401

    def test_list_messages(self, client, auth_headers, sample_message):
        response = client.get("/api/contact", **auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert any(m["name"] == "John Doe" for m in data["items"])

    def test_mark_read_requires_auth(self, client, sample_message):
        response = client.patch(f"/api/contact/{sample_message.id}/read")
        assert response.status_code == 401

    def test_mark_read(self, client, auth_headers, sample_message):
        assert sample_message.is_read is False
        response = client.patch(
            f"/api/contact/{sample_message.id}/read",
            **auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["is_read"] is True

    def test_mark_read_not_found(self, client, auth_headers):
        response = client.patch(
            "/api/contact/00000000-0000-0000-0000-000000000000/read",
            **auth_headers,
        )
        assert response.status_code == 404
