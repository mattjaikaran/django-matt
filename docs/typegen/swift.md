# Swift Generation

Generate Swift Codable structs from Django models.

## Quick Start

```bash
python manage.py sync_types --target swift --output ios/Generated
```

## Generated Output

```swift
// User.swift
struct User: Codable {
    let id: Int
    let email: String
    let firstName: String
    let lastName: String
    let createdAt: Date
}

// APIClient.swift
class APIClient {
    func listUsers() async throws -> [User] {
        return try await request(.get, "/users/")
    }

    func getUser(id: Int) async throws -> User {
        return try await request(.get, "/users/\(id)")
    }
}
```

## Configuration

```python
# settings.py
DJANGO_MATT = {
    "TYPEGEN": {
        "SWIFT_OUTPUT_DIR": "ios/Generated",
    },
}
```
