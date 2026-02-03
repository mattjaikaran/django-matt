# Feature Flags REST API

Complete REST API for managing feature flags programmatically.

## Setup

Register the flag controllers with your API:

```python
from django_matt import MattAPI
from django_matt.flags import FlagController, FlagEvaluationController

api = MattAPI()

# Full management API (CRUD + evaluation)
api.register_controller(FlagController)

# Lightweight evaluation-only API
api.register_controller(FlagEvaluationController)
```

## Authentication

The API uses your configured authentication. For production, protect the management endpoints:

```python
from django_matt.permissions import IsAdmin

class SecureFlagController(FlagController):
    permission_classes = [IsAdmin]

api.register_controller(SecureFlagController)
```

---

## Flag Management Endpoints

### List Flags

```http
GET /api/flags
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status: `active`, `inactive`, `archived` |
| `type` | string | Filter by type: `boolean`, `percentage`, `variant` |
| `search` | string | Search by key or name |
| `page` | integer | Page number (default: 1) |
| `page_size` | integer | Items per page (default: 20, max: 100) |

**Response:**

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "key": "new_checkout",
      "name": "New Checkout Flow",
      "description": "Enables the redesigned checkout experience",
      "flag_type": "boolean",
      "status": "active",
      "enabled_by_default": true,
      "rollout_percentage": 0,
      "variants": {},
      "targeting_rules": [],
      "scheduled_enable_at": null,
      "scheduled_disable_at": null,
      "metadata": {},
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z",
      "created_by_id": "123e4567-e89b-12d3-a456-426614174000",
      "is_active": true,
      "override_count": 5
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

### Create Flag

```http
POST /api/flags
```

**Request Body:**

```json
{
  "key": "new_feature",
  "name": "New Feature",
  "description": "Optional description",
  "flag_type": "boolean",
  "status": "inactive",
  "enabled_by_default": false,
  "rollout_percentage": 0,
  "variants": {
    "variants": [],
    "default_variant": null
  },
  "targeting_rules": [],
  "scheduled_enable_at": null,
  "scheduled_disable_at": null,
  "metadata": {}
}
```

**Response:** `201 Created`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "key": "new_feature",
  ...
}
```

### Get Flag

```http
GET /api/flags/{key}
```

**Response:**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "key": "new_feature",
  "name": "New Feature",
  ...
}
```

### Update Flag

```http
PUT /api/flags/{key}
PATCH /api/flags/{key}
```

**Request Body (partial for PATCH):**

```json
{
  "name": "Updated Name",
  "enabled_by_default": true,
  "status": "active"
}
```

### Delete Flag

```http
DELETE /api/flags/{key}
```

**Response:**

```json
{
  "message": "Flag 'new_feature' deleted",
  "success": true
}
```

### Enable Flag

```http
POST /api/flags/{key}/enable
```

Sets status to `active` and `enabled_by_default` to `true`.

**Response:**

```json
{
  "message": "Flag 'new_feature' enabled",
  "success": true
}
```

### Disable Flag

```http
POST /api/flags/{key}/disable
```

Sets status to `inactive` and `enabled_by_default` to `false`.

**Response:**

```json
{
  "message": "Flag 'new_feature' disabled",
  "success": true
}
```

---

## Override Endpoints

### List Overrides

```http
GET /api/flags/{key}/overrides
```

**Response:**

```json
{
  "items": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440000",
      "flag_id": "550e8400-e29b-41d4-a716-446655440000",
      "flag_key": "new_feature",
      "override_type": "user",
      "target_id": "123e4567-e89b-12d3-a456-426614174000",
      "target_value": "",
      "enabled": true,
      "variant": null,
      "expires_at": "2024-03-01T00:00:00Z",
      "created_at": "2024-01-15T10:30:00Z",
      "created_by_id": "789e4567-e89b-12d3-a456-426614174000",
      "is_active": true
    }
  ],
  "total": 5
}
```

### Create Override

```http
POST /api/flags/{key}/overrides
```

**Request Body:**

```json
{
  "override_type": "user",
  "target_id": "123e4567-e89b-12d3-a456-426614174000",
  "enabled": true,
  "variant": null,
  "expires_at": "2024-03-01T00:00:00Z"
}
```

**Override Types:**

| Type | target_id | target_value |
|------|-----------|--------------|
| `user` | User UUID | - |
| `organization` | Organization UUID | - |
| `email` | - | Email address |
| `attribute` | - | Attribute value |

### Delete Override

```http
DELETE /api/flags/{key}/overrides/{override_id}
```

**Response:**

```json
{
  "message": "Override deleted",
  "success": true
}
```

---

## Evaluation Endpoints

### Evaluate Single Flag

```http
POST /api/flags/evaluate
```

**Request Body:**

```json
{
  "flag_key": "new_feature",
  "context": {
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "organization_id": "456e7890-e89b-12d3-a456-426614174000",
    "email": "user@example.com",
    "attributes": {
      "plan": "premium",
      "country": "US"
    }
  },
  "default": false
}
```

**Response:**

```json
{
  "flag_key": "new_feature",
  "enabled": true,
  "variant": null,
  "reason": ""
}
```

### Evaluate Multiple Flags (Bulk)

```http
POST /api/flags/evaluate/bulk
```

**Request Body:**

```json
{
  "flag_keys": ["feature_a", "feature_b", "feature_c"],
  "context": {
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "attributes": {}
  },
  "include_all": false
}
```

Set `include_all: true` to evaluate all active flags.

**Response:**

```json
{
  "flags": {
    "feature_a": true,
    "feature_b": false,
    "feature_c": true
  },
  "variants": {
    "experiment_x": "treatment_a"
  }
}
```

---

## Lightweight Evaluation API

Use `FlagEvaluationController` for simple flag checks without management capabilities.

### Check Flag

```http
GET /api/flags/check/{key}
```

**Response:**

```json
{
  "enabled": true
}
```

### Get Variant

```http
GET /api/flags/variant/{key}
```

**Response:**

```json
{
  "variant": "treatment_a"
}
```

### Get All Flags

```http
GET /api/flags/all
```

**Response:**

```json
{
  "flags": {
    "feature_a": true,
    "feature_b": false,
    "feature_c": true
  }
}
```

---

## Statistics & Audit

### Get Statistics

```http
GET /api/flags/stats
```

**Response:**

```json
{
  "total_flags": 42,
  "active_flags": 28,
  "inactive_flags": 10,
  "archived_flags": 4,
  "total_overrides": 156,
  "flags_by_type": {
    "boolean": 25,
    "percentage": 12,
    "variant": 5
  },
  "recent_changes": 8
}
```

### Get Audit Logs

```http
GET /api/flags/{key}/audit-logs
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `page` | integer | Page number (default: 1) |
| `page_size` | integer | Items per page (default: 20, max: 100) |

