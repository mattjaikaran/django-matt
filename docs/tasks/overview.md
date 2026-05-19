# Native Task Engine

> Stage 17A — complete. Built-in background task system with Django 6.0 native worker support and Celery fallback for Django 5.x.

```mermaid
flowchart TB
    subgraph "Task Definition"
        TASK[@task decorator]
        PERIODIC[@periodic_task]
        PAYLOAD[Pydantic Payload]
    end

    subgraph "Execution"
        QUEUE[(Task Queue)]
        WORKER[Worker Process]
        RETRY[Retry Policy]
        DLQ[Dead Letter Queue]
    end

    subgraph "Monitoring"
        ADMIN[Unfold Admin Dashboard]
        METRICS[Queue Metrics]
        WS[WebSocket Real-time]
    end

    TASK --> QUEUE
    PERIODIC --> QUEUE
    PAYLOAD --> TASK
    QUEUE --> WORKER
    WORKER --> RETRY
    RETRY --> DLQ
    WORKER --> ADMIN
    METRICS --> ADMIN
    WS --> ADMIN
```

## Quick Start

```python
from django_matt.tasks_native import task, periodic_task
from pydantic import BaseModel

class EmailPayload(BaseModel):
    user_id: int
    template: str

@task
async def send_email(payload: EmailPayload) -> bool:
    """Payload validated at enqueue time — bad data raises immediately."""
    user = await User.objects.aget(id=payload.user_id)
    return await deliver_email(user, payload.template)

# Enqueue with validation
send_email.delay(EmailPayload(user_id=1, template="welcome"))

# Dict is auto-coerced
send_email.delay({"user_id": 1, "template": "welcome"})
```

## Configuration

```python
# settings.py
MATT_TASKS = {
    "backend": "auto",  # auto | redis | postgres | rabbitmq | sync
    "url": "redis://localhost:6379/0",
}
```

Add to `INSTALLED_APPS` to enable database models (required for DLQ, purge, retry commands):

```python
INSTALLED_APPS = [
    ...
    "django_matt.tasks_native",
]
```

### Backend Detection

The engine auto-detects the best available backend at startup. Zero overhead when the module is not installed.

| Django version | Default backend | Fallback chain |
|----------------|-----------------|----------------|
| 6.0+ | `DjangoNativeBackend` | Celery → Dramatiq → Sync |
| 5.x | `CeleryBackend` | Dramatiq → Django-Q → Sync |
| Dev / no broker | `SyncBackend` | — |

## Task Decorators

### Basic task

```python
from django_matt.tasks_native import task

@task
async def process_order(order_id: int) -> dict:
    order = await Order.objects.aget(id=order_id)
    await order.process()
    return {"status": "processed", "id": order_id}
```

### With options

```python
@task(
    queue="high-priority",
    priority=10,
    timeout=300,
    max_retries=5,
    retry_delay=60,
    rate_limit="10/m",  # 10 per minute
)
async def send_notification(user_id: int, message: str) -> None: ...
```

### Periodic tasks (database-driven, no celerybeat)

```python
from django_matt.tasks_native import periodic_task, crontab, every

@periodic_task(crontab(hour=9, minute=0))  # 9 AM daily
async def daily_report(): ...

@periodic_task(every(minutes=5))           # Every 5 minutes
async def health_check(): ...
```

Schedules are stored in the database and editable via Admin without redeploying.

## Retry Policies

```python
from django_matt.tasks_native import task, retry

@task(retry=retry.exponential(max_retries=5, base_delay=1.0))
async def flaky_api_call(url: str): ...   # Delays: 1s, 2s, 4s, 8s, 16s

@task(retry=retry.linear(max_retries=3, delay=10))
async def send_webhook(payload: dict): ... # Delays: 10s, 20s, 30s

@task(retry=retry.fixed(max_retries=3, delay=5))
async def simple_task(): ...               # Delays: 5s, 5s, 5s
```

Composite policies (e.g., exponential + jitter) are supported via `retry.composite()`.

## Failure and Success Handlers

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

## Task Results

```python
result = await send_email.delay(EmailPayload(user_id=1, template="welcome"))
print(result.task_id)

status = await send_email.get_status(result.task_id)
print(status.state)  # pending | running | completed | failed

final_result = await send_email.wait_result(result.task_id, timeout=30)
```

## Dead Letter Queue

Tasks that exhaust all retries are moved to the DLQ automatically:

```python
from django_matt.tasks_native import dlq

failed = await dlq.list()
await dlq.retry(task_id)
await dlq.purge(older_than_days=7)
```

DLQ entries are also visible and retryable from the Unfold Admin dashboard.

## Type Safety

Pydantic validation at enqueue time — errors surface immediately in the calling code, not later in the worker:

```python
class OrderPayload(BaseModel):
    order_id: int
    items: list[int]
    priority: Literal["normal", "rush"] = "normal"

@task
async def process_order(payload: OrderPayload): ...

# Raises TaskValidationError immediately (not inside the worker)
process_order.delay({"order_id": "not-an-int"})
```

## Admin Dashboard

Built on Django Unfold, included out of the box:

- **Real-time task status** via WebSocket
- **Failure tracking** with full stack traces
- **Retry controls** — single task or bulk retry
- **Schedule management** — create, edit, disable periodic tasks without redeploy
- **Queue metrics** — throughput, duration, error rates
- **Filterable history** — search by status, task name, date

## CLI Commands

```bash
# List all registered tasks
python manage.py matt_tasks list

# List registered schedules
python manage.py matt_tasks schedules

# Run a task (enqueued)
python manage.py matt_tasks run send_email --payload '{"user_id": 1, "template": "welcome"}'

# Run synchronously (bypasses queue)
python manage.py matt_tasks run send_email --payload '{}' --sync

# Show queue status
python manage.py matt_tasks status

# Purge old completed tasks
python manage.py matt_tasks purge --older-than 30d

# Purge by state
python manage.py matt_tasks purge --older-than 7d --state failed

# Dry run before purging
python manage.py matt_tasks purge --older-than 30d --dry-run

# Bulk retry failures from the last 24 hours
python manage.py matt_tasks retry --failed --last 24h

# Retry failures for a specific task only
python manage.py matt_tasks retry --failed --last 7d --task myapp.tasks.send_email
```

## Comparison with Celery

| Feature | Native Tasks | Celery |
|---------|--------------|--------|
| Type-safe payloads | Pydantic validation | Manual |
| Django 6.0 native workers | Built-in | External |
| Admin dashboard | Unfold integration | Flower (separate process) |
| Zero-config dev | Works without broker | Requires broker |
| Async support | Native async/await | gevent/eventlet workaround |
| DB-driven schedules | Editable via admin | Code-only (celerybeat) |
| Dead letter queue | Built-in | Plugin required |

## See Also

- [Features: Tasks](../features/tasks.md) — full @task reference, retry, scheduling, CLI, admin
- [Background Workers](../features/background-workers.md) — decision guide and legacy backend docs
- [Background Tasks recipe](../recipes/background-tasks.md)
