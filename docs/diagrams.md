# Visual Diagrams Index

This page collects all architectural diagrams for django-matt.

## System Overview

```mermaid
graph TB
    subgraph "Client Layer"
        WEB[Web App]
        MOBILE[Mobile App]
        CLI[CLI]
    end

    subgraph "API Layer"
        API[MattAPI]
        AUTH[Auth]
        MW[Middleware]
    end

    subgraph "Service Layer"
        MSG[Messaging]
        NOTIF[Notifications]
        EMAIL[Email]
        BILLING[Billing]
    end

    subgraph "Data Layer"
        DB[(PostgreSQL)]
        CACHE[(Redis)]
        STORAGE[S3/Storage]
    end

    WEB --> API
    MOBILE --> API
    CLI --> API

    API --> AUTH
    AUTH --> MW
    MW --> MSG
    MW --> NOTIF
    MW --> EMAIL
    MW --> BILLING

    MSG --> DB
    NOTIF --> DB
    EMAIL --> DB
    BILLING --> DB

    MSG --> CACHE
    NOTIF --> CACHE
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

## Related Documentation

- [Architecture Overview](./architecture/overview.md)
- [Authentication](./architecture/authentication.md)
- [Data Flow](./architecture/data-flow.md)
- [Messaging](./messaging/overview.md)
- [Notifications](./notifications/overview.md)
- [Email](./email/overview.md)
- [Deployment](./deployment/overview.md)