**Response:**

```json
{
  "items": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440000",
      "flag_key": "new_feature",
      "action": "enable",
      "changes": {},
      "old_values": {"status": "inactive"},
      "new_values": {"status": "active"},
      "user_id": "123e4567-e89b-12d3-a456-426614174000",
      "ip_address": "192.168.1.1",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 25,
  "page": 1,
  "page_size": 20
}
```

---

## Error Responses

### Not Found

```json
{
  "detail": "Flag 'nonexistent' not found",
  "code": "not_found"
}
```

### Validation Error

```json
{
  "detail": "Validation error message",
  "code": "validation_error",
  "errors": []
}
```

### Key Already Exists

```json
{
  "detail": "Flag with key 'existing_key' already exists",
  "code": "key_exists"
}
```

---

## Client Libraries

### JavaScript/TypeScript

```typescript
// Using fetch
const response = await fetch('/api/flags/check/new_feature');
const { enabled } = await response.json();

if (enabled) {
  showNewFeature();
}

// Bulk evaluation
const { flags, variants } = await fetch('/api/flags/evaluate/bulk', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    flag_keys: ['feature_a', 'feature_b'],
    context: { user_id: userId }
  })
}).then(r => r.json());
```

### Python

```python
import httpx

async def get_flag(key: str, user_id: str | None = None) -> bool:
    async with httpx.AsyncClient() as client:
        if user_id:
            response = await client.post(
                f"{API_URL}/flags/evaluate",
                json={
                    "flag_key": key,
                    "context": {"user_id": user_id}
                }
            )
            return response.json()["enabled"]
        else:
            response = await client.get(f"{API_URL}/flags/check/{key}")
            return response.json()["enabled"]
```

### React Hook

```typescript
import { useState, useEffect } from 'react';

function useFeatureFlag(key: string): boolean {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    fetch(`/api/flags/check/${key}`)
      .then(r => r.json())
      .then(data => setEnabled(data.enabled));
  }, [key]);

  return enabled;
}

// Usage
function MyComponent() {
  const showNewFeature = useFeatureFlag('new_feature');

  return showNewFeature ? <NewFeature /> : <OldFeature />;
}
```

## See Also

- [Backends](backends.md) - Configure different storage backends
- [Admin](admin.md) - Manage flags via Django admin
- [Best Practices](best-practices.md) - API usage patterns
