import pytest

from apps.todos.models import Todo


@pytest.mark.django_db
class TestTodoLists:
    def test_create_todo_list(self, client, auth_headers, organization, membership):
        response = client.post(
            f"/api/organizations/{organization.id}/lists",
            data={"name": "My List", "description": "Test list"},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My List"

    def test_list_todo_lists(self, client, auth_headers, organization, membership, todo_list):
        response = client.get(
            f"/api/organizations/{organization.id}/lists",
            **auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_get_todo_list(self, client, auth_headers, organization, membership, todo_list):
        response = client.get(
            f"/api/organizations/{organization.id}/lists/{todo_list.id}",
            **auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Test List"

    def test_update_todo_list(self, client, auth_headers, organization, membership, todo_list):
        response = client.patch(
            f"/api/organizations/{organization.id}/lists/{todo_list.id}",
            data={"name": "Updated List"},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated List"

    def test_delete_todo_list(self, client, auth_headers, organization, membership, todo_list):
        response = client.delete(
            f"/api/organizations/{organization.id}/lists/{todo_list.id}",
            **auth_headers,
        )
        assert response.status_code == 204


@pytest.mark.django_db
class TestTodos:
    def test_create_todo(self, client, auth_headers, organization, membership, todo_list):
        response = client.post(
            f"/api/organizations/{organization.id}/todos",
            data={
                "title": "New Todo",
                "description": "Do this thing",
                "priority": "high",
                "todo_list_id": str(todo_list.id),
            },
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "New Todo"
        assert data["priority"] == "high"
        assert data["status"] == "pending"

    def test_create_todo_default_list(self, client, auth_headers, organization, membership):
        response = client.post(
            f"/api/organizations/{organization.id}/todos",
            data={"title": "Quick Todo"},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["title"] == "Quick Todo"

    def test_list_todos(self, client, auth_headers, organization, membership, todo):
        response = client.get(
            f"/api/organizations/{organization.id}/todos",
            **auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_list_todos_filter_status(self, client, auth_headers, organization, membership, todo):
        response = client.get(
            f"/api/organizations/{organization.id}/todos?status=pending",
            **auth_headers,
        )
        assert response.status_code == 200
        for item in response.json()["items"]:
            assert item["status"] == "pending"

    def test_list_todos_filter_priority(self, client, auth_headers, organization, membership, todo):
        response = client.get(
            f"/api/organizations/{organization.id}/todos?priority=medium",
            **auth_headers,
        )
        assert response.status_code == 200
        for item in response.json()["items"]:
            assert item["priority"] == "medium"

    def test_list_todos_search(self, client, auth_headers, organization, membership, todo):
        response = client.get(
            f"/api/organizations/{organization.id}/todos?search=Test",
            **auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] >= 1

    def test_list_todos_pagination(self, client, auth_headers, organization, membership, todo):
        response = client.get(
            f"/api/organizations/{organization.id}/todos?limit=1&offset=0",
            **auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 1
        assert data["offset"] == 0

    def test_get_todo(self, client, auth_headers, organization, membership, todo):
        response = client.get(
            f"/api/organizations/{organization.id}/todos/{todo.id}",
            **auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Test Todo"

    def test_update_todo(self, client, auth_headers, organization, membership, todo):
        response = client.patch(
            f"/api/organizations/{organization.id}/todos/{todo.id}",
            data={"title": "Updated Todo", "priority": "high"},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Todo"
        assert data["priority"] == "high"

    def test_complete_todo(self, client, auth_headers, organization, membership, todo):
        response = client.patch(
            f"/api/organizations/{organization.id}/todos/{todo.id}",
            data={"status": "done"},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "done"
        assert data["completed_at"] is not None

    def test_uncomplete_todo(self, client, auth_headers, organization, membership, todo):
        # First complete it
        todo.status = "done"
        todo.save()
        # Then uncomplete
        response = client.patch(
            f"/api/organizations/{organization.id}/todos/{todo.id}",
            data={"status": "pending"},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert data["completed_at"] is None

    def test_delete_todo(self, client, auth_headers, organization, membership, todo):
        response = client.delete(
            f"/api/organizations/{organization.id}/todos/{todo.id}",
            **auth_headers,
        )
        assert response.status_code == 204
        assert not Todo.objects.filter(id=todo.id).exists()

    def test_org_isolation(self, client, other_user, organization, membership, todo):
        """Todos from one org are not visible to non-members."""
        from apps.organizations.models import Organization

        # Create another org and login as other_user (not a member of first org)
        Organization.objects.create(name="Other Org", slug="other-org")

        # Login as other_user
        from apps.users.models import User

        other = User.objects.create_user(
            email="isolated@example.com", username="isolated", password="pass12345"
        )
        login_resp = client.post(
            "/api/auth/login",
            data={"email": other.email, "password": "pass12345"},
            content_type="application/json",
        )
        token = login_resp.json()["access_token"]
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        response = client.get(
            f"/api/organizations/{organization.id}/todos",
            **headers,
        )
        # Should be forbidden - not a member
        assert response.status_code == 403
