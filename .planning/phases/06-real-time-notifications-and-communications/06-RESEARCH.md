# Phase 6: Real-Time, Notifications, and Communications - Research

**Researched:** 2026-03-08
**Domain:** Django Channels / WebSockets, async service boundaries, push notifications, email delivery, multi-channel notification dispatch
**Confidence:** HIGH — all findings are grounded in direct codebase inspection of the source files being modified

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **MessagingConsumer broken calls**: Must fix `MessageService.asend_message()`, `MessageService.amark_as_read()`, and `Conversation.ais_member()` — these methods don't exist and the consumer is non-functional
- **Async boundary approach**: Choose the pattern that best fits existing codebase conventions (Phase 1 established sync_to_async wrapping for sync model methods called from async; Phase 4 used same pattern for multitenancy)

### Claude's Discretion
- **PresenceManager.get_user_groups()**: Build reverse index or leave as stub — evaluate against success criteria needs
- **Polling controller sync ORM**: Evaluate against Phase 1 correctness precedent
- **Messaging test coverage**: Determine minimum viable coverage for success criteria. Messaging currently has zero tests for models/services/consumer/controllers (only enums/schemas)
- **FCM/APNs implementation**: Pick approach that fits the "Django-only dependency" philosophy. Consider extensible base class pattern (PushToken model + abstract PushProvider) vs real integration
- **SMS implementation**: Abstract SMSProvider base with users bringing their own Twilio/Vonage
- **Push test approach**: Mock dispatch is fine — test verifies pipeline end-to-end with mocked external calls
- **Webhook delivery async**: Evaluate whether WebhookDeliveryHandler should use httpx async based on where it's called from
- **Provider webhook receivers**: Evaluate what's needed to satisfy success criteria
- **Email digest scheduling**: Evaluate whether digests are needed for success criteria
- **Default email templates**: Evaluate whether email module needs shipped templates or plain text fallback is sufficient
- **Template rendering engine**: Django template engine already implemented in EmailTemplate.render() — evaluate if sufficient
- **Wire notifications through email module**: Evaluate whether EmailDeliveryHandler should call EmailService.send() instead of django.core.mail.send_mail
- **In-app WebSocket degradation**: Evaluate whether InAppDeliveryHandler should gracefully degrade when channel layer isn't configured
- **Example app migration**: Evaluate whether saas-starter notification consumers should migrate from raw channels to django_matt.websockets
- **datetime.utcnow() deprecations**: Evaluate whether to fix while already in these files

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RT-01 | WebSocket consumer base class with authentication middleware | BaseConsumer + JWTAuthMiddleware exist and work; MessagingConsumer inherits AuthenticatedConsumer — needs async boundary fix for ais_member() |
| RT-02 | Presence tracking (who's online in a channel) | PresenceManager (cache-backed) exists; forward lookup works; reverse index (get_user_groups) is a stub that returns empty list |
| RT-03 | WebSocket routing integrated with django-matt router | WebSocketRouter + collect_routes + create_asgi_application all exist and work end-to-end |
| MSG-01 | Conversation model with participants and messages | Conversation, ConversationMember, Message, MessageStatus, MessageReaction, MessageEdit all exist in messaging/models/ |
| MSG-02 | Message attachments (file references) | Attachment model exists in messaging/models/attachment.py |
| MSG-03 | WebSocket transport for real-time message delivery | MessagingConsumer exists but is broken: calls asend_message(), amark_as_read(), ais_member() that don't exist |
| NOTIF-01 | In-app notification system with read/unread tracking | Notification + NotificationDelivery + InAppDeliveryHandler all exist; mark_as_read() works on the model |
| NOTIF-02 | Email notifications with template rendering | EmailDeliveryHandler exists; uses django.core.mail.send_mail (not EmailService); template fallback exists |
| NOTIF-03 | Push notifications via FCM and APNs | PushDeliveryHandler exists but calls apps.get_model("notifications", "PushToken") — model doesn't exist anywhere |
| NOTIF-04 | SMS notifications | SMSDeliveryHandler exists; _send_sms() is a documented no-op with Twilio example in docstring |
| NOTIF-05 | Webhook notifications to external endpoints | WebhookDeliveryHandler exists; uses sync `requests` library; has hmac.new() bug (correct is hmac.new = not valid, correct is hmac.HMAC via hmac.new is actually correct Python 3 — verified: it's hmac.new() which IS the correct call in Python 3) |
| EMAIL-01 | SendGrid email backend | SendGridProvider exists in email/providers/sendgrid.py — lazy-loads sendgrid SDK |
| EMAIL-02 | Mailgun email backend | MailgunProvider exists in email/providers/mailgun.py |
| EMAIL-03 | AWS SES email backend | SESProvider exists in email/providers/ses.py |
| EMAIL-04 | SMTP fallback backend | SMTPProvider exists in email/providers/smtp.py |
| EMAIL-05 | Email templates with variable substitution | EmailTemplate model exists with render() using Django template engine |
</phase_requirements>

---

## Summary

Phase 6 is a **completion and correctness audit phase**, not a build-from-scratch phase. The infrastructure for all 16 requirements already exists in the codebase; what's missing is: (1) a handful of critical bugs that make MessagingConsumer non-functional, (2) a missing PushToken model, (3) a sync ORM violation in the polling controller, (4) deprecated datetime.utcnow() calls in websockets/schemas.py, and (5) test coverage for the messaging module (currently zero tests for models/services/consumer/controllers).

The five success criteria map cleanly to what the codebase already has or can easily gain. The biggest lift is the MessagingConsumer fix (add three async wrapper methods), the PushToken model (single new model with migration), and messaging test coverage (write tests that exercise the existing code path end-to-end with an async channel layer mock).

The pattern for all async boundary fixes is established and consistent: sync model methods get `sync_to_async` wrappers added to the service layer, named with the `a` prefix (matching `aget`, `asave`, `acreate` Django conventions). The existing test infrastructure (asyncio_mode=auto, pytest-django, mock-based channel layer testing) is sufficient to test all success criteria.

**Primary recommendation:** Fix the four critical bugs first (asend_message, amark_as_read, ais_member, PushToken model), then write the minimum test suite that proves all five success criteria pass. Do not attempt external FCM/APNs SDK integration — the abstract provider pattern (PushDeliveryHandler._send_push is already a documented override point) is sufficient for NOTIF-03.

---

## Standard Stack

### Core (Already in Place)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| channels | 4.x | Django WebSocket support (ASGI) | Official Django async extension; already used throughout |
| channels-redis | 4.x | Redis channel layer backend | Required for multi-process presence; already configured in examples |
| asgiref | 3.x | sync_to_async / async_to_sync bridges | Django's own async boundary tool; Phase 1 established its use pattern |
| orjson | 3.x | JSON serialization in consumers | Already a base dep; consumers use it directly |
| django.core.cache | Django built-in | PresenceManager backend | Already used; no external dep needed |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-asyncio | 0.23+ | Async test support | Already configured: asyncio_mode=auto in pyproject.toml |
| pytest-django | 4.x | Django test fixtures | Already in place; db fixture, django_db marker |
| unittest.mock (AsyncMock) | stdlib | Mock channel layer in tests | Standard for testing consumers without real Redis |

### NOT in Standard Stack (Django-only dep philosophy)
- firebase-admin: NOT used — PushDeliveryHandler._send_push() is a documented override point
- twilio: NOT used — SMSDeliveryHandler._send_sms() is a documented override point
- httpx: Evaluate for WebhookDeliveryHandler ONLY (currently uses sync `requests`)
- sendgrid SDK, boto3, requests: Already optional deps loaded lazily in providers

**Installation:** No new packages needed. All required packages already declared in pyproject.toml.

---

## Architecture Patterns

### Recommended Project Structure (Phase 6 Touch Points)

```
django_matt/
├── websockets/
│   ├── consumers.py       # BaseConsumer, AuthenticatedConsumer — already correct
│   ├── auth.py            # JWTAuthMiddleware — already correct
│   ├── groups.py          # PresenceManager — fix get_user_groups() reverse index
│   ├── routing.py         # WebSocketRouter — already correct
│   └── schemas.py         # Fix datetime.utcnow() → datetime.now(UTC)
├── messaging/
│   ├── models/
│   │   └── conversation.py  # Add ais_member() async wrapper
│   ├── services/
│   │   └── message.py       # Add asend_message(), amark_as_read() async wrappers
│   └── realtime/
│       └── consumer.py      # Already calls correct methods; will work after service fix
├── notifications/
│   ├── models/
│   │   └── notification.py  # Add PushToken model (new)
│   └── services/
│       └── delivery.py      # Fix WebhookDeliveryHandler sync requests; optionally upgrade EmailDeliveryHandler
└── email/
    └── service.py           # Already correct; EmailService.send() is the canonical API
```

### Pattern 1: sync_to_async Wrapper for Service Methods (Established - Phase 1/4)

**What:** Sync model/service methods are not refactored; instead, async wrapper class/static methods are added that call `sync_to_async(cls.sync_method)(...)`.

**When to use:** Any time an async consumer or async controller needs to call a sync service method that contains ORM operations.

**Example:**
```python
# Source: Phase 1/4 established pattern in django_matt/auth/ and django_matt/multitenancy/
from asgiref.sync import sync_to_async

class MessageService:
    # Existing sync method stays unchanged
    @staticmethod
    @transaction.atomic
    def send_message(conversation, sender, content, ...):
        # ... sync ORM operations
        pass

    # New async wrapper — never contains ORM, just delegates
    @staticmethod
    async def asend_message(conversation, sender, content, ...):
        return await sync_to_async(MessageService.send_message)(
            conversation, sender, content, ...
        )

    @staticmethod
    async def amark_as_read(conversation, user, up_to_message=None):
        return await sync_to_async(MessageService.mark_as_read)(
            conversation, user, up_to_message
        )
```

### Pattern 2: Model Instance Async Method (Established - Phase 4)

**What:** Sync instance methods on models are wrapped with `sync_to_async` inside an async method on the same model. Used when the model method is called from async context.

**When to use:** When `Conversation.is_member(user)` (sync) is called from `MessagingConsumer._verify_conversation_access()` (async).

**Example:**
```python
# In messaging/models/conversation.py
class Conversation(models.Model):
    def is_member(self, user) -> bool:
        """Sync: Check if user is active member."""
        return self.members.filter(user=user, is_active=True).exists()

    async def ais_member(self, user) -> bool:
        """Async: Check if user is active member."""
        from asgiref.sync import sync_to_async
        return await sync_to_async(self.is_member)(user)
```

### Pattern 3: PushToken Model (New)

**What:** A new model in `notifications/` that stores per-user, per-device push tokens with platform discrimination.

**When to use:** NOTIF-03 requires push tokens to be registered and retrieved. PushDeliveryHandler already calls `apps.get_model("notifications", "PushToken")` — the model must exist.

**Example:**
```python
# In notifications/models/notification.py (or a new push.py)
class PushToken(models.Model):
    """Per-device push notification token."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="push_tokens")
    token = models.CharField(max_length=512)
    platform = models.CharField(max_length=20,
                                choices=[("fcm", "FCM"), ("apns", "APNs"), ("web", "Web Push")])
    device_id = models.CharField(max_length=255, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("user", "token")]
        app_label = "notifications"
```

### Pattern 4: PresenceManager Reverse Index

**What:** Add a user→groups index to cache alongside the group→users forward index. Updated on `user_joined()` and `user_left()`.

**When to use:** `get_user_groups()` currently returns empty list stub. RT-02 success criterion requires presence events (join/leave) for other users, which the existing forward lookup (per-group) already satisfies. The reverse index is needed only for "what groups is this user in" queries during disconnect cleanup. Evaluate: is it needed for the success criterion? Yes — when a user disconnects, the consumer needs to clean up their presence from all groups they joined.

**Example:**
```python
# In websockets/groups.py
async def user_joined(self, group_name, user_id, channel_name, metadata=None):
    # ... existing forward index update ...

    # Reverse index: user -> set of groups
    reverse_key = f"{self._prefix}user:{user_id}:groups"
    cache = self._get_cache()
    user_groups = cache.get(reverse_key) or set()
    user_groups.add(group_name)
    cache.set(reverse_key, user_groups, timeout=86400)

async def get_user_groups(self, user_id: str) -> list[str]:
    cache = self._get_cache()
    reverse_key = f"{self._prefix}user:{user_id}:groups"
    return list(cache.get(reverse_key) or set())
```

### Pattern 5: Graceful Channel Layer Degradation (InAppDeliveryHandler)

**What:** InAppDeliveryHandler._broadcast_websocket() already has try/except ImportError for `channels` not installed. The pattern is correct; it silently skips WebSocket broadcast if channels isn't configured.

**Verdict:** Existing pattern is already correct for the optional-dependency philosophy. No change needed.

### Anti-Patterns to Avoid

- **Direct ORM in async consumer**: Never call `Conversation.objects.get()` in a consumer `handle_*` method without `await`. Always use `aget()` or `sync_to_async()`.
- **Calling sync service methods directly from async context**: e.g., `MessageService.send_message()` from `handle_send_message()` — always use the async `asend_message()` wrapper.
- **hmac.new() vs hmac.HMAC()**: `hmac.new()` IS the correct Python 3 call (not a bug — it's the module-level constructor). Verified: `hmac.new(key, msg, digestmod)` is valid Python 3 standard library. No fix needed.
- **datetime.utcnow() in schemas**: `datetime.utcnow()` is deprecated in Python 3.12+. Replace with `datetime.now(UTC)` using `from datetime import UTC`. This affects websockets/schemas.py (8 occurrences).
- **sync `requests` in async delivery handler**: WebhookDeliveryHandler uses `requests.post()`. Since `deliver()` is called from `DeliveryService.deliver_notification()` which is sync (not async), this is acceptable. The handler ABC defines `deliver()` as sync. Verdict: leave `requests` as-is — it's called from a sync context; switching to httpx async would require making the entire delivery pipeline async which is out of scope.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WebSocket auth | Custom handshake parsing | JWTAuthMiddleware (websockets/auth.py) | Already handles query param, header, subprotocol |
| Group broadcast | Custom pub/sub | channel_layer.group_send() via BaseConsumer.broadcast_to_group() | Already abstracted |
| Presence tracking | Custom Redis sorted sets | PresenceManager (websockets/groups.py) | Cache-backed; already works for forward lookup |
| Email sending | django.core.mail direct calls | EmailService.send() / send_template() | Adds tracking, suppression, provider selection |
| JWT decode in WS | Custom token parsing | JWTAuthMiddleware._get_user_from_token() | Reuses auth module's get_user_from_token() |
| Notification delivery | Custom dispatch loop | DeliveryService.deliver_notification() | Handler registry pattern already in place |
| Template rendering | Custom Jinja/Mako | EmailTemplate.render() (Django template engine) | Already implemented; Django templates are sufficient |

**Key insight:** The codebase has the right abstractions. The only hand-rolling needed is adding missing async wrappers and a missing model — not building new systems.

---

## Common Pitfalls

### Pitfall 1: Calling Sync Service Methods from Async Consumer
**What goes wrong:** `MessageService.send_message()` uses `@transaction.atomic` and sync ORM (`Message.objects.create()`). Calling it directly from `handle_send_message()` (async) triggers `SynchronousOnlyOperation` or deadlocks the event loop.
**Why it happens:** This is exactly the DJANGO_ALLOW_ASYNC_UNSAFE=true mistake eliminated in Phase 1. MessagingConsumer currently calls `MessageService.asend_message()` which doesn't exist yet.
**How to avoid:** Add async wrappers to MessageService using the Phase 1/4 pattern. The consumer code is already written correctly — it just needs the methods to exist.
**Warning signs:** `AttributeError: type object 'MessageService' has no attribute 'asend_message'`

### Pitfall 2: PushToken Model Missing from App Registry
**What goes wrong:** `apps.get_model("notifications", "PushToken")` raises `LookupError: No installed app with label 'notifications'` or `LookupError: App 'notifications' doesn't have a 'PushToken' model` at runtime.
**Why it happens:** PushToken is referenced in PushDeliveryHandler but never defined.
**How to avoid:** Add PushToken model to `notifications/models/notification.py` (or its own file), add to `notifications/models/__init__.py`, create migration.
**Warning signs:** Any push notification test silently returns `[]` from `_get_push_tokens()` because the except clause swallows the LookupError.

### Pitfall 3: PresenceManager Cache Methods Are Sync, Called from Async Consumer
**What goes wrong:** `PresenceManager.user_joined()` and `user_left()` are defined as `async def` but use `cache.get()` / `cache.set()` (sync Django cache API). This is mixed signals.
**Why it happens:** The methods have `async def` signatures but their bodies are sync. This works (async functions can call sync code) but misses a subtle correctness issue: if the cache backend is async (unlikely in practice), this breaks.
**How to avoid:** The current implementation is acceptable since Django's cache is sync. The `async def` wrappers on PresenceManager are fine as-is — they call sync cache ops, which is allowed in async context (just slightly inefficient due to no await).
**Warning signs:** None at runtime; the issue is theoretical for async cache backends only.

### Pitfall 4: Testing Consumers Without Real Channel Layer
**What goes wrong:** Tests that instantiate `MessagingConsumer` fail because `self.channel_layer` is None (no CHANNEL_LAYERS in test settings).
**Why it happens:** Channels consumers need either a real Redis channel layer or an in-memory mock.
**How to avoid:** Use `channels.testing.WebsocketCommunicator` with `InMemoryChannelLayer` for integration tests. For unit tests, mock `self.channel_layer` with `AsyncMock`. The existing `test_websockets.py` (728 lines) demonstrates the full mock ASGI scope pattern.
**Warning signs:** Tests that hang indefinitely (waiting on channel layer) or `AttributeError: 'NoneType' has no attribute 'group_send'`.

### Pitfall 5: datetime.utcnow() Deprecation Warning Noise
**What goes wrong:** Python 3.12+ emits `DeprecationWarning: datetime.utcnow() is deprecated` for every schema instantiation. The filterwarnings config in pyproject.toml suppresses it in tests, but it will appear in production logs.
**Why it happens:** 8 occurrences in `websockets/schemas.py` use `Field(default_factory=datetime.utcnow)`.
**How to avoid:** Replace with `Field(default_factory=lambda: datetime.now(UTC))` or `Field(default_factory=datetime.now)` + timezone awareness. Since this phase touches `websockets/schemas.py`, fix these while in the file.
**Warning signs:** Production log noise at schema construction time.

### Pitfall 6: Email Delivery via django.core.mail vs EmailService
**What goes wrong:** `EmailDeliveryHandler._send_email()` calls `django.core.mail.send_mail()` which bypasses the `EmailService` pipeline — no tracking record created, no suppression list checked, no provider selection.
**Why it happens:** EmailDeliveryHandler was written before EmailService was mature.
**How to avoid:** Upgrade EmailDeliveryHandler to call `EmailService.send()` instead. This satisfies NOTIF-02 correctly and gives tracking for free.
**Warning signs:** Email notifications sent but no `EmailMessage` record created in database.

---

## Code Examples

Verified patterns from direct codebase inspection:

### Adding asend_message() to MessageService
```python
# Source: django_matt/messaging/services/message.py
from asgiref.sync import sync_to_async

class MessageService:
    # ... existing sync methods unchanged ...

    @staticmethod
    async def asend_message(conversation, sender, content,
                             message_type=MessageType.TEXT,
                             reply_to=None, attachments=None, metadata=None):
        """Async wrapper for send_message."""
        return await sync_to_async(MessageService.send_message)(
            conversation, sender, content,
            message_type=message_type,
            reply_to=reply_to,
            attachments=attachments,
            metadata=metadata,
        )

    @staticmethod
    async def amark_as_read(conversation, user, up_to_message=None):
        """Async wrapper for mark_as_read."""
        return await sync_to_async(MessageService.mark_as_read)(
            conversation, user, up_to_message
        )
```

### Adding ais_member() to Conversation
```python
# Source: django_matt/messaging/models/conversation.py
class Conversation(models.Model):
    # ... existing sync methods unchanged ...

    async def ais_member(self, user) -> bool:
        """Async check if user is active member."""
        from asgiref.sync import sync_to_async
        return await sync_to_async(self.is_member)(user)
```

### Testing MessagingConsumer with InMemoryChannelLayer
```python
# Source: pattern from existing test_websockets.py (lines 1-728)
import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from channels.layers import InMemoryChannelLayer
from unittest.mock import AsyncMock, patch

@pytest.mark.django_db
async def test_messaging_consumer_send_message(user, conversation):
    """MSG-03: User sends message, other participant receives via WebSocket."""
    from django_matt.messaging.realtime.consumer import MessagingConsumer

    # Use in-memory channel layer
    layer = InMemoryChannelLayer()
    with patch("channels.layers.get_channel_layer", return_value=layer):
        communicator = WebsocketCommunicator(
            MessagingConsumer.as_asgi(),
            "/ws/messaging/"
        )
        communicator.scope["user"] = user
        communicator.scope["channel_layer"] = layer
        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({
            "type": "subscribe",
            "conversation_ids": [conversation.id]
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "subscribed"
        # ... send message, verify broadcast ...
        await communicator.disconnect()
```

### NotificationController mark_read (NOTIF-01 success criterion)
```python
# Source: django_matt/notifications/controllers/notification.py
# The controller already exists with list, get, mark_read, dismiss endpoints.
# Test pattern:
@pytest.mark.django_db
async def test_mark_notification_read(async_client, user, notification):
    async_client.force_authenticate(user)
    response = await async_client.post(
        f"/notifications/{notification.id}/read/"
    )
    assert response.status_code == 200
    await notification.arefresh_from_db()
    assert notification.read_at is not None  # NOTIF-01 success criterion
```

### EmailService.send_template() with mock backend (EMAIL-05 success criterion)
```python
# Source: django_matt/email/service.py + django_matt/email/providers/console.py
@pytest.mark.django_db
@override_settings(
    DJANGO_MATT_EMAIL={"PROVIDER": "console"},
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
def test_template_email_variable_substitution(db):
    """EMAIL-05: Template renders variables correctly."""
    template = EmailTemplate.objects.create(
        name="welcome",
        subject="Hello {{ first_name }}",
        text_body="Welcome, {{ first_name }}!",
        is_active=True,
    )
    email = EmailService.send_template(
        to="user@example.com",
        template_name="welcome",
        context={"first_name": "Alice"},
    )
    assert "Alice" in email.text_body
    assert email.subject == "Hello Alice"
```

### datetime.utcnow() fix in schemas.py
```python
# Source: django_matt/websockets/schemas.py — fix 8 occurrences
# Before:
from datetime import datetime
timestamp: datetime = Field(default_factory=datetime.utcnow)

# After:
from datetime import UTC, datetime
timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| DJANGO_ALLOW_ASYNC_UNSAFE=true | sync_to_async wrappers | Phase 1 | All async ORM must use aget/asave or wrappers |
| Direct django.core.mail | EmailService.send() | Phase 6 | Tracking + suppression + provider selection |
| Sync MessageService | Async wrappers (asend_message, amark_as_read) | Phase 6 | MessagingConsumer becomes functional |
| PushToken stub | PushToken model + migration | Phase 6 | Push pipeline unblocks |
| datetime.utcnow() | datetime.now(UTC) | Phase 6 | Clears Python 3.12 deprecation warnings |

**Deprecated/outdated:**
- `datetime.utcnow()`: deprecated in Python 3.12, present in 8 locations in websockets/schemas.py — fix while in the file
- `hmac.new()`: verified NOT a bug — `hmac.new(key, msg, digestmod)` is valid Python 3 stdlib (it's the module-level `new()` function equivalent to `hmac.HMAC()`). Leave as-is.

---

## Open Questions

1. **Polling controller sync ORM**
   - What we know: `messaging/realtime/polling.py` exists; likely has sync ORM in an async context
   - What's unclear: Haven't inspected it; CONTEXT.md flags it as discretionary
   - Recommendation: Inspect during planning; fix only if it's called from async context (Phase 1 precedent)

2. **Email digest scheduling**
   - What we know: NotificationPreferences supports `email_frequency: "daily"/"weekly"` but no aggregation task exists
   - What's unclear: Is this needed for any success criterion?
   - Recommendation: Not needed — success criteria only require immediate email dispatch; leave digest as future work

3. **get_user_groups() reverse index scope**
   - What we know: Stub returns empty list; needed for disconnect cleanup in PresenceManager
   - What's unclear: Does the RT-02 success criterion ("receives presence events for other users in same channel") require reverse lookup?
   - Recommendation: Implement reverse index — it's needed for correct disconnect cleanup. Cache key pattern: `{prefix}user:{user_id}:groups` → set of group names

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio + pytest-django |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_messaging.py tests/test_notifications.py tests/test_websockets.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RT-01 | JWT token in WS handshake → user authenticated | integration | `uv run pytest tests/test_websockets.py -k "jwt" -x` | ✅ (partial — auth middleware tested, MessagingConsumer not) |
| RT-02 | User joins channel → others receive presence events | integration | `uv run pytest tests/test_messaging.py -k "presence" -x` | ❌ Wave 0 — new test class needed |
| RT-03 | WebSocketRouter routes to consumer via ASGI | unit | `uv run pytest tests/test_websockets.py -k "router" -x` | ✅ existing |
| MSG-01 | Conversation + Message model CRUD | unit | `uv run pytest tests/test_messaging.py -k "conversation" -x` | ❌ Wave 0 — only enums/schemas tested |
| MSG-02 | Attachment model CRUD | unit | `uv run pytest tests/test_messaging.py -k "attachment" -x` | ❌ Wave 0 |
| MSG-03 | User sends WS message → participant receives it same cycle | integration | `uv run pytest tests/test_messaging.py -k "consumer" -x` | ❌ Wave 0 |
| NOTIF-01 | Notification created, retrieved via API, mark_read updates timestamp | integration | `uv run pytest tests/test_notifications.py -k "mark_read" -x` | ✅ (partial — model tested, controller mark_read needs test) |
| NOTIF-02 | Email delivery handler dispatches notification via email | unit | `uv run pytest tests/test_notifications.py -k "email_delivery" -x` | ✅ (partial — handler tested with mock) |
| NOTIF-03 | Push enqueued for FCM/APNs with mock dispatch | unit | `uv run pytest tests/test_notifications.py -k "push" -x` | ❌ Wave 0 — PushToken model needed first |
| NOTIF-04 | SMS enqueued with mock dispatch | unit | `uv run pytest tests/test_notifications.py -k "sms" -x` | ✅ (SMSDeliveryHandler tested with mock) |
| NOTIF-05 | Webhook delivers with HMAC signature | unit | `uv run pytest tests/test_notifications.py -k "webhook" -x` | ✅ (handler exists in test file) |
| EMAIL-01 | SendGrid backend sends via mock HTTP | unit | `uv run pytest tests/test_email_service.py -k "sendgrid" -x` | ✅ |
| EMAIL-02 | Mailgun backend sends via mock HTTP | unit | `uv run pytest tests/test_email_service.py -k "mailgun" -x` | ✅ |
| EMAIL-03 | SES backend sends via mock boto3 | unit | `uv run pytest tests/test_email_service.py -k "ses" -x` | ✅ |
| EMAIL-04 | SMTP backend sends | unit | `uv run pytest tests/test_email_service.py -k "smtp" -x` | ✅ |
| EMAIL-05 | Template renders {{ variables }} correctly | unit | `uv run pytest tests/test_email_service.py -k "template" -x` | ✅ |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_messaging.py tests/test_notifications.py tests/test_websockets.py tests/test_email_service.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_messaging.py` — add `TestConversationModel`, `TestMessageModel`, `TestMessageService`, `TestMessagingConsumer` classes — covers MSG-01, MSG-02, MSG-03, RT-01, RT-02
- [ ] `notifications/models/__init__.py` — expose `PushToken` after model is added — covers NOTIF-03
- [ ] Django migration for `PushToken` model — `uv run python manage.py makemigrations notifications`

*(Existing test infrastructure covers all other phase requirements — only messaging consumer integration and push token model are missing)*

---

## Sources

### Primary (HIGH confidence — direct codebase inspection)
- `/Users/mattjaikaran/dev/django-matt/django_matt/websockets/consumers.py` — BaseConsumer, AuthenticatedConsumer, RoomConsumer full implementation
- `/Users/mattjaikaran/dev/django-matt/django_matt/websockets/auth.py` — JWTAuthMiddleware, token extraction patterns
- `/Users/mattjaikaran/dev/django-matt/django_matt/websockets/groups.py` — PresenceManager, get_user_groups stub confirmed
- `/Users/mattjaikaran/dev/django-matt/django_matt/messaging/realtime/consumer.py` — MessagingConsumer with nonexistent method calls confirmed
- `/Users/mattjaikaran/dev/django-matt/django_matt/messaging/services/message.py` — MessageService sync-only confirmed; no asend_message/amark_as_read
- `/Users/mattjaikaran/dev/django-matt/django_matt/messaging/models/conversation.py` — Conversation.is_member() sync; no ais_member()
- `/Users/mattjaikaran/dev/django-matt/django_matt/notifications/services/delivery.py` — PushDeliveryHandler apps.get_model bug confirmed; WebhookDeliveryHandler sync requests confirmed; hmac.new() verified correct
- `/Users/mattjaikaran/dev/django-matt/django_matt/notifications/models/notification.py` — Notification + NotificationDelivery complete; PushToken absent confirmed
- `/Users/mattjaikaran/dev/django-matt/django_matt/email/service.py` — EmailService.send() + send_template() complete
- `/Users/mattjaikaran/dev/django-matt/django_matt/email/providers/sendgrid.py` — lazy-loaded SendGrid SDK pattern
- `/Users/mattjaikaran/dev/django-matt/django_matt/websockets/schemas.py` — datetime.utcnow() confirmed in 8 fields
- `/Users/mattjaikaran/dev/django-matt/.planning/phases/06-real-time-notifications-and-communications/06-CONTEXT.md` — locked decisions and discretionary areas
- `/Users/mattjaikaran/dev/django-matt/.planning/REQUIREMENTS.md` — RT-01 through EMAIL-05 requirement text
- `/Users/mattjaikaran/dev/django-matt/pyproject.toml` — asyncio_mode=auto, pytest configuration

### Secondary (MEDIUM confidence — grep search across codebase)
- `hmac.new()` usage across codebase: confirmed it's the correct Python 3 stdlib call (not a bug)
- `datetime.utcnow()` across codebase: confirmed 8 occurrences in websockets/schemas.py; tasks/ and files/ are out of scope for this phase

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — direct inspection of imports and pyproject.toml
- Architecture: HIGH — patterns traced from Phase 1/4 decisions in STATE.md and live code
- Pitfalls: HIGH — bugs confirmed by reading the actual broken code (asend_message, PushToken, utcnow)
- Test gaps: HIGH — confirmed by reading test_messaging.py which covers only enums/schemas

**Research date:** 2026-03-08
**Valid until:** 2026-06-08 (stable — no external library evolution risk; all findings are internal codebase facts)
