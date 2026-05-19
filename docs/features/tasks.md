# Background Tasks

Django Matt ships a built-in native task engine (`tasks_native`) as the recommended approach. The older Celery/Dramatiq/Django-Q wrappers in `django_matt.tasks` remain available for projects that already use them.

---

## Native Task Engine (Recommended)

`django_matt.tasks_native` — type-safe, zero-broker-required background tasks that run on Django 6.0's built-in workers and fall back to Celery on Django 5.x.

### Configuration

```python
# settings.py
MATT_TASKS = {
    "backend": "auto",  # auto | redis | postgres | rabbitmq | sync
    "url": "redis://localhost:6379/0",
}
```

Auto-detection order:

| Django version | Primary backend | Fallback |
|----------------|-----------------|----------|
| 6.0+ | `DjangoNativeBackend` | Celery → Dramatiq → Sync |
| 5.x | `CeleryBackend` | Dramatiq → Django-Q → Sync |
| Dev / no broker | `SyncBackend` | — |

Zero overhead when not enabled — the module loads only when `tasks_native` is in `INSTALLED_APPS`.

### @task decorator

```python
from django_matt.tasks_native import task
from pydantic import BaseModel

class EmailPayload(BaseModel):
    user_id: int
    template: str

@task
async def send_email(payload: EmailPayload) -> bool:
    """Payload is validated at enqueue time, not inside the worker."""
    user = await User.objects.aget(id=payload.user_id)
    return await deliver_email(user, payload.template)

# Enqueue — validates immediately, raises ValidationError if invalid
send_email.delay(EmailPayload(user_id=1, template="welcome"))

# Dict is auto-coerced and validated
send_email.delay({"user_id": 1, "template": "welcome"})
```

#### Decorator options

```python
@task(
    queue="high-priority",
    priority=10,
    timeout=300,
    max_retries=5,
    retry_delay=60,
    rate_limit="10/m",
)
async def send_notification(user_id: int, message: str) -> None: ...
```

### Retry policies

```python
from django_matt.tasks_native import task, retry

@task(retry=retry.exponential(max_retries=5, base_delay=1.0))
async def flaky_api_call(url: str): ...

@task(retry=retry.linear(max_retries=3, delay=10))
async def send_webhook(payload: dict): ...

@task(retry=retry.fixed(max_retries=3, delay=5))
async def simple_task(): ...
```

### Periodic tasks (database-driven, no celerybeat)

```python
from django_matt.tasks_native import periodic_task, crontab, every

@periodic_task(crontab(hour=9, minute=0))   # 9 AM daily
async def daily_report(): ...

@periodic_task(every(minutes=5))            # Every 5 minutes
async def health_check(): ...
```

Schedules are stored in the database and editable via the Unfold Admin dashboard — no redeploy needed.

### Failure and success handlers

```python
@task
async def send_email(user_id: int): ...

@send_email.on_failure
async def handle_email_failure(task, exc, payload):
    await notify_ops(f"Email task failed: {exc}")

@send_email.on_success
async def handle_email_success(task, result, payload):
    await log_success(payload.user_id)
```

### Dead letter queue

Failed tasks that exhaust all retries move to the DLQ automatically:

```python
from django_matt.tasks_native import dlq

failed = await dlq.list()
await dlq.retry(task_id)
await dlq.purge(older_than_days=7)
```

### Task results

```python
result = await send_email.delay(EmailPayload(user_id=1, template="welcome"))
print(result.task_id)

status = await send_email.get_status(result.task_id)
print(status.state)  # pending | running | completed | failed

final = await send_email.wait_result(result.task_id, timeout=30)
```

### Admin dashboard

Built on Django Unfold:

- Real-time task status via WebSocket
- Failure tracking with full stack traces
- Retry controls — single task or bulk
- Schedule management — create, edit, disable periodic tasks without redeploy
- Queue metrics — throughput, duration, error rates
- Filterable history — search by status, task name, date

### CLI commands

```bash
# List all registered tasks
python manage.py matt_tasks list

# List registered schedules
python manage.py matt_tasks schedules

# Run a task manually (enqueued)
python manage.py matt_tasks run send_email --payload '{"user_id": 1, "template": "welcome"}'

# Run synchronously (skips the queue)
python manage.py matt_tasks run send_email --payload '{}' --sync

# Queue status
python manage.py matt_tasks status

# Purge old completed tasks
python manage.py matt_tasks purge --older-than 30d

# Bulk retry failures from the last 24 hours
python manage.py matt_tasks retry --failed --last 24h
```

### Using in views

```python
@api.post("/orders")
async def create_order(request, data: OrderCreate):
    order = await Order.objects.acreate(**data.model_dump())

    send_order_confirmation.delay(order.id)
    update_inventory.delay(order.id)

    return {"order_id": order.id}
```

---

## Legacy: Celery / Dramatiq / Django-Q Wrappers

The `django_matt.tasks` module wraps third-party task backends and remains supported for existing projects. New projects should prefer `tasks_native`.

### Configuration

```python
# settings.py
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

### @task and @shared_task

```python
from django_matt.tasks import task, shared_task

@task
def send_email(to: str, subject: str, body: str):
    ...

send_email.delay("user@example.com", "Hello", "World")

@shared_task
def process_order(order_id: int):
    order = Order.objects.get(id=order_id)
    ...
```

### Retry policies (legacy wrappers)

```python
from django_matt.tasks import task, ExponentialBackoff, LinearBackoff, FixedDelay

@task(retry_policy=ExponentialBackoff(max_retries=5, base_delay=1))
def flaky_task(): ...

@task(retry_policy=LinearBackoff(max_retries=3, delay=5))
def linear_retry_task(): ...

@task(retry_policy=FixedDelay(max_retries=3, delay=10))
def fixed_retry_task(): ...
```

### Task primitives (Celery-style)

```python
from django_matt.tasks import group, chain, chord

# Parallel
group(
    send_email.s("u1@example.com", "Hi", "Body"),
    send_email.s("u2@example.com", "Hi", "Body"),
).apply_async()

# Sequential
chain(fetch_data.s(url), process_data.s(), save_results.s()).apply_async()

# Group + callback
chord(
    group(fetch_user.s(1), fetch_user.s(2)),
    aggregate_users.s(),
).apply_async()
```

### Backends

#### Celery

```python
DJANGO_MATT = {
    "TASKS": {
        "BACKEND": "celery",
        "CELERY": {
            "BROKER_URL": "redis://localhost:6379/0",
            "RESULT_BACKEND": "redis://localhost:6379/1",
            "TASK_SERIALIZER": "json",
            "ACCEPT_CONTENT": ["json"],
            "TIMEZONE": "UTC",
        },
    },
}
# celery -A myproject worker -l info
```

#### Dramatiq

```python
DJANGO_MATT = {
    "TASKS": {
        "BACKEND": "dramatiq",
        "DRAMATIQ": {"BROKER": "redis://localhost:6379/0"},
    },
}
# python manage.py rundramatiq
```

#### Django-Q

```python
DJANGO_MATT = {
    "TASKS": {
        "BACKEND": "django_q",
        "DJANGO_Q": {"workers": 4, "timeout": 90, "orm": "default"},
    },
}
# python manage.py qcluster
```

#### Sync (development)

```python
DJANGO_MATT = {"TASKS": {"BACKEND": "sync"}}
```

---

## See Also

- [Native Task Engine overview](../tasks/overview.md)
- [Background Workers](background-workers.md) — decision guide and legacy backend docs
- [Background Tasks recipe](../recipes/background-tasks.md)
