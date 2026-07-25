# Visual Diagrams Index

This page collects all architectural diagrams for django-matt.

## System Overview

```mermaid
graph TB
    subgraph "Client Layer"
        WEB[Web App]
        MOBILE[Mobile App]
        CLI[CLI]
        SSE_CLIENT[SSE Client]
    end

    subgraph "API Layer"
        API[DjangoMattAPI]
        AUTH[Auth]
        MW[Middleware]
        INTERCEPT[Interceptors]
        EXCFILTER[Exception Filters]
        STREAM[Streaming/SSE]
    end

    subgraph "Service Layer"
        MSG[Messaging]
        NOTIF[Notifications]
        EMAIL[Email]
        BILLING[Billing]
        EVENTS[Event Bus]
        CQRS[CQRS]
        RPC[RPC Client]
    end

    subgraph "Infrastructure Layer"
        SECRETS[Secrets]
        MODULES[Module System]
        INTRO[Introspection]
        OBSERVE[Auto-Instrumentation]
        TASKS_NATIVE[Native Task Engine]
        AUDITS[AI-Assisted Audits]
    end

    subgraph "Data Layer"
        DB[(PostgreSQL)]
        CACHE[(Redis)]
        STORAGE[S3/Storage]
    end

    WEB --> API
    MOBILE --> API
    CLI --> API
    SSE_CLIENT --> STREAM

    API --> AUTH
    AUTH --> MW
    MW --> INTERCEPT
    INTERCEPT --> EXCFILTER
    EXCFILTER --> MSG
    EXCFILTER --> NOTIF
    EXCFILTER --> EMAIL
    EXCFILTER --> BILLING

    MSG --> EVENTS
    BILLING --> EVENTS
    EVENTS --> CQRS

    MSG --> DB
    NOTIF --> DB
    EMAIL --> DB
    BILLING --> DB
    CQRS --> DB

    MSG --> CACHE
    NOTIF --> CACHE
    EVENTS --> CACHE

    SECRETS --> AUTH
    MODULES --> API
    OBSERVE --> API
    INTRO --> MODULES
    RPC --> API
    TASKS_NATIVE --> EVENTS
    AUDITS --> INTRO
```

## Request Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant M as Middleware
    participant A as Auth
    participant H as Handler
    participant S as Service
    participant D as Database

    C->>M: HTTP Request
    M->>A: Authenticate
    A->>H: Authorized
    H->>S: Business Logic
    S->>D: Query
    D->>S: Data
    S->>H: Result
    H->>C: Response
```

## Authentication Methods

```mermaid
flowchart TD
    AUTH{Authentication}

    AUTH --> JWT[JWT Tokens]
    AUTH --> SESSION[Sessions]
    AUTH --> APIKEY[API Keys]
    AUTH --> OAUTH[OAuth 2.0]
    AUTH --> PASSKEY[Passkeys]
    AUTH --> SSO[Enterprise SSO]

    OAUTH --> GOOGLE[Google]
    OAUTH --> GITHUB[GitHub]
    OAUTH --> APPLE[Apple]

    SSO --> SAML[SAML 2.0]
    SSO --> OIDC[OpenID Connect]
```

## Messaging Architecture

```mermaid
flowchart LR
    subgraph "Transport"
        WS[WebSocket]
        POLL[HTTP Polling]
    end

    subgraph "Services"
        CONV[Conversations]
        MSG[Messages]
        PRES[Presence]
    end

    subgraph "Storage"
        DB[(Database)]
        CACHE[(Cache)]
    end

    WS --> CONV
    WS --> MSG
    WS --> PRES
    POLL --> CONV
    POLL --> MSG

    MSG --> DB
    CONV --> DB
    PRES --> CACHE
