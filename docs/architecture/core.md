# Core Components Architecture

The core module provides the fundamental building blocks for API development.

## Component Hierarchy

```mermaid
classDiagram
    class MattAPI {
        +routers: list
        +middleware: list
        +register_controller()
        +get()
        +post()
        +put()
        +delete()
    }

    class Router {
        +prefix: str
        +tags: list
        +routes: list
        +add_route()
    }

    class APIController {
        +permission_classes: list
        +throttle_classes: list
        +get_permissions()
    }

    class CRUDController {
        +model: Model
        +create_schema: Schema
        +update_schema: Schema
        +response_schema: Schema
        +list()
        +create()
        +read()
        +update()
        +delete()
    }

    class Schema {
        +model_config: ConfigDict
        +model_validate()
        +model_dump()
    }

    class ModelSchema {
        +Meta: class
        +from_orm()
    }

    MattAPI --> Router
    Router --> APIController
    APIController <|-- CRUDController
    Schema <|-- ModelSchema
    CRUDController --> ModelSchema
```

## Route Registration Flow

```mermaid
sequenceDiagram
    participant D as Developer
    participant A as MattAPI
    participant R as Router
    participant O as OpenAPI

    D->>A: @api.get("/users")
    A->>R: Register route
    R->>R: Store path, method, handler
    R->>O: Generate schema
    O->>O: Extract params, body, response

    D->>A: @api.controller("/products")
    A->>R: Register controller routes
    R->>R: Scan controller methods
    R->>O: Generate schemas for all
```

## Controller Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Initialize: Request arrives
    Initialize --> Authenticate: Load controller
    Authenticate --> CheckPermissions: Validate auth
    CheckPermissions --> Throttle: Check permissions
    Throttle --> ValidateInput: Check rate limits
    ValidateInput --> Execute: Validate schemas
    Execute --> Serialize: Run handler
    Serialize --> [*]: Return response

    Authenticate --> Error: Auth failed
    CheckPermissions --> Error: Permission denied
    Throttle --> Error: Rate limited
    ValidateInput --> Error: Validation failed
    Execute --> Error: Handler error
    Error --> [*]
```

## Schema Validation

```mermaid
flowchart TD
    INPUT[Raw Input] --> PARSE[Parse JSON/Form]
    PARSE --> SCHEMA[Pydantic Schema]

    SCHEMA --> FIELDS{Validate Fields}
    FIELDS -->|Pass| VALIDATORS[Run Validators]
    FIELDS -->|Fail| ERROR[ValidationError]

    VALIDATORS --> CUSTOM{Custom Validators}
    CUSTOM -->|Pass| MODEL[Create Model Instance]
    CUSTOM -->|Fail| ERROR

    MODEL --> HANDLER[Pass to Handler]
    ERROR --> RESPONSE[422 Response]
```

## Error Handling

```mermaid
flowchart TD
    ERROR[Exception Raised] --> TYPE{Error Type?}

    TYPE -->|ValidationError| V422[422 Unprocessable]
    TYPE -->|AuthError| V401[401 Unauthorized]
    TYPE -->|PermissionError| V403[403 Forbidden]
    TYPE -->|NotFoundError| V404[404 Not Found]
    TYPE -->|APIError| CUSTOM[Custom Status]
    TYPE -->|Exception| V500[500 Server Error]

    V422 --> FORMAT[Format Response]
    V401 --> FORMAT
    V403 --> FORMAT
    V404 --> FORMAT
    CUSTOM --> FORMAT
    V500 --> LOG[Log Error]
    LOG --> FORMAT

    FORMAT --> JSON[JSON Response]
```

## Code Examples

### Basic Controller

```python
from django_matt import MattAPI
from django_matt.core import APIController

api = MattAPI()

@api.controller("/users", tags=["Users"])
class UserController(APIController):

    @api.get("/")
    async def list(self, request):
        users = await User.objects.all()
        return [UserSchema.from_orm(u) for u in users]

    @api.get("/{user_id}")
    async def detail(self, request, user_id: int):
        user = await User.objects.aget(id=user_id)
        return UserSchema.from_orm(user)
```

### CRUD Controller

```python
from django_matt.core import CRUDController

@api.controller("/products", tags=["Products"])
class ProductController(CRUDController):
    model = Product
    create_schema = ProductCreate
    update_schema = ProductUpdate
    response_schema = ProductSchema

    # All CRUD methods auto-generated
    # Override for customization:
    async def list(self, request, **filters):
        qs = self.get_queryset().filter(is_active=True)
        return await self.paginate(qs)
```

### Schema Definition

```python
from django_matt.core import Schema, ModelSchema

class UserCreate(Schema):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(max_length=100)

class UserSchema(ModelSchema):
    class Meta:
        model = User
        fields = ["id", "email", "name", "created_at"]
```

## Related Documentation

- [Routing](../core/routing.md)
- [Controllers](../core/controllers.md)
- [Schemas](../core/schemas.md)
- [Errors](../core/errors.md)
