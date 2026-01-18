# Authentication Architecture

django-matt supports multiple authentication strategies that can be used independently or combined.

## Authentication Flow Overview

```mermaid
flowchart TD
    REQ[Incoming Request] --> CHECK{Has Auth Header?}

    CHECK -->|Yes| PARSE[Parse Auth Header]
    CHECK -->|No| ANON[Anonymous User]

    PARSE --> TYPE{Auth Type?}

    TYPE -->|Bearer| JWT[JWT Validation]
    TYPE -->|ApiKey| APIKEY[API Key Lookup]
    TYPE -->|Basic| BASIC[Basic Auth]
    TYPE -->|Session| SESSION[Session Lookup]

    JWT --> VALID{Token Valid?}
    APIKEY --> VALID
    BASIC --> VALID
    SESSION --> VALID

    VALID -->|Yes| USER[Load User]
    VALID -->|No| REJECT[401 Unauthorized]

    USER --> PERM{Check Permissions}
    ANON --> PERM

    PERM -->|Allowed| HANDLER[Execute Handler]
    PERM -->|Denied| FORBIDDEN[403 Forbidden]
```

## JWT Authentication

```mermaid
sequenceDiagram
    participant C as Client
    participant A as Auth Endpoint
    participant J as JWT Service
    participant DB as Database

    Note over C,DB: Login Flow
    C->>A: POST /auth/login {email, password}
    A->>DB: Verify credentials
    DB->>A: User record
    A->>J: Generate tokens
    J->>A: {access_token, refresh_token}
    A->>C: 200 {tokens, user}

    Note over C,DB: Authenticated Request
    C->>A: GET /api/resource<br/>Authorization: Bearer {token}
    A->>J: Validate token
    J->>A: Token payload
    A->>DB: Load user
    DB->>A: User data
    A->>C: 200 {resource}

    Note over C,DB: Token Refresh
    C->>A: POST /auth/refresh {refresh_token}
    A->>J: Validate & rotate
    J->>A: New tokens
    A->>C: 200 {new_tokens}
```

## OAuth Flow

```mermaid
sequenceDiagram
    participant U as User
    participant A as App
    participant P as OAuth Provider
    participant B as Backend

    U->>A: Click "Login with Google"
    A->>B: GET /auth/oauth/google/authorize
    B->>A: Redirect URL
    A->>P: Redirect to provider
    P->>U: Login prompt
    U->>P: Enter credentials
    P->>A: Redirect with code
    A->>B: GET /auth/oauth/google/callback?code=xxx
    B->>P: Exchange code for tokens
    P->>B: Access token + user info
    B->>B: Create/update user
    B->>A: JWT tokens
    A->>U: Logged in
```

## Passkey/WebAuthn Flow

```mermaid
sequenceDiagram
    participant U as User
    participant B as Browser
    participant S as Server
    participant A as Authenticator

    Note over U,A: Registration
    U->>B: Click "Add Passkey"
    B->>S: GET /auth/passkeys/register/options
    S->>B: Challenge + options
    B->>A: Create credential request
    A->>U: Biometric prompt
    U->>A: Approve
    A->>B: Credential
    B->>S: POST /auth/passkeys/register/verify
    S->>S: Verify & store credential
    S->>B: Success

    Note over U,A: Authentication
    U->>B: Click "Login with Passkey"
    B->>S: GET /auth/passkeys/authenticate/options
    S->>B: Challenge + allowed credentials
    B->>A: Get assertion request
    A->>U: Biometric prompt
    U->>A: Approve
    A->>B: Assertion
    B->>S: POST /auth/passkeys/authenticate/verify
    S->>S: Verify signature
    S->>B: JWT tokens
```

## Enterprise SSO Flow

```mermaid
sequenceDiagram
    participant U as User
    participant A as App
    participant B as Backend
    participant I as Identity Provider

    Note over U,I: SAML Flow
    U->>A: Access protected resource
    A->>B: Check auth
    B->>A: Redirect to SSO
    A->>I: SAML AuthnRequest
    I->>U: Login page
    U->>I: Credentials
    I->>A: SAML Response (POST)
    A->>B: Validate assertion
    B->>B: Create session
    B->>A: JWT tokens
    A->>U: Access granted
```

## Auth Strategy Comparison

| Strategy | Use Case | Stateless | Security Level |
|----------|----------|-----------|----------------|
| JWT | APIs, SPAs | Yes | High |
| Session | Traditional web | No | High |
| API Keys | Service-to-service | Yes | Medium |
| OAuth | Social login | Yes | High |
| Passkeys | Passwordless | Yes | Very High |
| SSO | Enterprise | No | Very High |

## Configuration

```python
# settings.py
DJANGO_MATT = {
    "AUTH": {
        "JWT_SECRET": env("JWT_SECRET"),
        "JWT_ALGORITHM": "HS256",
        "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
        "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    },
    "OAUTH": {
        "GOOGLE": {
            "CLIENT_ID": env("GOOGLE_CLIENT_ID"),
            "CLIENT_SECRET": env("GOOGLE_CLIENT_SECRET"),
        },
    },
}
```

## Related Documentation

- [JWT Details](../auth/jwt.md)
- [OAuth Providers](../auth/oauth.md)
- [Passkeys](../auth/passkeys.md)
- [Enterprise SSO](../auth/sso.md)
- [API Keys](../auth/api-keys.md)