```

## Notification Channels

```mermaid
flowchart LR
    NOTIF[Notification] --> CHANNELS{Channels}

    CHANNELS --> INAPP[In-App]
    CHANNELS --> EMAIL[Email]
    CHANNELS --> PUSH[Push]
    CHANNELS --> SMS[SMS]
    CHANNELS --> WEBHOOK[Webhook]

    PUSH --> FCM[Firebase]
    PUSH --> APNS[Apple]
    PUSH --> WEBPUSH[Web Push]
```

## Email Service

```mermaid
flowchart TB
    APP[Application] --> SVC[EmailService]

    SVC --> PROV{Provider}

    PROV --> SMTP[SMTP]
    PROV --> SES[Amazon SES]
    PROV --> SG[SendGrid]
    PROV --> MG[Mailgun]
    PROV --> CONSOLE[Console]
```

## Data Model - Core

```mermaid
erDiagram
    User ||--o{ Organization : belongs_to
    Organization ||--o{ Team : has
    Team ||--o{ Membership : has
    User ||--o{ Membership : has

    User {
        uuid id PK
        string email
        string password_hash
        boolean is_active
    }

    Organization {
        uuid id PK
        string name
        string slug
    }

    Team {
        uuid id PK
        uuid org_id FK
        string name
    }

    Membership {
        uuid id PK
        uuid user_id FK
        uuid team_id FK
        string role
    }
```

## Data Model - Messaging

```mermaid
erDiagram
    Conversation ||--o{ Message : contains
    Conversation ||--o{ Member : has
    Message ||--o{ Attachment : has
    Message ||--o{ Reaction : has

    Conversation {
        uuid id PK
        string type
        string name
    }

    Message {
        uuid id PK
        uuid conversation_id FK
        uuid sender_id FK
        text content
        datetime created_at
    }

    Attachment {
        uuid id PK
        uuid message_id FK
        string filename
        string url
    }
```

## Data Model - Billing

```mermaid
erDiagram
    Customer ||--o{ Subscription : has
    Customer ||--o{ Invoice : has
    Subscription }o--|| Product : for
    Product ||--o{ Price : has

    Customer {
        uuid id PK
        uuid user_id FK
        string provider_id
    }

    Subscription {
        uuid id PK
        uuid customer_id FK
        string status
        datetime current_period_end
    }

    Product {
        uuid id PK
        string name
        string provider_id
    }

    Price {
        uuid id PK
        uuid product_id FK
        int amount
        string interval
    }
```

## Deployment Architecture

```mermaid
flowchart TB
    subgraph "Load Balancer"
        LB[Caddy/Nginx]
    end

    subgraph "Application"
        APP1[Django App 1]
        APP2[Django App 2]
        WORKER[Celery Worker]
        BEAT[Celery Beat]
    end

    subgraph "Data"
        PG[(PostgreSQL)]
        REDIS[(Redis)]
        S3[S3 Storage]
    end

    LB --> APP1
    LB --> APP2

    APP1 --> PG
    APP2 --> PG
    APP1 --> REDIS
    APP2 --> REDIS

    WORKER --> PG
    WORKER --> REDIS
    BEAT --> REDIS
```

## Component System

```mermaid
flowchart LR
    subgraph "Definition"
        COMP[Components]
        THEME[Theme]
    end

    subgraph "Renderers"
        JSON[JSON]
        HTML[HTML]
        REACT[React]
    end

    subgraph "Output"
        API[API Response]
        SSR[Server HTML]
        PROPS[React Props]
    end

    COMP --> JSON
    COMP --> HTML
    COMP --> REACT
    THEME --> HTML
    THEME --> REACT

    JSON --> API
    HTML --> SSR
    REACT --> PROPS
```

## Dependency Injection

```mermaid
flowchart TB
    subgraph "Registration"
        REG[container.register]
        INST[register_instance]
        FACT[register_factory]
    end

    subgraph "Lifetimes"
        SING[Singleton<br/>App lifetime]
        SCOPED[Scoped<br/>Request lifetime]
        TRANS[Transient<br/>Always new]
    end

    subgraph "Resolution"
        RES[container.resolve]
        DEP[Depends marker]
        AUTO[Auto-injection]
    end

    REG --> SING & SCOPED & TRANS
    INST --> SING
    FACT --> SING & SCOPED & TRANS
    SING & SCOPED & TRANS --> RES
    RES --> DEP --> AUTO
```

## Content Negotiation

```mermaid
flowchart LR
    subgraph "Input"
        ACCEPT[Accept Header]
        QUERY[?format=xml]
        SUFFIX[/users.csv]
    end

    subgraph "Negotiator"
        NEG[ContentNegotiator]
    end

    subgraph "Renderers"
        JSON[JSON]
        XML[XML]
        CSV[CSV]
        YAML[YAML]
        MSG[MessagePack]
    end

    ACCEPT & QUERY & SUFFIX --> NEG
    NEG --> JSON & XML & CSV & YAML & MSG
```

## RBAC Hierarchy

```mermaid
flowchart TB
    SUPER[Super Admin<br/>level: 100] --> ADMIN
    ADMIN[Admin<br/>level: 80] --> MANAGER
    MANAGER[Manager<br/>level: 60] --> MEMBER
    MEMBER[Member<br/>level: 40] --> GUEST
    GUEST[Guest<br/>level: 20]

    SUPER -.-> |"*"| ALL[All Permissions]
    ADMIN -.-> |"users:*, admin:*"| ADMIN_PERMS[Admin Perms]
    MANAGER -.-> |"users:read, team:*"| MGR_PERMS[Manager Perms]
```

## AI/RAG Pipeline

```mermaid
flowchart TB
    subgraph "Input"
        DOCS[Documents]
        QUERY[User Query]
    end

    subgraph "Processing"
        SPLIT[Text Splitter]
        EMBED[Embeddings]
        STORE[Vector Store]
        RETRIEVE[Retrieval]
    end

    subgraph "Generation"
        LLM[LLM Provider]
        RESP[Response]
    end

    DOCS --> SPLIT --> EMBED --> STORE
    QUERY --> EMBED --> RETRIEVE
    STORE --> RETRIEVE
    RETRIEVE --> LLM --> RESP
```

## Audit Trail

```mermaid
sequenceDiagram
    participant U as User
    participant M as Middleware
    participant V as View
    participant A as AuditLog
    participant DB as Database

    U->>M: Request
    M->>M: Set audit context (IP, User-Agent)
    M->>V: Handle request
    V->>DB: Model.save()
    DB->>A: Signal: post_save
    A->>A: Create audit entry
    A->>DB: Save AuditLog
    V->>U: Response
```

## Request Pipeline

```mermaid
flowchart LR
    REQ[Request] --> GMW[Global Middleware]
    GMW --> RSM[Route-Scoped Middleware]
    RSM --> INT_PRE[Interceptors: Before]
    INT_PRE --> CTRL[Controller]
    CTRL --> SVC[Service]
    SVC --> CTRL
    CTRL --> INT_POST[Interceptors: After]
    INT_POST --> EF[Exception Filters]
    EF --> RESP[Response]

    SVC -.->|error| EF
    CTRL -.->|error| EF
```

## Event-Driven Architecture

```mermaid
flowchart TB
    subgraph "Write Path"
        CMD[Command] --> CMDBUS[Command Bus]
        CMDBUS --> HANDLER[Command Handler]
        HANDLER --> DB[(Database)]
        HANDLER --> DE[Domain Events]
    end

    subgraph "Event Distribution"
        DE --> EBUS[Event Bus]
        EBUS --> SUB1[Subscriber: Notifications]
        EBUS --> SUB2[Subscriber: Analytics]
        EBUS --> SUB3[Subscriber: Projections]
        EBUS --> SUB4[Subscriber: Webhooks]
    end

    subgraph "Read Path"
        QUERY[Query] --> QBUS[Query Bus]
        QBUS --> QHANDLER[Query Handler]
        QHANDLER --> READDB[(Read Model)]
        SUB3 --> READDB
    end
```

## Module System

```mermaid
flowchart TB
    subgraph "Discovery"
        APPS[INSTALLED_APPS] --> REG[Module Registry]
        EXPLICIT[Explicit Registration] --> REG
    end

    subgraph "Resolution"
        REG --> DEP[Dependency Resolution]
        DEP --> TOPO[Topological Sort]
    end

    subgraph "Loading"
        TOPO --> INIT[on_init hooks]
        INIT --> READY[on_ready hooks]
        READY --> RUNNING[Running]
        RUNNING -.-> SHUTDOWN[on_shutdown hooks]
    end

    subgraph "Exports"
        RUNNING --> ROUTES[Routes]
        RUNNING --> MIDDLEWARE[Middleware]
        RUNNING --> EVENTS[Event Handlers]
        RUNNING --> CONFIG[Configuration]
    end
```

## Slim Mode

```mermaid
flowchart TB
    STARTUP[Application Startup] --> MODE{MATT_MODE}

    MODE -->|full| FULL[Full Mode]
    MODE -->|slim| SLIM[Slim Mode]
    MODE -->|minimal| MIN[Minimal Mode]

    subgraph "Full Mode — All Modules"
        FULL --> F_CORE[Core + Router + Auth]
        FULL --> F_SVC[Messaging + Notifications + Email + Billing]
        FULL --> F_INFRA[Events + CQRS + Modules + Observability]
        FULL --> F_EXT[AI + GraphQL + WebSockets + Analytics]
    end

    subgraph "Slim Mode — Referenced Only"
        SLIM --> S_CORE[Core + Router + Auth]
        SLIM --> S_USED[Only imported modules loaded]
        SLIM --> S_SKIP[Unreferenced modules skipped]
    end

    subgraph "Minimal Mode — Bare Minimum"
        MIN --> M_CORE[Core + Router + Auth]
        MIN --> M_NOTE[All other modules opt-in]
    end
```

## Streaming / SSE

```mermaid
sequenceDiagram
    participant C as Client
    participant S as SSE Endpoint
    participant E as Event Bus
    participant SVC as Service

    C->>S: GET /events (Accept: text/event-stream)
    S->>C: HTTP 200 (chunked)

    loop While connected
        SVC->>E: emit(OrderCreated)
        E->>S: notify subscriber
        S->>C: event: order.created\ndata: {...}\n\n
    end

    S->>C: keepalive (: ping)
    C--xS: disconnect
    S->>S: cleanup
```

## Secrets Management

```mermaid
flowchart LR
    subgraph "Backends"
        ENV[Environment Vars]
        VAULT[HashiCorp Vault]
        AWS[AWS Secrets Manager]
        GCP[GCP Secret Manager]
    end

    subgraph "Secrets Manager"
        SM[SecretStore]
        CACHE_S[Local Cache]
        ROTATE[Rotation Monitor]
    end

    subgraph "Consumers"
        AUTH[Auth / JWT Keys]
        DB_CONF[DB Credentials]
        API_KEYS[External API Keys]
    end

    ENV & VAULT & AWS & GCP --> SM
    SM --> CACHE_S
    ROTATE --> SM
    CACHE_S --> AUTH & DB_CONF & API_KEYS
```

## Module Ecosystem

```mermaid
graph TB
    subgraph "Core"
        API[api.py<br/>DjangoMattAPI]
        ROUTER[core/router]
        CTRL[core/controller]
        SCHEMA[core/schema]
        ERRORS[core/errors]
    end

    subgraph "Auth & Access"
        JWT[auth/jwt]
        OAUTH[auth/oauth]
        SSO[auth/sso]
        PASSKEYS[auth/passkeys]
        APIKEYS[auth/api_keys]
        RBAC[auth/rbac]
        PERMS[permissions]
    end

    subgraph "Request Pipeline"
        MW[middleware]
        INTERCEPT[interceptors]
        EXCFILTER[exceptions]
        THROTTLE[throttling]
        NEGOTIATE[negotiation]
        VERSION[versioning]
        DI_MOD[di]
    end

    subgraph "Data & Query"
        VIEWS[views]
        PAGINATE[pagination]
        FILTER[filtering]
        SERIAL[serialization]
        DB[db]
        AUDIT_MOD[audit]
    end

    subgraph "Communication"
        MSG_MOD[messaging]
        NOTIF_MOD[notifications]
        EMAIL_MOD[email]
        WS[websockets]
        STREAM_MOD[streaming]
        EVENTS_MOD[events]
    end

    subgraph "Business Logic"
        BILLING_MOD[billing]
        TENANT[multitenancy]
        FLAGS_MOD[flags]
        ANALYTICS_MOD[analytics]
        EXPERIMENTS_MOD[experiments]
        TASKS_MOD[tasks]
        TASKS_NATIVE_MOD[tasks_native]
        AUDITS_MOD[audits]
    end

    subgraph "AI & ML"
        AI[ai]
        ML[ml]
        GRAPHQL_MOD[graphql]
    end

    subgraph "Frontend & Codegen"
        HTMX_MOD[htmx]
        COMPONENTS_MOD[components]
        TYPEGEN[typegen]
        CODEGEN[codegen]
        RPC_MOD[rpc]
        SDKGEN[sdkgen]
        INERTIA_MOD[inertia]
        LIVEWIRE_MOD[livewire]
        UNPOLY_MOD[unpoly]
        VITE_MOD[vite]
        TAILWIND_MOD[tailwind]
        FORMS_MOD[forms]
        PAGES_MOD[pages]
    end

    subgraph "DevOps & Infra"
        DEPLOY[deployment]
        CLI_MOD[cli]
        OBSERVE_MOD[observability]
        SECRETS_MOD[secrets]
        FILES[files]
        INTRO_MOD[introspection]
        CONFIG[config]
        SERVERS_MOD[servers]
        WASM_MOD[wasm]
    end

    subgraph "Architecture"
        CQRS_MOD[cqrs]
        MODULES_MOD[modules]
        LOADER[loader]
        SLIM[slim]
        PLUGINS_MOD[plugins]
        ADVISOR_MOD[advisor]
    end

    subgraph "Data & Query Extended"
        BATCH_MOD[batch]
        PREFETCH_MOD[prefetch]
        SERVICES_MOD[services]
        RESOURCES_MOD[resources]
        SCHEMA_DESIGNER[schema_designer]
        CODEMODS_MOD[codemods]
        MIGRATION_TOOLS_MOD[migration_tools]
    end

    API --> ROUTER
    ROUTER --> CTRL
    CTRL --> SCHEMA
    CTRL --> ERRORS
    CTRL --> PERMS
    CTRL --> DI_MOD

    API --> MW
    MW --> INTERCEPT
    INTERCEPT --> EXCFILTER
    MW --> THROTTLE
    MW --> NEGOTIATE
    MW --> VERSION

    CTRL --> VIEWS
    VIEWS --> PAGINATE
    VIEWS --> FILTER
    VIEWS --> SERIAL
    VIEWS --> DB

    JWT --> RBAC
    OAUTH --> JWT
    SSO --> JWT
    PASSKEYS --> JWT
    APIKEYS --> JWT

    EVENTS_MOD --> CQRS_MOD
    MSG_MOD --> WS
    MSG_MOD --> EVENTS_MOD
    NOTIF_MOD --> EMAIL_MOD
    STREAM_MOD --> EVENTS_MOD

    MODULES_MOD --> LOADER
    LOADER --> SLIM
    OBSERVE_MOD --> INTRO_MOD
    SECRETS_MOD --> CONFIG
    PLUGINS_MOD --> MODULES_MOD
    ADVISOR_MOD --> INTRO_MOD
    SDKGEN --> TYPEGEN
    MIGRATION_TOOLS_MOD --> DB
    BATCH_MOD --> TASKS_NATIVE_MOD
    PREFETCH_MOD --> VIEWS
    SERVERS_MOD --> API
    CODEMODS_MOD --> CODEGEN
    SCHEMA_DESIGNER --> DB
```

## Rust Acceleration Map

```mermaid
graph LR
    subgraph "Request Hot Path"
        direction LR
        TCP["TCP Accept<br/>🐍 Python"]
        HTTP["HTTP Parse<br/>🐍 ASGI Server"]
        ROUTE["Route Match<br/>🦀 Rust 4x"]
        HEADERS["Header Parse<br/>🦀 Rust"]
        AUTH_R["JWT Verify<br/>🦀 Rust 1.5x"]
        QS["Query Parse<br/>🦀 Rust 4x"]
        HANDLER["Handler<br/>🐍 Python"]
        ORM["ORM Query<br/>🐍 Python"]
        SERIALIZE["JSON Serialize<br/>🦀 Rust 1.9x"]
        RESP["Response<br/>🐍 Python"]
    end

    TCP --> HTTP --> ROUTE --> HEADERS --> AUTH_R --> QS --> HANDLER --> ORM --> SERIALIZE --> RESP

    style ROUTE fill:#dea584,stroke:#b7472a
    style HEADERS fill:#dea584,stroke:#b7472a
    style AUTH_R fill:#dea584,stroke:#b7472a
    style QS fill:#dea584,stroke:#b7472a
    style SERIALIZE fill:#dea584,stroke:#b7472a

    style TCP fill:#306998,stroke:#FFD43B,color:#fff
    style HTTP fill:#306998,stroke:#FFD43B,color:#fff
    style HANDLER fill:#306998,stroke:#FFD43B,color:#fff
    style ORM fill:#306998,stroke:#FFD43B,color:#fff
    style RESP fill:#306998,stroke:#FFD43B,color:#fff
```

## Stage 17: Native Tasks & AI Audits

Stage 17 adds two zero-dependency infrastructure layers: a native task engine that works without Celery (17A) and an AI-assisted audit pipeline that surfaces security, performance, and maintainability issues directly inside the Django management CLI (17B).

### Task Lifecycle

```mermaid
flowchart LR
    DEC["@task decorator"] --> ENQUEUE[task.delay / apply_async]
    ENQUEUE --> VALID[Pydantic payload validation]
    VALID --> BACKEND{Backend}
    BACKEND -->|Django 6.0+| NATIVE[Django Native Queue]
    BACKEND -->|Django 5.x| CELERY[Celery Broker]
    BACKEND -->|Dramatiq| DRAMATIQ[Dramatiq Queue]
    NATIVE & CELERY & DRAMATIQ --> WORKER[Worker]
    WORKER -->|success| HIST[Task History]
    WORKER -->|failure| RETRY[Retry w/ backoff]
    RETRY -->|max retries| DLQ[Dead Letter Queue]
    HIST & DLQ --> DASH[Unfold Admin Dashboard]
```

### Audit Pipeline

```mermaid
flowchart LR
    CMD["python manage.py matt_audit"] --> FW[Audit Framework]
    FW --> SEC[Security Auditor]
    FW --> PERF[Performance Auditor]
    FW --> BUNDLE[Bundle Analyzer]
    FW --> BP[Best Practices Auditor]
    SEC & PERF & BUNDLE & BP --> FINDINGS[AuditFindings]
    FINDINGS --> SARIF[SARIF — GitHub Code Scanning]
    FINDINGS --> JSON_O[JSON]
    FINDINGS --> MD_O[Markdown]
    FINDINGS --> TXT_O[Text]
```

## Native Task System (Stage 17A)

```mermaid
flowchart TB
    subgraph "Task Definition"
        TASK[@task decorator]
        PERIODIC[@periodic_task]
        PAYLOAD[Pydantic Payload]
    end

    subgraph "Enqueueing"
        DELAY[task.delay]
        APPLY[task.apply_async]
        VALIDATE[Payload Validation]
    end

    subgraph "Backend Detection"
        AUTO{Auto-detect}
        AUTO -->|Django 6.0+| NATIVE[Django Native Backend]
        AUTO -->|Django 5.x| CELERY[Celery Backend]
        AUTO -->|Dramatiq| DRAMATIQ[Dramatiq Backend]
        AUTO -->|Sync| SYNC[Sync Backend]
    end

    subgraph "Execution"
        QUEUE[(Task Queue)]
        WORKER[Worker Process]
        RETRY[Retry Policy]
        DLQ[Dead Letter Queue]
    end

    subgraph "Monitoring"
        ADMIN[Unfold Admin Dashboard]
        METRICS[Queue Metrics]
        HISTORY[Task History]
    end

    TASK --> DELAY
    PERIODIC --> SCHEDULER[DB Scheduler]
    PAYLOAD --> VALIDATE
    DELAY --> VALIDATE
    VALIDATE --> AUTO
    NATIVE --> QUEUE
    CELERY --> QUEUE
    QUEUE --> WORKER
    WORKER -->|success| HISTORY
    WORKER -->|failure| RETRY
    RETRY -->|max retries| DLQ
    ADMIN --> QUEUE
    ADMIN --> HISTORY
    ADMIN --> DLQ
    METRICS --> ADMIN
```

## AI-Assisted Audit System (Stage 17B)

```mermaid
flowchart TB
    subgraph "Audit Categories"
        SEC[Security Auditor]
        PERF[Performance Auditor]
        BP[Best Practices Auditor]
        MAINT[Maintainability Auditor]
    end

    subgraph "Audit Framework"
        RUN[run_audit]
        LEVEL{Audit Level}
        LEVEL -->|relaxed| CRIT[Critical Only]
        LEVEL -->|standard| STD[Critical + Important]
        LEVEL -->|strict| ALL[All Issues]
        LEVEL -->|paranoid| PARANOID[Security Focus]
    end

    subgraph "Findings"
        FINDING[AuditFinding]
        REPORT[AuditReport]
    end

    subgraph "Output Formats"
        TXT[Text]
        JSON_OUT[JSON]
        MD[Markdown]
        SARIF[SARIF<br/>GitHub Code Scanning]
    end

    SEC --> RUN
    PERF --> RUN
    BP --> RUN
    MAINT --> RUN
    RUN --> LEVEL
    CRIT --> FINDING
    STD --> FINDING
    ALL --> FINDING
    FINDING --> REPORT
    REPORT --> TXT
    REPORT --> JSON_OUT
    REPORT --> MD
    REPORT --> SARIF
```

## Bundle Size Analyzer

```mermaid
flowchart LR
    subgraph "Analysis"
        SCAN[Module Scanner]
        IMPORT[Import Profiler]
        DEPS[Dependency Analyzer]
    end

    subgraph "Detection"
        UNUSED[Unused Modules]
        HEAVY[Heavy Imports]
        STARTUP[Startup Time]
    end

    subgraph "Optimization"
        SLIM[SlimConfig Generator]
        LAZY[Lazy Loading Suggestions]
        TREE[Tree Shaking Opportunities]
    end

    SCAN --> UNUSED
    IMPORT --> HEAVY
    IMPORT --> STARTUP
    DEPS --> TREE
    UNUSED --> SLIM
    HEAVY --> LAZY
    TREE --> SLIM
```

## LLM Audit Integration

```mermaid
sequenceDiagram
    participant U as Developer
    participant CLI as matt_audit CLI
    participant CTX as Context Generator
    participant LLM as Claude/GPT
    participant PARSE as Response Parser

    U->>CLI: matt_audit context --for claude
    CLI->>CTX: Generate project context
    CTX->>CTX: Gather settings, models, routes, patterns
    CTX->>U: Markdown/XML context file

    U->>LLM: Paste context + prompt
    LLM->>LLM: Analyze codebase
    LLM->>U: Structured findings

    U->>CLI: Parse LLM response
    CLI->>PARSE: Extract findings
    PARSE->>CLI: AuditFinding objects
    CLI->>U: Formatted report
```

## MCP Tool Integration

```mermaid
flowchart TB
    subgraph "MCP Tools"
        TOOL1[run_django_matt_audit]
        TOOL2[analyze_bundle_size]
        TOOL3[get_audit_prompt]
        TOOL4[generate_project_context]
        TOOL5[fix_audit_finding]
    end

    subgraph "AI Agents"
        CURSOR[Cursor IDE]
        CLAUDE[Claude Code]
        CODEX[OpenAI Codex]
    end

    subgraph "Actions"
        AUDIT[Run Audit]
        ANALYZE[Bundle Analysis]
        CONTEXT[Generate Context]
        FIX[Auto-fix Issues]
    end

    CURSOR --> TOOL1
    CURSOR --> TOOL2
    CLAUDE --> TOOL3
    CLAUDE --> TOOL4
    CODEX --> TOOL5

    TOOL1 --> AUDIT
    TOOL2 --> ANALYZE
    TOOL3 --> CONTEXT
    TOOL4 --> CONTEXT
    TOOL5 --> FIX
```

## Release Pipeline

```mermaid
flowchart LR
    PR[Pull Request] --> LINT[Ruff Lint<br/>+ Type Check]
    LINT --> TEST[pytest<br/>4100+ tests]
    TEST --> RUSTBUILD[Build Rust<br/>Wheels]
    RUSTBUILD --> SMOKE[Smoke Test<br/>Import + CLI]
    SMOKE --> TESTPYPI[Upload to<br/>TestPyPI]
    TESTPYPI --> VERIFY[Install Verify<br/>from TestPyPI]
    VERIFY --> PYPI[Publish to<br/>PyPI]
    PYPI --> DOCS[Deploy<br/>Docs]
    DOCS --> SDK[Generate<br/>TS/Swift SDK]

    RUSTBUILD --> |"Linux x86_64<br/>Linux aarch64<br/>macOS x86_64<br/>macOS aarch64<br/>Windows x86_64"| WHEELS[Platform<br/>Wheels]
    WHEELS --> SMOKE
```

## Related Documentation

- [Architecture Overview](./architecture/overview.md)
- [Authentication](./architecture/authentication.md)
- [Data Flow](./architecture/data-flow.md)
- [Messaging](./messaging/overview.md)
- [Notifications](./notifications/overview.md)
- [Email](./email/overview.md)
- [Deployment](./deployment/index.md)
- [Dependency Injection](./di/overview.md)
- [Content Negotiation](./negotiation/overview.md)
- [RBAC](./auth/rbac.md)
- [Admin Interface](./admin/overview.md)
- [Audit Logging](./audit/overview.md)
- [AI/ML](./ai/overview.md)
- [HTMX](./htmx/overview.md)
- [Livewire](./livewire/overview.md)
- [Code Generation](./codegen/overview.md)
- [OpenAPI](./openapi/overview.md)
- [Interceptors](./interceptors/overview.md)
- [Streaming/SSE](./streaming/overview.md)
- [Event Bus](./events/overview.md)
- [CQRS](./cqrs/overview.md)
- [Module System](./modules/overview.md)
- [Secrets Management](./secrets/overview.md)
- [Introspection](./introspection/overview.md)
- [RPC Client](./rpc/overview.md)
- [Observability](./observability/index.md)
- [Native Tasks](./tasks/overview.md) (Stage 17A)
- [AI-Assisted Audits](./audits/overview.md) (Stage 17B)
- [Slim Mode](./slim-mode.md)
