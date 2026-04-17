# Background Workers

django-matt provides a unified task API that works across multiple backend implementations. Write your tasks once, switch backends without code changes.

## Quick Start

```python
from django_matt.tasks import task, periodic_task

@task
async def send_welcome_email(user_id: int):
    user = await User.objects.aget(id=user_id)
    await send_email(user.email, "Welcome!", "...")

@periodic_task(crontab(hour=0, minute=0))
async def cleanup_expired_tokens():
    await Token.objects.filter(expires_at__lt=now()).adelete()

# Dispatch
await send_welcome_email.delay(user_id=42)
```

The same `@task` and `@periodic_task` decorators work regardless of which backend you configure.

## Backend Comparison

| Feature | Sync | Django Workers | Celery | Dramatiq | Django-Q |
|---------|------|---------------|--------|----------|----------|
| **Setup** | Zero | Django 6.0+ | Redis/RabbitMQ | Redis/RabbitMQ | Database |
| **Async** | No (inline) | Yes | Yes | Yes | No |
| **Priorities** | N/A | Yes | Yes | Yes | Yes |
| **Retries** | N/A | Basic | Full | Full | Basic |
| **Scheduling** | N/A | Basic | Celery Beat | APScheduler | Database |
| **Result backend** | In-memory | Limited | Redis/DB | Redis | Database |
| **Monitoring** | N/A | Django admin | Flower | Built-in | Django admin |
| **Distributed** | No | No | Yes | Yes | Optional |
| **Maturity** | N/A | New (6.0) | 15+ years | 5+ years | 5+ years |

## Configuration

```python
# settings.py
DJANGO_MATT_TASKS = {
    "BACKEND": "celery",  # sync, django_workers, celery, dramatiq, django_q
}
```

### Sync Backend (Development)

Executes tasks immediately in-process. No external services needed.

```python
DJANGO_MATT_TASKS = {"BACKEND": "sync"}
```

Or force sync execution in tests:

```python
DJANGO_MATT_TASKS = {"TASK_ALWAYS_EAGER": True}
```

### Django Native Workers (Django 6.0+)

Uses Django's built-in background workers from [DEP-0014](https://github.com/django/deps/blob/main/accepted/0014-background-workers.rst).

```python
DJANGO_MATT_TASKS = {"BACKEND": "django_workers"}
```

**Best for:** Simple background tasks, Django 6.0+ projects, teams that want minimal infrastructure.

### Celery

The industry standard for distributed task queues.

```python
DJANGO_MATT_TASKS = {
    "BACKEND": "celery",
    "CELERY_BROKER_URL": "redis://localhost:6379/0",
    "CELERY_RESULT_BACKEND": "redis://localhost:6379/1",
}
```

```bash
# Start worker
celery -A config worker -l info

# Start scheduler
celery -A config beat -l info
```

**Best for:** Large-scale systems, distributed workers, complex workflows (chains, chords, groups).

### Dramatiq

Modern alternative to Celery with simpler API and better defaults.

```python
DJANGO_MATT_TASKS = {
    "BACKEND": "dramatiq",
    "DRAMATIQ_BROKER": "redis://localhost:6379/0",
}
```

```bash
# Start worker
dramatiq config.tasks
```

**Best for:** Teams that want Celery-like power with less configuration.

### Django-Q

Database-backed task queue — no Redis or RabbitMQ needed.

```python
DJANGO_MATT_TASKS = {
    "BACKEND": "django_q",
}

Q_CLUSTER = {
    "name": "default",
    "workers": 4,
    "timeout": 90,
    "orm": "default",
}
```

```bash
python manage.py qcluster
```

**Best for:** Small deployments, projects that can't run Redis, database-only infrastructure.

## Task Features

### Retry Policies

```python
from django_matt.tasks import task
from django_matt.tasks.retry import ExponentialBackoff, LinearBackoff, FixedDelay

@task(retry_policy=ExponentialBackoff(max_retries=5, base_delay=1.0))
async def flaky_api_call(url: str):
    ...

@task(retry_policy=LinearBackoff(max_retries=3, delay=10.0))
async def send_notification(user_id: int):
    ...

@task(retry_policy=FixedDelay(max_retries=10, delay=60.0))
async def poll_external_service():
    ...
```

### Workflows

```python
from django_matt.tasks.primitives import chain, group, chord

# Sequential: A → B → C (result of each feeds into the next)
workflow = chain(fetch_data.s(url), process_data.s(), save_results.s())
workflow.delay()

# Parallel: A + B + C (all run concurrently)
workflow = group(resize_image.s(img, "sm"), resize_image.s(img, "md"), resize_image.s(img, "lg"))
workflow.delay()

# Fan-out/fan-in: parallel group → single callback
workflow = chord(
    [check_inventory.s(item) for item in items],
    create_order.s(),
)
workflow.delay()
```

### Scheduling

```python
from django_matt.tasks import periodic_task
from django_matt.tasks.scheduling import crontab, every

@periodic_task(crontab(hour=2, minute=0))  # Daily at 2 AM
async def daily_report():
    ...

@periodic_task(every(minutes=5))  # Every 5 minutes
async def check_health():
    ...

@periodic_task(crontab(day_of_week=1, hour=9))  # Monday at 9 AM
async def weekly_digest():
    ...
```

## Decision Guide

```
Solo dev / prototype?
  → Sync backend (zero setup)

Django 6.0+ and simple tasks?
  → Django native workers

Need distributed workers or complex workflows?
  → Celery (proven) or Dramatiq (modern)

Can't run Redis?
  → Django-Q (database-backed)

Testing?
  → Sync backend with TASK_ALWAYS_EAGER = True
```

## Scale Recommendations

| Scale | Recommendation |
|-------|---------------|
| **Prototype** | Sync — no infrastructure needed |
| **Solo / small team** | Django Workers or Django-Q |
| **Startup** | Celery with Redis |
| **Growth** | Celery with RabbitMQ + Flower monitoring |
| **Enterprise** | Celery with dedicated workers per queue |

## Switching Backends

Change one setting — your task code stays the same:

```python
# Before (development)
DJANGO_MATT_TASKS = {"BACKEND": "sync"}

# After (production)
DJANGO_MATT_TASKS = {
    "BACKEND": "celery",
    "CELERY_BROKER_URL": "redis://localhost:6379/0",
}
```

All `@task` and `@periodic_task` decorators, retry policies, and workflow primitives work identically across backends.

## API Reference

- `django_matt.tasks.decorators.task` — register a function as a background task
- `django_matt.tasks.decorators.periodic_task` — register a scheduled task
- `django_matt.tasks.config.get_backend()` — get the configured backend instance
- `django_matt.tasks.retry.ExponentialBackoff` — exponential retry policy
- `django_matt.tasks.retry.LinearBackoff` — linear retry policy
- `django_matt.tasks.retry.FixedDelay` — fixed-delay retry policy
- `django_matt.tasks.primitives.chain` — sequential task workflow
- `django_matt.tasks.primitives.group` — parallel task workflow
- `django_matt.tasks.primitives.chord` — fan-out/fan-in workflow
- `django_matt.tasks.scheduling.crontab` — cron-style schedule
- `django_matt.tasks.scheduling.every` — interval-based schedule
