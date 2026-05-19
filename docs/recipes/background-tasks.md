# Background Tasks

Native task engine, Celery/Dramatiq integration, retry policies, and scheduling.

---

## Native Tasks (recommended)

The native task engine requires no external broker for simple use cases. For production scale, swap in a backend (Redis, database).

### Define a task

```python
from django_matt.tasks_native import task
from pydantic import BaseModel

class WelcomePayload(BaseModel):
    user_id: int
    template: str = "welcome"

@task
async def send_welcome_email(payload: WelcomePayload) -> bool:
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = await User.objects.aget(id=payload.user_id)
    await deliver_email(user, payload.template)
    return True
```

### Enqueue

```python
# Default queue
send_welcome_email.delay({"user_id": 42})

# With options
send_welcome_email.apply_async(
    args=[{"user_id": 42}],
    countdown=60,                    # delay 60 seconds
    eta=datetime(2025, 1, 1, 9, 0), # or run at specific time
    queue="email",
    priority=5,
)

# Run synchronously (tests, management commands)
result = send_welcome_email.apply(args=[{"user_id": 42}], throw=True)
```

### Callbacks

```python
@send_welcome_email.on_success
async def on_success(result, payload):
    await log_email_sent(payload["user_id"])

@send_welcome_email.on_failure
async def on_failure(exc, payload):
    await alert_team(f"Email failed for user {payload['user_id']}: {exc}")
```

---

## Retry Policies

```python
from django_matt.tasks_native import task, retry

@task(retry_policy=retry.exponential(max_retries=5, base_delay=1.0, max_delay=300.0))
async def flaky_api_call(payload):
    ...

# Linear backoff
@task(retry_policy=retry.linear(max_retries=3, delay=10.0, increment=5.0))
async def send_sms(payload):
    ...

# Fixed delay
@task(retry_policy=retry.fixed(delay=60.0, max_retries=3))
async def sync_crm(payload):
    ...

# Retry only on specific exceptions
@task(retry_policy=retry.on_exception([ConnectionError, TimeoutError], max_retries=3))
async def fetch_external(payload):
    ...

# Combine policies
@task(retry_policy=retry.composite([
    retry.on_exception([RateLimitError], max_retries=5, delay=30.0),
    retry.exponential(max_retries=3),
]))
async def resilient_task(payload):
    ...
```

---

## Periodic / Scheduled Tasks

```python
from django_matt.tasks_native import periodic_task, crontab, every

# Crontab syntax
@periodic_task(crontab(hour=9, minute=0))            # 9 AM daily
async def daily_digest():
    await send_daily_digest()

@periodic_task(crontab(minute="*/15"))               # every 15 minutes
async def sync_data():
    await pull_external_data()

@periodic_task(crontab(day_of_week="1-5", hour=8))  # weekdays at 8 AM
async def morning_report():
    await generate_report()

# Interval syntax
@periodic_task(every(minutes=5))
async def health_check():
    await ping_services()

@periodic_task(every(hours=1))
async def cleanup_sessions():
    await expire_old_sessions()
```

---

## Task Registry

```python
from django_matt.tasks_native.registry import task_registry

# List all registered tasks
for name, task in task_registry.all():
    print(name)

# Look up a task by name (e.g. from a webhook payload)
task_fn = task_registry.get_or_raise("myapp.tasks.send_welcome_email")
task_fn.delay(payload)
```

---

## Celery Integration

Use the `@task` decorator from `django_matt.tasks` for Celery-compatible queuing:

```python
from django_matt.tasks import task, shared_task

@task(retry=3, retry_delay=60, queue="default", timeout=300)
def process_payment(order_id: int):
    order = Order.objects.get(id=order_id)
    charge(order)

# Shared task (importable from any app)
@shared_task
def send_notification(user_id: int, message: str):
    ...
```

### Enqueue (Celery)

```python
# Immediate
process_payment.delay(order_id=123)

# With options
process_payment.apply_async(
    args=[123],
    countdown=10,
    queue="payments",
    priority=9,
    expires=600,
)
```

### Celery retry policies

```python
from django_matt.tasks import task
from django_matt.tasks.retry import ExponentialBackoff, FixedDelay

@task(retry_policy=ExponentialBackoff(
    initial_delay=2.0,
    max_delay=120.0,
    multiplier=2.0,
    max_retries=5,
))
def resilient_task():
    ...
```

---

## Celery Periodic Tasks

```python
from django_matt.tasks import periodic_task, crontab, every, schedule

@periodic_task(crontab(hour=0, minute=0))
def nightly_cleanup():
    OldRecord.objects.filter(created_at__lt=days_ago(90)).delete()

# Decouple schedule from definition
@schedule(every(hours=6))
@task
def refresh_cache():
    warm_caches()
```

---

## Task Composition (Celery)

```python
from django_matt.tasks import group, chain

# Parallel
result = group(
    process_image.s(img_id) for img_id in image_ids
).apply_async()

# Sequential pipeline
pipeline = chain(
    validate_order.s(order_id),
    charge_payment.s(),
    send_confirmation.s(),
)
pipeline.delay()
```

---

## Management Commands

```bash
# Native task engine
python manage.py matt_tasks list               # registered tasks
python manage.py matt_tasks run send_welcome_email '{"user_id": 1}'
python manage.py matt_tasks status            # queue depth
python manage.py matt_tasks purge --older-than 30d
```

---

## Choosing Native vs Celery

| | Native | Celery |
|---|---|---|
| Broker required | No (or Redis) | Yes (Redis / RabbitMQ) |
| Async-first | Yes | Partial |
| Pydantic validation | Built-in | Manual |
| Periodic tasks | Built-in | Beat required |
| Task composition | Limited | Full (`group`, `chain`, `chord`) |
| Dashboard | Unfold (Stage 17A) | Flower |
| Best for | Simple apps, async workloads | Complex pipelines, high throughput |
