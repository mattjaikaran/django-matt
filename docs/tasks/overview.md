# Native Task Engine

> Stage 17A: Built-in background task system with Django 6.0 native support.

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
    end

    subgraph "Monitoring"
        ADMIN[Unfold Admin Dashboard]
        METRICS[Queue Metrics]
    end

    TASK --> QUEUE
    PERIODIC --> QUEUE
    PAYLOAD --> TASK
    QUEUE --> WORKER
    WORKER --> ADMIN
    METRICS --> ADMIN
```

## Quick Start

```python
from django_matt.tasks import task, periodic_task
from pydantic import BaseModel

class EmailPayload(BaseModel):
    user_id: int
    template: str

@task
async def send_email(payload: EmailPayload) -> bool:
    """Fully typed, validated at enqueue time."""
    user = await User.objects.aget(id=payload.user_id)
    return await deliver_email(user, payload.template)

# Enqueue - validates payload automatically
send_email.delay(EmailPayload(user_id=1, template="welcome"))
```

## Configuration

```python
# settings.py
MATT_TASKS = {
    "backend": "auto",  # auto, redis, postgres, rabbitmq, sync
    "url": "redis://localhost:6379/0",
}
```

### Backend Detection

The task engine auto-detects the best available backend:

| Django Version | Default Backend | Fallback |
|----------------|-----------------|----------|
| 6.0+ | `DjangoNativeBackend` | Celery, Dramatiq, Sync |
| 5.x | `CeleryBackend` | Dramatiq, Django-Q, Sync |
| Development | `SyncBackend` | - |

## Task Decorators

### Basic Task

```python
from django_matt.tasks import task

@task
async def process_order(order_id: int) -> dict:
    order = await Order.objects.aget(id=order_id)
    await order.process()
    return {"status": "processed", "id": order_id}
```

### With Options

```python
@task(
    queue="high-priority",
    priority=10,
    timeout=300,
    max_retries=5,
    retry_delay=60,
    rate_limit="10/m",  # 10 per minute
)
async def send_notification(user_id: int, message: str) -> None:
    ...
```

### Periodic Tasks

```python
from django_matt.tasks import periodic_task, crontab, every

@periodic_task(crontab(hour=9, minute=0))  # 9 AM daily
async def daily_report():
    ...

@periodic_task(every(minutes=5))  # Every 5 minutes
async def health_check():
    ...
```

## Retry Policies

```python
from django_matt.tasks import task, retry

@task(retry=retry.exponential(max_retries=5, base_delay=1.0))
async def flaky_api_call(url: str):
    ...

@task(retry=retry.linear(max_retries=3, delay=10))
async def send_webhook(payload: dict):
    ...

@task(retry=retry.fixed(max_retries=3, delay=5))
async def simple_task():
    ...
```

## Error Handlers

```python
@task
async def send_email(user_id: int):
    ...

@send_email.on_failure
async def handle_email_failure(task, exc, payload):
    await notify_ops(f"Email task failed: {exc}")

@send_email.on_success
async def handle_email_success(task, result, payload):
    await log_success(payload.user_id)
```

## Task Results

```python
# Get task result
result = await send_email.delay(EmailPayload(user_id=1, template="welcome"))
print(result.task_id)

# Check status
status = await send_email.get_status(result.task_id)
print(status.state)  # pending, running, completed, failed

# Wait for result
final_result = await send_email.wait_result(result.task_id, timeout=30)
```

## Admin Dashboard

The task system includes a full admin dashboard built on Django Unfold:

- **Real-time task status** with WebSocket updates
- **Failure tracking** with full stack traces
- **Retry controls** - retry single or bulk retry
- **Schedule management** - create/edit/disable periodic tasks
- **Queue metrics** - throughput, duration, error rates
- **Filterable history** - search by status, task name, date

## CLI Commands

```bash
# List registered tasks
python manage.py matt_tasks list

# Run task manually
python manage.py matt_tasks run send_email '{"user_id": 1, "template": "welcome"}'

# Check queue status
python manage.py matt_tasks status

# Purge old completed tasks
python manage.py matt_tasks purge --older-than 30d
```

## Dead Letter Queue

Failed tasks after max retries are moved to the Dead Letter Queue (DLQ):

```python
from django_matt.tasks import dlq

# List failed tasks
failed = await dlq.list()

# Retry a failed task
await dlq.retry(task_id)

# Purge old failures
await dlq.purge(older_than_days=7)
```

## Type Safety

All task payloads are validated using Pydantic:

```python
class OrderPayload(BaseModel):
    order_id: int
    items: list[int]
    priority: Literal["normal", "rush"] = "normal"

@task
async def process_order(payload: OrderPayload):
    ...

# This raises ValidationError at enqueue time (not in worker!)
process_order.delay({"order_id": "invalid"})  # Fails immediately
```

## Comparison with Celery

| Feature | Native Tasks | Celery |
|---------|--------------|--------|
| Type-safe payloads | ✅ Pydantic validation | ❌ Manual |
| Django 6.0 native | ✅ Built-in | ❌ External |
| Admin dashboard | ✅ Unfold integration | ❌ Flower (separate) |
| Zero-config dev | ✅ Works out of box | ❌ Requires broker |
| Async support | ✅ Native async | ⚠️ gevent/eventlet |
| DB-driven schedules | ✅ Editable via admin | ❌ Code-only |

## See Also

- [Retry Policies](./retry.md)
- [Scheduling](./scheduling.md)
- [Admin Dashboard](./admin.md)
- [Backend Configuration](./backends.md)
