---
phase: 06-real-time-notifications-and-communications
plan: 01
subsystem: websockets, messaging
tags: [websockets, messaging, async, sync_to_async, presence, pydantic]

# Dependency graph
requires:
  - phase: 01-correctness-audit
    provides: sync_to_async patterns for async boundary correctness
  - phase: 04-auth-hardening-and-multi-tenancy
    provides: JWT auth used by WebSocket consumers
provides:
  - MessageService.asend_message() and amark_as_read() async wrappers
  - Conversation.ais_member() async wrapper
  - PresenceManager reverse index for get_user_groups()
  - Timezone-aware datetime defaults in WebSocket schemas
  - Comprehensive messaging model/service/presence tests
affects: [06-02, 06-03, notifications, messaging]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - sync_to_async wrappers for ORM-bound service methods
    - Reverse index in cache for O(1) user-to-groups lookup
    - datetime.now(UTC) replacing deprecated datetime.utcnow()

key-files:
  created: []
  modified:
    - django_matt/messaging/services/message.py
    - django_matt/messaging/models/conversation.py
    - django_matt/websockets/groups.py
    - django_matt/websockets/schemas.py
    - tests/test_messaging.py

key-decisions:
  - "Lazy import of sync_to_async in Conversation.ais_member() following Phase 4 model-layer pattern"
  - "PresenceManager reverse index uses cache with 24h TTL matching forward index TTL"

patterns-established:
  - "Async service wrappers: static async method calling sync_to_async(SyncMethod) with full kwarg forwarding"
  - "Reverse index pattern: maintain user:{id}:groups cache key alongside forward group:{name} key"

requirements-completed: [RT-01, RT-02, RT-03, MSG-01, MSG-02, MSG-03]

# Metrics
duration: 3min
completed: 2026-03-08
---

# Phase 6 Plan 01: WebSocket/Messaging Async Boundary Fixes Summary

**MessagingConsumer async wrappers (asend_message, amark_as_read, ais_member), PresenceManager reverse index, and datetime.utcnow() elimination with 23 new tests**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-08T21:55:14Z
- **Completed:** 2026-03-08T21:58:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Added async wrappers (asend_message, amark_as_read, ais_member) fixing broken MessagingConsumer
- Implemented PresenceManager reverse index so get_user_groups() returns actual groups instead of empty list
- Replaced all 8 datetime.utcnow() calls with datetime.now(UTC) in websockets/schemas.py
- Added 23 new tests covering conversation models, message service, async wrappers, and presence manager

## Task Commits

Each task was committed atomically:

1. **Task 1: Add async wrappers and fix PresenceManager + datetime.utcnow()** - `6f3266b` (feat)
2. **Task 2: Add messaging model/service/consumer tests** - `5138bbf` (test)

## Files Created/Modified
- `django_matt/messaging/services/message.py` - Added asend_message() and amark_as_read() async static methods
- `django_matt/messaging/models/conversation.py` - Added ais_member() async instance method
- `django_matt/websockets/groups.py` - Implemented reverse index in user_joined/user_left, replaced get_user_groups stub
- `django_matt/websockets/schemas.py` - Replaced 8 datetime.utcnow() with datetime.now(UTC)
- `tests/test_messaging.py` - Added TestConversationModel, TestMessageModel, TestMessageService, TestPresenceManagerReverseIndex

## Decisions Made
- Lazy import of sync_to_async in Conversation.ais_member() following Phase 4 model-layer pattern (keeps model file clean for sync callers)
- PresenceManager reverse index uses cache with 24h TTL matching forward index TTL for consistency

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed import ordering after adding asgiref import**
- **Found during:** Task 1
- **Issue:** ruff I001 import sorting error after adding `from asgiref.sync import sync_to_async`
- **Fix:** Ran `ruff check --fix` to auto-sort imports
- **Files modified:** django_matt/messaging/services/message.py
- **Verification:** `ruff check` passes clean
- **Committed in:** 6f3266b (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Trivial import ordering fix. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- MessagingConsumer can now call asend_message(), amark_as_read(), ais_member() without AttributeError
- PresenceManager supports user-to-groups lookup for notification routing
- Ready for 06-02 (notification system) which will use these messaging primitives

---
*Phase: 06-real-time-notifications-and-communications*
*Completed: 2026-03-08*
