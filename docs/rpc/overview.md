# RPC Client

Django Matt provides type-safe RPC clients for consuming APIs built with the framework. Generate Python or TypeScript clients from your API definition, or use dynamic proxies for zero-config consumption.

## Overview

```mermaid
flowchart LR
    subgraph "Client Types"
        RPC[RPCClient<br/>Base HTTP client]
        TYPED[TypedRPCClient<br/>Route-aware from API instance]
        PROXY[RPCProxy<br/>Dynamic attribute-based]
    end

    subgraph "Auth Strategies"
        BEARER[BearerAuth]
        APIKEY[APIKeyAuth]
        BASIC[BasicAuth]
        COMP[CompositeAuth]
    end

    subgraph "Code Generation"
        PY[Python Client]
        TS[TypeScript Client]
    end

    RPC --> TYPED
    RPC --> PROXY
    RPC --> BEARER
    RPC --> APIKEY
    RPC --> BASIC
    TYPED --> PY
    TYPED --> TS
```

## Quick Start

```python
from django_matt.rpc import RPCClient, BearerAuth

async with RPCClient(
    "https://api.example.com",
    auth=BearerAuth("my-token"),
) as client:
    users = await client.request("GET", "/api/users/")
    user = await client.request("POST", "/api/users/", data={"name": "Alice"})
```

## RPCClient

The base HTTP client with retry logic, error mapping, and Pydantic response parsing. Supports both `httpx` and `aiohttp` as transport backends (auto-detects which is installed, preferring httpx).

### Constructor

```python
RPCClient(
    base_url: str,
    auth: AuthStrategy | None = None,
    timeout: float = 30.0,
    max_retries: int = 3,
    retry_backoff: float = 0.5,
    headers: dict[str, str] | None = None,
)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `base_url` | required | API base URL (trailing slash stripped) |
| `auth` | `None` | Authentication strategy |
| `timeout` | `30.0` | Request timeout in seconds |
| `max_retries` | `3` | Max retry attempts for connection/timeout errors |
| `retry_backoff` | `0.5` | Base backoff delay (exponential: `0.5 * 2^attempt`) |
| `headers` | `None` | Extra default headers merged into every request |

### Making Requests

```python
result = await client.request(
    method="GET",
    path="/api/users/",
    params={"page": 1},
    response_model=UserSchema,  # auto-validates response
)
```

The `request` method:
- Serializes `data` (Pydantic model or dict) with orjson
- Retries on `RPCConnectionError` and `RPCTimeoutError` with exponential backoff
- Maps HTTP error responses to typed exceptions
- Parses responses with `response_model.model_validate()` when provided
- Handles both single objects and lists automatically

### Context Manager

```python
async with RPCClient("https://api.example.com") as client:
    result = await client.request("GET", "/health/")
# Connection cleaned up automatically
```

## TypedRPCClient

Extends `RPCClient` with route awareness built from a `MattAPI` instance. Enables calling endpoints by method name.

```python
from django_matt.rpc import TypedRPCClient, BearerAuth
from myapp.api import api

async with TypedRPCClient(
    "https://api.example.com",
    api=api,
    auth=BearerAuth("token"),
) as client:
    # Call by method name (resolved from API route map)
    users = await client.call("list_users", response_model=UserSchema)

    # Call by qualified name
    user = await client.call("UserController.create_user", data={"name": "Bob"})

    # List all available methods
    print(client.get_available_methods())
```

The client builds a route map by introspecting:
1. Top-level `api.routes` (function-based endpoints)
2. Controller methods with `_route_info` attributes (class-based endpoints)

## RPCProxy

Dynamic proxy client that maps Python attribute access to API namespaces. Routes are derived from controller prefixes.

```python
from django_matt.rpc import RPCProxy, BearerAuth
from myapp.api import api

async with RPCProxy(
    api=api,
    base_url="https://api.example.com",
    auth=BearerAuth("token"),
) as proxy:
    # Namespace maps to controller prefix
    users = await proxy.users.list()
    user = await proxy.users.create(name="Alice", email="alice@example.com")
    detail = await proxy.users.read(id="123")
```

### Path Parameter Substitution

The proxy handles Django-style path parameters automatically:

```python
# For a route like /users/<int:id>/
user = await proxy.users.read(id=42)
# Calls GET /users/42/
```

### Accessing the Underlying Client

```python
proxy.client  # Returns the RPCClient instance
```

## Authentication Strategies

All strategies implement the `AuthStrategy` protocol:

```python
class AuthStrategy(Protocol):
    def apply(self, headers: dict[str, str]) -> dict[str, str]: ...
```

### BearerAuth

```python
from django_matt.rpc import BearerAuth

auth = BearerAuth("my-jwt-token")
# Sets: Authorization: Bearer my-jwt-token
```

### APIKeyAuth

```python
from django_matt.rpc import APIKeyAuth

auth = APIKeyAuth("sk_live_abc123")
# Sets: X-API-Key: sk_live_abc123

# Custom header name
auth = APIKeyAuth("sk_live_abc123", header="Authorization")
```

### BasicAuth

```python
from django_matt.rpc import BasicAuth

