# Authentication

Django Matt ships a complete, async-first authentication system. See the dedicated guides below.

## Authentication Methods

| Method | Use Case | Guide |
|--------|----------|-------|
| **JWT** | API tokens for SPAs and mobile apps | [JWT](auth/jwt.md) |
| **Session** | Cookie-based for traditional web apps | [Session](auth/session.md) |
| **API Keys** | Server-to-server / third-party integrations | [API Keys](auth/api-keys.md) |
| **OAuth** | Social login (Google, GitHub, Apple, Microsoft) | [OAuth](auth/oauth.md) |
| **Passkeys** | Passwordless FIDO2/WebAuthn | [Passkeys](auth/passkeys.md) |
| **SSO** | Enterprise SAML 2.0 / OpenID Connect | [SSO](auth/sso.md) |
| **Magic Links** | Passwordless email authentication | [Overview](auth/overview.md) |
| **RBAC** | Role hierarchy and permission checks | [RBAC](auth/rbac.md) |

## Quick Start

```python
from django_matt.auth import (
    jwt_required,
    jwt_optional,
    create_token_pair,
    AuthController,
)
from django_matt.permissions import IsAuthenticated, IsAdmin, HasRole

# Register the built-in auth controller
api.register_controller(AuthController)
```

See [Authentication Overview](auth/overview.md) for a full getting-started guide.
