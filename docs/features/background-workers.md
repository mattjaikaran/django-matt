# Background Workers

Django Matt ships `tasks_native` as the built-in, recommended task engine. It requires no external beat process, validates payloads with Pydantic at enqueue time, and integrates with the Unfold Admin dashboard out of the box.

The legacy `django_matt.tasks` wrappers (Celery, Dramatiq, Django-Q) remain available for projects already using those queues.

---

## Quick Start (Native Engine)

```python
from django_matt.tasks_native import task, periodic_task, crontab, every
from pydantic import BaseModel

class WelcomePayload(BaseModel):
    user_id: int

@task
async def send_welcome_email(payload: WelcomePayload) -> None:
    user = await User.objects.aget(id=payload.user_id)
    await send_email(user.email, "Welcome!", "...")

@periodic_task(crontab(hour=0, minute=0))
async def cleanup_expired_tokens() -> None:
    await Token.objects.filter(expires_at__lt=now()).adelete()

# Enqueue — payload validated immediately, not inside the worker
send_welcome_email.delay(WelcomePayload(user_id=42))

# Dict is auto-coerced and validated
send_welcome_email.delay({"user_id": 42})
```

---

## Configuration

```python
# settings.py
MATT_TASKS = {
    "backend": "auto",  # auto | redis | postgres | rabbitmq | sync
    "url": "redis://localhost:6379/0",
}

INSTALLED_APPS = [
    ...
    "django_matt.tasks_native",   # Required for DLQ, purge, retry DB models
]
```

### Backend Auto-Detection

The engine selects the best available backend at startup. Zero overhead when `tasks_native` is not in `INSTALLED_APPS`.

| Django version | Default backend | Fallback chain |
|----------------|-----------------|----------------|
| 6.0+ | `DjangoNativeBackend` | Celery → Dramatiq → Sync |
| 5.x | `CeleryBackend` | Dramatiq → Django-Q → Sync |
| Dev / no broker | `SyncBackend` | — |

---

## Retry Policies

```python
from django_matt.tasks_native import task, retry

# Exponential backoff: 1s, 2s, 4s, 8s, 16s (default has jitter)
@task(retry=retry.exponential(max_retries=5, base_delay=1.0))
async def call_external_api(url: str) -> dict: ...

# Linear backoff: 10s, 20s, 30s
@task(retry=retry.linear(max_retries=3, delay=10))
async def send_webhook(payload: dict) -> None: ...

# Fixed delay: 60s, 60s, 60s
@task(retry=retry.fixed(delay=60, max_retries=3))
async def reliable_poll() -> None: ...

# Retry only on specific exceptions
@task(retry=retry.on_exception([ConnectionError, TimeoutError], max_retries=5, delay=5))
async def network_task() -> None: ...

# No retry — fail immediately
@task(retry=retry.none())
async def one_shot_task() -> None: ...

# Composite: combine multiple policies
@task(retry=retry.composite([
    retry.on_exception([ConnectionError], max_retries=5, delay=1),
    retry.on_exception([ValueError], max_retries=2, delay=10),
]))
async def complex_task() -> None: ...
```

---

## Scheduling (Database-Driven, No Celerybeat)

```python
from django_matt.tasks_native import periodic_task, crontab, every

@periodic_task(crontab(hour=2, minute=0))         # Daily at 2 AM
async def daily_report() -> None: ...

@periodic_task(every(minutes=5))                  # Every 5 minutes
async def check_health() -> None: ...

@periodic_task(crontab(day_of_week=1, hour=9))    # Mondays at 9 AM
async def weekly_digest() -> None: ...

@periodic_task(crontab(minute="*/15"))            # Every 15 minutes
async def sync_data() -> None: ...
```

Schedules are stored in the database and editable via the Unfold Admin dashboard — no redeploy needed.

---

## Workflows (Task Composition)