auth = BasicAuth("username", "password")
# Sets: Authorization: Basic dXNlcm5hbWU6cGFzc3dvcmQ=
```

### CompositeAuth

Combine multiple strategies (applied in order):

```python
from django_matt.rpc import CompositeAuth, BearerAuth, APIKeyAuth

auth = CompositeAuth(
    BearerAuth("token"),
    APIKeyAuth("key", header="X-Tenant-Key"),
)
# Sets both Authorization and X-Tenant-Key headers
```

### Custom Strategy

```python
class OAuth2PKCE:
    def __init__(self, access_token: str):
        self.access_token = access_token

    def apply(self, headers: dict[str, str]) -> dict[str, str]:
        headers["Authorization"] = f"Bearer {self.access_token}"
        headers["X-Auth-Method"] = "pkce"
        return headers
```

## Error Handling

All RPC errors extend `RPCError`:

```
RPCError (base)
  RPCConnectionError  — 503, connection failed
  RPCTimeoutError     — 504, request timed out
  RPCAuthError        — 401, authentication failed
  RPCNotFoundError    — 404, not found
  RPCValidationError  — 422, validation error (includes .errors list)
```

Error mapping from HTTP status codes:

| Status Code | Exception |
|-------------|-----------|
| 401 | `RPCAuthError` |
| 404 | `RPCNotFoundError` |
| 422 | `RPCValidationError` |
| 504 | `RPCTimeoutError` |
| Other 4xx/5xx | `RPCError` |

```python
from django_matt.rpc import RPCError, RPCAuthError, RPCValidationError

try:
    result = await client.request("POST", "/api/users/", data=payload)
except RPCAuthError:
    # Token expired, refresh and retry
    pass
except RPCValidationError as e:
    print(e.errors)  # [{"loc": ["name"], "msg": "required"}]
except RPCError as e:
    print(e.status_code, e.message, e.detail)
```

## Client Code Generation

Generate standalone client code from your API definition.

### Python Client

```python
from django_matt.rpc import generate_python_client
from myapp.api import api

code = generate_python_client(api, class_name="MyAppClient")
# Write to file
with open("client.py", "w") as f:
    f.write(code)
```

Generated output:

```python
from django_matt.rpc.auth import AuthStrategy
from django_matt.rpc.client import RPCClient

class MyAppClient:
    def __init__(self, base_url: str, auth: AuthStrategy | None = None, **kwargs):
        self._client = RPCClient(base_url, auth=auth, **kwargs)

    async def list_users(self) -> list[UserSchema]:
        return await self._client.request("GET", "/api/users/")

    async def create_user(self, data: UserCreateSchema) -> UserSchema:
        return await self._client.request("POST", "/api/users/", data=data)

    async def close(self) -> None:
        await self._client.close()

    async def __aenter__(self) -> MyAppClient:
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()
```

### TypeScript Client

```python
from django_matt.rpc import generate_typescript_client
from myapp.api import api

code = generate_typescript_client(api, class_name="APIClient")
```

Generated output:

```typescript
// Auto-generated by django_matt.rpc.generator
// Do not edit manually

export interface UserSchema {
  id: string;
  name: string;
  email: string;
}

export interface UserCreateSchema {
  name: string;
  email: string;
}

export class APIClient {
  private baseUrl: string;
  private headers: Record<string, string>;

  constructor(baseUrl: string, headers: Record<string, string> = {}) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.headers = { "Content-Type": "application/json", ...headers };
  }

  async listUsers(): Promise<UserSchema[]> {
    return this.request<UserSchema[]>("GET", "/api/users/");
  }

  async createUser(data: UserCreateSchema): Promise<UserSchema> {
    return this.request<UserSchema>("POST", "/api/users/", data);
  }
}
```

The generator:
- Extracts routes from both function endpoints and controller methods
- Introspects type hints for parameter and return types
- Generates Pydantic model interfaces for TypeScript
- Converts Python types to TypeScript equivalents (`str` -> `string`, `list[X]` -> `X[]`, `dict[K, V]` -> `Record<K, V>`)
- Converts snake_case method names to camelCase for TypeScript

### CLI Generation

```python
from django_matt.rpc.cli import generate_rpc_client

# Generate and write to file
generate_rpc_client(api, lang="python", output="generated/client.py")
generate_rpc_client(api, lang="typescript", output="generated/client.ts")

# Generate and get code string
code = generate_rpc_client(api, lang="python", class_name="MyClient")
```

## Configuration

### Transport Backend

The client auto-detects `httpx` (preferred) or `aiohttp`. Install one:

```bash
uv add httpx    # recommended
# or
uv add aiohttp
```

### Retry Behavior

Retries apply only to `RPCConnectionError` and `RPCTimeoutError`. Client errors (4xx) and server errors (5xx) are raised immediately.

Retry delay: `retry_backoff * 2^attempt` (0.5s, 1s, 2s by default).

## Best Practices

1. **Use `TypedRPCClient` or `RPCProxy`** over raw `RPCClient` for type safety and route resolution
2. **Always use context managers** (`async with`) to ensure connections are cleaned up
3. **Set `response_model`** on requests to get validated Pydantic objects back
4. **Generate clients for consumers** — ship the generated Python/TypeScript client alongside your API
5. **Use `CompositeAuth`** when your API requires multiple auth headers (e.g., JWT + tenant key)
6. **Handle `RPCValidationError` specifically** to surface field-level errors to users
