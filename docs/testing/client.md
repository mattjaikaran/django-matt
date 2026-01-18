# Test Client

API testing utilities.

## APITestClient

```python
from django_matt.testing import APITestClient

class TestUserAPI:
    def setup_method(self):
        self.client = APITestClient(api)

    def test_list_users(self):
        response = self.client.get("/users/")
        assert response.status_code == 200

    def test_create_user(self):
        response = self.client.post("/users/", json={
            "email": "test@example.com",
            "password": "secret123",
        })
        assert response.status_code == 201
```

## AsyncAPITestClient

```python
from django_matt.testing import AsyncAPITestClient

class TestUserAPI:
    async def test_list_users(self):
        async with AsyncAPITestClient(api) as client:
            response = await client.get("/users/")
            assert response.status_code == 200
```

## Authentication

```python
def test_authenticated_request(self):
    self.client.authenticate(user)
    response = self.client.get("/me/")
    assert response.status_code == 200
```
