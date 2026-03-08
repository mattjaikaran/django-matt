# Phase 6: Real-Time, Notifications, and Communications - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Complete WebSocket consumers with auth middleware and presence, messaging module with WebSocket transport, notification dispatch (in-app, push, SMS, webhook), and email backends (SendGrid, Mailgun, SES, SMTP) — all working end-to-end with tests.

Requirements: RT-01, RT-02, RT-03, MSG-01, MSG-02, MSG-03, NOTIF-01, NOTIF-02, NOTIF-03, NOTIF-04, NOTIF-05, EMAIL-01, EMAIL-02, EMAIL-03, EMAIL-04, EMAIL-05

</domain>

<decisions>
## Implementation Decisions

### WebSocket Consumer Fixes
- **Async boundary approach**: Claude's discretion — choose the pattern that best fits existing codebase conventions (Phase 1 established sync_to_async wrapping for sync model methods called from async; Phase 4 used same pattern for multitenancy)
- **MessagingConsumer broken calls**: Must fix `MessageService.asend_message()`, `MessageService.amark_as_read()`, and `Conversation.ais_member()` — these methods don't exist and the consumer is non-functional
- **PresenceManager.get_user_groups()**: Claude's discretion on whether to build reverse index or leave as stub — evaluate against success criteria needs
- **Polling controller sync ORM**: Claude's discretion — evaluate against Phase 1 correctness precedent
- **Messaging test coverage**: Claude's discretion on depth — determine minimum viable coverage for success criteria. Messaging currently has zero tests for models/services/consumer/controllers (only enums/schemas)

### Push Notification Strategy
- **FCM/APNs implementation**: Claude's discretion — pick approach that fits the "Django-only dependency" philosophy. Consider extensible base class pattern (PushToken model + abstract PushProvider) vs real integration
- **SMS implementation**: Claude's discretion — same dependency philosophy consideration. Abstract SMSProvider base with users bringing their own Twilio/Vonage
- **Push test approach**: Mock dispatch is fine — test verifies pipeline end-to-end with mocked external calls
- **Webhook delivery async**: Claude's discretion — evaluate whether WebhookDeliveryHandler should use httpx async based on where it's called from

### Email Webhook Ingestion
- **Provider webhook receivers**: Claude's discretion — evaluate what's needed to satisfy success criteria and match existing provider coverage. EmailEvent model exists but nothing populates it
- **Email digest scheduling**: Claude's discretion — evaluate whether digests are needed for success criteria. NotificationPreferences supports daily/weekly but no aggregation task exists
- **Default email templates**: Claude's discretion — evaluate whether the email module needs shipped templates to be functional or if plain text fallback is sufficient
- **Template rendering engine**: Claude's discretion — Django template engine is already implemented in EmailTemplate.render(). Evaluate if that's sufficient

### Notification-Email Integration
- **Wire notifications through email module**: Claude's discretion — evaluate whether EmailDeliveryHandler should call EmailService.send() instead of django.core.mail.send_mail (gets tracking, suppression, provider selection for free)
- **In-app WebSocket degradation**: Claude's discretion — evaluate whether InAppDeliveryHandler should gracefully degrade when channel layer isn't configured (framework's optional-dependency philosophy)
- **Example app migration**: Claude's discretion — evaluate whether saas-starter notification consumers should migrate from raw channels to django_matt.websockets
- **datetime.utcnow() deprecations**: Claude's discretion — evaluate whether to fix while already in these files

### Claude's Discretion
Claude has broad discretion on implementation approach for this phase. The user trusts Claude to make the right call based on:
1. Phase 1 correctness precedent (no sync ORM in async context)
2. Django-only dependency philosophy (no external packages in core)
3. Existing codebase patterns (sync_to_async wrapping, async-first)
4. Success criteria satisfaction (5 specific testable outcomes)
5. Test coverage that proves the success criteria

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. User deferred all implementation decisions to Claude's judgment based on established project patterns and principles.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `websockets/consumers.py`: BaseConsumer, JsonConsumer, AuthenticatedConsumer, RoomConsumer — fully implemented with rate limiting, group management, orjson serialization (728-line test file)
- `websockets/auth.py`: JWTAuthMiddleware, SessionAuthMiddleware, TokenAuthMiddleware, CombinedAuthMiddleware — all working
- `websockets/routing.py`: WebSocketRouter with fluent API, decorator, ASGI application builder
- `websockets/groups.py`: PresenceManager (cache-backed) — forward lookup works, reverse index is stub
- `websockets/schemas.py`: 25+ Pydantic message schemas (chat, room, presence, notification, pub/sub)
- `websockets/centrifugo/`: Full Centrifugo integration (client, tokens, proxy views)
- `messaging/models/`: Complete Conversation, Message, Attachment, MessageStatus, MessageReaction, MessageEdit models
- `messaging/services/`: ConversationService and MessageService (sync-only), PresenceService (cache-based)
- `messaging/realtime/events.py`: 14 event types with Pydantic models and factory functions
- `notifications/models/`: Notification, NotificationDelivery, NotificationPreferences, NotificationRule — all complete
- `notifications/services/`: NotificationService (create, bulk, collapse, mark_read) and DeliveryService with handler registry
- `email/models.py`: EmailMessage, EmailEvent, EmailTemplate, SuppressedEmail — all complete
- `email/service.py`: EmailService with send, template, bulk, retry, stats
- `email/providers/`: 6 providers (SMTP, SendGrid, Mailgun, SES, Console, Resend) — all implemented

### Established Patterns
- Async-first: sync model methods wrapped with sync_to_async when called from async context (Phase 1/4 pattern)
- orjson for all JSON serialization
- Pydantic v2 schemas with model_construct() fast path for list reads
- Service layer pattern: models stay sync, services add business logic, controllers handle HTTP
- Optional deps: pytest.importorskip() for packages not in core

### Integration Points
- MessagingConsumer inherits from AuthenticatedConsumer (websockets module)
- InAppDeliveryHandler broadcasts via channel_layer to user_{id} group
- EmailDeliveryHandler currently uses django.core.mail (should potentially use django_matt.email.EmailService)
- PushDeliveryHandler tries apps.get_model("notifications", "PushToken") — model doesn't exist
- examples/realtime-chat/ uses RoomConsumer and PresenceManager — dogfoods websocket module
- examples/saas-starter/notifications/ uses raw channels — doesn't use framework

### Critical Bugs to Fix
1. MessagingConsumer calls nonexistent async methods (asend_message, amark_as_read, ais_member)
2. No PushToken model anywhere in codebase
3. PingMessage.timestamp uses deprecated datetime.utcnow()
4. WebhookDeliveryHandler uses sync `requests` library

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-real-time-notifications-and-communications*
*Context gathered: 2026-03-08*
