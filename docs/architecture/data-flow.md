# Data Flow Architecture

This document describes how data flows through a django-matt application.

## Request Processing Pipeline

```mermaid
flowchart LR
    subgraph "Middleware Stack"
        M1[Security] --> M2[Session]
        M2 --> M3[Auth]
        M3 --> M4[Tenant]
        M4 --> M5[Throttle]
    end

    subgraph "Router"
        R1[URL Match] --> R2[Version Check]
        R2 --> R3[Content Negotiation]
    end

    subgraph "Handler"
        H1[Permission Check] --> H2[Input Validation]
        H2 --> H3[Controller Logic]
        H3 --> H4[Response Serialization]
    end

    REQ[Request] --> M1
    M5 --> R1
    R3 --> H1
    H4 --> RES[Response]
```

## Controller Data Flow

```mermaid
flowchart TD
    subgraph "Input"
        PATH[Path Params]
        QUERY[Query Params]
        BODY[Request Body]
        FILES[Uploaded Files]
    end

    subgraph "Validation"
        PSCHEMA[Path Schema]
        QSCHEMA[Query Schema]
        BSCHEMA[Body Schema]
        FVALID[File Validator]
    end

    subgraph "Processing"
        CTRL[Controller]
        SVC[Service Layer]
        REPO[Repository/ORM]
    end

    subgraph "Output"
        RSCHEMA[Response Schema]
        SERIAL[Serializer]
        FORMAT[Formatter]
    end

    PATH --> PSCHEMA
    QUERY --> QSCHEMA
    BODY --> BSCHEMA
    FILES --> FVALID

    PSCHEMA --> CTRL
    QSCHEMA --> CTRL
    BSCHEMA --> CTRL
    FVALID --> CTRL

    CTRL --> SVC
    SVC --> REPO
    REPO --> SVC
    SVC --> CTRL

    CTRL --> RSCHEMA
    RSCHEMA --> SERIAL
    SERIAL --> FORMAT
    FORMAT --> RES[Response]
```

## Database Query Optimization

```mermaid
flowchart TD
    QUERY[Build QuerySet] --> ANALYZE{Auto-Optimize?}

    ANALYZE -->|Yes| DETECT[Detect Relations]
    ANALYZE -->|No| EXEC[Execute Query]

    DETECT --> FK{Foreign Keys?}
    FK -->|Yes| SELECT[Add select_related]
    FK -->|No| M2M

    SELECT --> M2M{Many-to-Many?}
    M2M -->|Yes| PREFETCH[Add prefetch_related]
    M2M -->|No| EXEC

    PREFETCH --> EXEC
    EXEC --> CACHE{Cache Enabled?}

    CACHE -->|Yes| CHECK{In Cache?}
    CACHE -->|No| DB[(Database)]

    CHECK -->|Yes| RETURN[Return Cached]
    CHECK -->|No| DB

    DB --> STORE[Store in Cache]
    STORE --> RETURN
```

## Caching Strategy

```mermaid
flowchart LR
    subgraph "Cache Layers"
        L1[Response Cache<br/>Full responses]
        L2[Query Cache<br/>QuerySet results]
        L3[Object Cache<br/>Model instances]
    end

    subgraph "Invalidation"
        SIG[Model Signals]
        MAN[Manual Invalidation]
        TTL[TTL Expiry]
    end

    REQ[Request] --> L1
    L1 -->|Miss| L2
    L2 -->|Miss| L3
    L3 -->|Miss| DB[(Database)]

    DB --> L3
    L3 --> L2
    L2 --> L1
    L1 --> RES[Response]

    SIG --> L3
    MAN --> L2
    TTL --> L1
```

## Multi-Tenant Data Isolation

```mermaid
flowchart TD
    REQ[Request] --> AUTH[Authenticate User]
    AUTH --> TENANT[Resolve Tenant]

    TENANT --> CTX[Set Tenant Context]
    CTX --> QUERY[Build Query]

    QUERY --> FILTER{Auto-Filter?}
    FILTER -->|Yes| ADD[Add tenant_id filter]
    FILTER -->|No| MANUAL[Manual filtering]

    ADD --> EXEC[Execute Query]
    MANUAL --> EXEC

    EXEC --> CHECK{Belongs to Tenant?}
    CHECK -->|Yes| RETURN[Return Data]
    CHECK -->|No| ERROR[403 Forbidden]
```

## Serialization Flow

```mermaid
flowchart LR
    subgraph "Input"
        JSON[JSON Body]
        FORM[Form Data]
        MP[Multipart]
    end

    subgraph "Parsing"
        JP[JSON Parser]
        FP[Form Parser]
        MPP[Multipart Parser]
    end

    subgraph "Validation"
        PYDANTIC[Pydantic Schema]
    end

    subgraph "Output"
        ORJSON[orjson]
        MSGPACK[MessagePack]
        XML[XML]
        CSV[CSV]
    end

    JSON --> JP
    FORM --> FP
    MP --> MPP

    JP --> PYDANTIC
    FP --> PYDANTIC
    MPP --> PYDANTIC

    PYDANTIC --> MODEL[Domain Model]
    MODEL --> RSCHEMA[Response Schema]

    RSCHEMA --> NEG{Content Negotiation}
    NEG -->|application/json| ORJSON
    NEG -->|application/msgpack| MSGPACK
    NEG -->|application/xml| XML
    NEG -->|text/csv| CSV
```

## Related Documentation

- [Caching](../performance/caching.md)
- [Query Optimization](../performance/optimization.md)
- [Content Negotiation](../features/content-negotiation.md)
- [Multi-tenancy](../multitenancy/overview.md)