For Celery-style fan-out/fan-in patterns use the legacy wrappers (see [Legacy Backends](#legacy-backends) below). The native engine focuses on individual typed tasks with first-class retry/scheduling; for complex DAG workflows Celery remains the recommended choice.

---

## Admin Dashboard

Built on Django Unfold, available at `/admin/`:

- **Real-time task status** via WebSocket
- **Failure tracking** with full stack traces
- **Retry controls** — single task or bulk
- **Schedule management** — create, edit, disable periodic tasks without redeploy
- **Queue metrics** — throughput, duration, error rates
- **Filterable history** — search by status, task name, date

---

## CLI Reference

```bash
# List all registered tasks
python manage.py matt_tasks list

# List registered schedules
python manage.py matt_tasks schedules

# Run a task (enqueued to the queue)
python manage.py matt_tasks run myapp.tasks.send_welcome_email --payload '{"user_id": 42}'

# Run synchronously (bypasses queue — useful in dev)
python manage.py matt_tasks run myapp.tasks.send_welcome_email --payload '{"user_id": 42}' --sync

# Show queue status
python manage.py matt_tasks status

# Purge old completed tasks
python manage.py matt_tasks purge --older-than 30d

# Purge only failed tasks
python manage.py matt_tasks purge --older-than 7d --state failed

# Dry-run before purging
python manage.py matt_tasks purge --older-than 30d --dry-run

# Bulk retry failures from the last 24 hours
python manage.py matt_tasks retry --failed --last 24h

# Retry failures for a specific task only
python manage.py matt_tasks retry --failed --last 7d --task myapp.tasks.send_welcome_email

# JSON output
python manage.py matt_tasks list --format json
python manage.py matt_tasks status --format json
```

---

## Decision Guide

```
Dev / prototype with no broker?
  → SyncBackend (automatic, no config needed)

Django 6.0+ and want minimal infrastructure?
  → tasks_native with DjangoNativeBackend (auto-selected)

Need type-safe payloads, built-in admin, DB-driven schedules?
  → tasks_native (recommended for all new projects)

Already running Celery and need chains, chords, groups?
  → Keep Celery; use legacy django_matt.tasks wrappers

Can't run Redis and need database-only infrastructure?
  → Django-Q via legacy wrappers
```

---

## Legacy Backends

The `django_matt.tasks` module wraps Celery, Dramatiq, and Django-Q. Use these for existing projects that already depend on those brokers. New projects should prefer `tasks_native`.

```python
# settings.py (legacy wrappers)
DJANGO_MATT = {
    "TASKS": {
        "BACKEND": "celery",  # celery | dramatiq | django_q | sync
        "CELERY": {
            "BROKER_URL": "redis://localhost:6379/0",
            "RESULT_BACKEND": "redis://localhost:6379/1",
        },
    },
}
```

### Celery

```python
from django_matt.tasks import task, shared_task

@task
def send_email(to: str, subject: str, body: str): ...

@shared_task
def process_order(order_id: int): ...

# Start worker + beat
# celery -A config worker -l info
# celery -A config beat -l info
```

### Dramatiq

```python
DJANGO_MATT = {
    "TASKS": {
        "BACKEND": "dramatiq",
        "DRAMATIQ": {"BROKER": "redis://localhost:6379/0"},
    },
}
# python manage.py rundramatiq
```

### Django-Q

```python
DJANGO_MATT = {
    "TASKS": {
        "BACKEND": "django_q",
        "DJANGO_Q": {"workers": 4, "timeout": 90, "orm": "default"},
    },
}
# python manage.py qcluster
```

### Task Workflows (Celery-style)

```python
from django_matt.tasks import group, chain, chord

# Parallel
group(
    send_email.s("u1@example.com", "Hi", "Body"),
    send_email.s("u2@example.com", "Hi", "Body"),
).apply_async()

# Sequential
chain(fetch_data.s(url), process_data.s(), save_results.s()).apply_async()

# Fan-out / fan-in
chord(
    group(fetch_user.s(1), fetch_user.s(2)),
    aggregate_users.s(),
).apply_async()
```

### Switching Backends (Legacy)

Change one setting — task code using the legacy decorators stays the same:

```python
# Development
DJANGO_MATT = {"TASKS": {"BACKEND": "sync"}}

# Production
DJANGO_MATT = {
    "TASKS": {
        "BACKEND": "celery",
        "CELERY": {"BROKER_URL": "redis://localhost:6379/0"},
    },
}
```

---

## See Also

- [Native Task Engine](../tasks/overview.md) — complete tasks_native reference
- [Background Tasks recipe](../recipes/background-tasks.md)
- [Features: Tasks](tasks.md) — @task decorator, retry, scheduling, CLI, admin
