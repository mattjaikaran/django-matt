# Test Assertions

Helpful assertion functions for API testing.

## Status Assertions

```python
from django_matt.testing import assert_status, assert_created, assert_not_found

def test_user_api():
    response = client.get("/users/")
    assert_status(response, 200)

    response = client.post("/users/", json=data)
    assert_created(response)

    response = client.get("/users/999/")
    assert_not_found(response)
```

## JSON Assertions

```python
from django_matt.testing import assert_json_equal, assert_json_contains

def test_response_data():
    response = client.get("/user/1/")

    assert_json_equal(response, {
        "id": 1,
        "email": "test@example.com",
    })

    assert_json_contains(response, {"email": "test@example.com"})
```
