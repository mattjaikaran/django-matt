# Background Tasks

Run tasks asynchronously with Celery, Dramatiq, or Django-Q.

## Configuration

```python
# settings.py
DJANGO_MATT = {
    "TASKS": {
        "BACKEND": "celery",  # or "dramatiq", "django_q", "sync"
        "CELERY": {
            "BROKER_URL": "redis://localhost:6379/0",
            "RESULT_BACKEND": "redis://localhost:6379/1",
        },
    },
}
```

## Task Decorators

### @task

```python
from django_matt.tasks import task

@task
def send_email(to: str, subject: str, body: str):
    # Send email
    ...

# Call the task
send_email.delay("user@example.com", "Hello", "World")
```

### @shared_task

```python
from django_matt.tasks import shared_task

@shared_task
def process_order(order_id: int):
    order = Order.objects.get(id=order_id)
    # Process order
    ...

# Call from anywhere
process_order.delay(123)
```

### @periodic_task

```python
from django_matt.tasks import periodic_task, crontab, every

@periodic_task(crontab(hour=0, minute=0))  # Daily at midnight
def daily_cleanup():
    # Cleanup old records
    ...

@periodic_task(every(minutes=5))  # Every 5 minutes
def check_health():
    # Health check
    ...
```

## Retry Policies

```python
from django_matt.tasks import task, ExponentialBackoff, LinearBackoff, FixedDelay

@task(retry_policy=ExponentialBackoff(max_retries=5, base_delay=1))
def flaky_task():
    # Retries: 1s, 2s, 4s, 8s, 16s
    ...

@task(retry_policy=LinearBackoff(max_retries=3, delay=5))
def linear_retry_task():
    # Retries: 5s, 10s, 15s
    ...

@task(retry_policy=FixedDelay(max_retries=3, delay=10))
def fixed_retry_task():
    # Retries: 10s, 10s, 10s
    ...
```

## Task Primitives

### Groups (Parallel)

```python
from django_matt.tasks import group

# Run tasks in parallel
result = group(
    send_email.s("user1@example.com", "Hello", "World"),
    send_email.s("user2@example.com", "Hello", "World"),
    send_email.s("user3@example.com", "Hello", "World"),
).apply_async()

# Wait for all to complete
result.get()
```

### Chains (Sequential)

```python
from django_matt.tasks import chain

# Run tasks sequentially, passing results
result = chain(
    fetch_data.s(url),
    process_data.s(),
    save_results.s(),
).apply_async()
```

### Chords (Group + Callback)

```python
from django_matt.tasks import chord

# Run group, then callback with all results
result = chord(
    group(
        fetch_user.s(1),
        fetch_user.s(2),
        fetch_user.s(3),
    ),
    aggregate_users.s(),
).apply_async()
```

## Backends

### Celery

```python
# settings.py
DJANGO_MATT = {
    "TASKS": {
        "BACKEND": "celery",
        "CELERY": {
            "BROKER_URL": "redis://localhost:6379/0",
            "RESULT_BACKEND": "redis://localhost:6379/1",
            "TASK_SERIALIZER": "json",
            "RESULT_SERIALIZER": "json",
            "ACCEPT_CONTENT": ["json"],
            "TIMEZONE": "UTC",
        },
    },
}

# Run worker
# celery -A myproject worker -l info
```

### Dramatiq

```python
# settings.py
DJANGO_MATT = {
    "TASKS": {
        "BACKEND": "dramatiq",
        "DRAMATIQ": {
            "BROKER": "redis://localhost:6379/0",
            "RESULT_BACKEND": "redis://localhost:6379/1",
        },
    },
}

# Run worker
# python manage.py rundramatiq
```

### Django-Q

```python
# settings.py
DJANGO_MATT = {
    "TASKS": {
        "BACKEND": "django_q",
        "DJANGO_Q": {
            "name": "DjangORM",
            "workers": 4,
            "timeout": 90,
            "retry": 120,
            "orm": "default",
        },
    },
}

# Run worker
# python manage.py qcluster
```

### Sync (Development)

```python
# settings.py
DJANGO_MATT = {
    "TASKS": {
        "BACKEND": "sync",  # Tasks run synchronously
    },
}
```

## Scheduling

```python
from django_matt.tasks import Scheduler, crontab, every

scheduler = Scheduler()

# Cron-style scheduling
scheduler.add(
    daily_cleanup,
    crontab(hour=0, minute=0),
    name="daily-cleanup",
)

# Interval scheduling
scheduler.add(
    health_check,
    every(minutes=5),
    name="health-check",
)

# Start scheduler
scheduler.start()
```

## Using in Views

```python
@api.post("/orders")
async def create_order(request, data: OrderCreate):
    order = await Order.objects.acreate(**data.model_dump())

    # Queue background tasks
    send_order_confirmation.delay(order.id)
    update_inventory.delay(order.id)

    return {"order_id": order.id}
```
