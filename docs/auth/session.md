# Session Authentication

Cookie-based session authentication for traditional web applications.

## Configuration

```python
# settings.py
DJANGO_MATT = {
    "SESSION": {
        "COOKIE_NAME": "sessionid",
        "COOKIE_AGE": 1209600,  # 2 weeks
        "COOKIE_SECURE": True,  # HTTPS only
        "COOKIE_HTTPONLY": True,  # Not accessible via JavaScript
        "COOKIE_SAMESITE": "Lax",  # CSRF protection
        "COOKIE_PATH": "/",
        "CSRF_ENABLED": True,
        "CSRF_COOKIE_NAME": "csrftoken",
    },
}
```

## Middleware

```python
# settings.py
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django_matt.auth.session.SessionAuthMiddleware",
    "django_matt.auth.session.CSRFMiddleware",
]
```

## Decorators

### @session_required

```python
from django_matt.auth.session import session_required

@api.get("/profile")
@session_required
async def get_profile(request):
    return {"email": request.user.email}
```

### @login_required

Alias for session_required:

```python
from django_matt.auth.session import login_required

@api.get("/dashboard")
@login_required
async def dashboard(request):
    ...
```

### @fresh_session_required

Requires recent authentication (not just valid session):

```python
from django_matt.auth.session import fresh_session_required

@api.post("/change-password")
@fresh_session_required
async def change_password(request, data: ChangePasswordRequest):
    # User must have logged in recently
    ...
```

## Session Management

### Login

```python
from django_matt.auth.session import login_session

@api.post("/login")
async def login(request, data: LoginRequest):
    user = await authenticate(data.email, data.password)
    if not user:
        raise AuthenticationAPIError("Invalid credentials")

    await login_session(request, user)
    return {"message": "Logged in"}
```

### Logout

```python
from django_matt.auth.session import logout_session

@api.post("/logout")
@session_required
async def logout(request):
    await logout_session(request)
    return {"message": "Logged out"}
```

### Multi-Session Management

```python
from django_matt.auth.session import (
    get_user_sessions,
    delete_other_sessions,
)

@api.get("/sessions")
@session_required
async def list_sessions(request):
    sessions = await get_user_sessions(request.user)
    return {"sessions": sessions}

@api.post("/sessions/logout-others")
@session_required
async def logout_other_sessions(request):
    count = await delete_other_sessions(request)
    return {"deleted": count}
```

## CSRF Protection

### Decorators

```python
from django_matt.auth.session import (
    csrf_protect,
    csrf_exempt,
    ensure_csrf_cookie,
)

@api.post("/transfer")
@session_required
@csrf_protect
async def transfer_money(request, data: TransferRequest):
    # CSRF token is validated
    ...

@api.post("/webhook")
@csrf_exempt
async def webhook(request):
    # CSRF validation skipped
    ...

@api.get("/login-page")
@ensure_csrf_cookie
async def login_page(request):
    # Ensures CSRF cookie is set
    ...
```

### Getting CSRF Token

```python
from django_matt.auth.session import get_csrf_token

@api.get("/csrf-token")
async def get_token(request):
    token = get_csrf_token(request)
    return {"csrf_token": token}
```

### Frontend Usage

```javascript
// Get CSRF token from cookie
function getCsrfToken() {
    return document.cookie
        .split("; ")
        .find(row => row.startsWith("csrftoken="))
        ?.split("=")[1];
}

// Include in requests
fetch("/api/transfer", {
    method: "POST",
    headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
    },
    body: JSON.stringify(data),
    credentials: "include",  // Include cookies
});
```

## Flash Messages

Temporary messages stored in session:

```python
from django_matt.auth.session import flash_message, get_flash_messages

@api.post("/action")
@session_required
async def do_action(request):
    # Store a message
    flash_message(request, "Action completed successfully", "success")
    return {"ok": True}

@api.get("/messages")
@session_required
async def get_messages(request):
    # Retrieve and clear messages
    messages = get_flash_messages(request)
    return {"messages": messages}
```

## SessionController

Pre-built controller for session management:

```python
from django_matt.auth.session import SessionController

api.register_controller(SessionController, prefix="/auth")

# Provides:
# POST /auth/login - Login
# POST /auth/logout - Logout
# GET /auth/me - Get current user
# GET /auth/sessions - List all sessions
# DELETE /auth/sessions - Logout all other sessions
```

## Session Store

Enhanced session backend with user tracking:

```python
# settings.py
SESSION_ENGINE = "django_matt.auth.session.SessionStore"
```

This provides:
- User ID tracking per session
- Last activity timestamps
- IP address logging
- User agent tracking

## Security Best Practices

1. **Use HTTPS** - Always use secure cookies in production
2. **Enable CSRF** - Protect against cross-site request forgery
3. **Set HttpOnly** - Prevent XSS attacks from stealing cookies
4. **Use SameSite** - Prevent CSRF via cookie attribute
5. **Session timeout** - Expire inactive sessions
6. **Regenerate session ID** - After login to prevent fixation
