# Email Suppression

Automatic suppression list management that prevents sending to bounced, complained, or unsubscribed email addresses. Integrated with the email service and provider webhook handlers.

## Quick Start

```python
from django_matt.email.models import SuppressedEmail

# Check if an email is suppressed
if SuppressedEmail.is_suppressed("user@example.com"):
    print("This address is suppressed")

# Add to suppression list
SuppressedEmail.add_suppression(
    email="bounced@example.com",
    reason="bounce",
    bounce_type="hard",
)

# Remove from suppression list
SuppressedEmail.objects.filter(email="user@example.com").delete()
```

## Configuration

The suppression system works automatically when using the `EmailService`. No additional configuration is needed. The service calls `provider.filter_suppressed()` before sending, which checks the `SuppressedEmail` model.

## Key Features

### SuppressedEmail Model

The `SuppressedEmail` model stores addresses that should not receive emails:

| Field | Type | Description |
|-------|------|-------------|
| `email` | `EmailField` | Suppressed email address (unique, case-insensitive) |
| `reason` | `CharField` | Why suppressed: `bounce`, `complaint`, `unsubscribe`, `manual` |
| `bounce_type` | `CharField` | Bounce classification: `hard`, `soft`, `undetermined` |
| `source_email` | `ForeignKey` | The EmailMessage that caused suppression |
| `created_at` | `DateTimeField` | When the suppression was created |
| `expires_at` | `DateTimeField` | Optional expiry (for soft bounces) |

### Checking Suppression

```python
from django_matt.email.models import SuppressedEmail

# Single check (respects expiry)
is_blocked = SuppressedEmail.is_suppressed("user@example.com")

# The check is case-insensitive and respects expires_at:
# - If expires_at is NULL, the suppression is permanent
# - If expires_at is in the future, still suppressed
# - If expires_at is in the past, no longer suppressed
```

### Adding Suppressions

```python
from django_matt.email.models import SuppressedEmail
from datetime import timedelta
from django.utils import timezone

# Hard bounce (permanent)
SuppressedEmail.add_suppression(
    email="invalid@example.com",
    reason="bounce",
    bounce_type="hard",
)

# Soft bounce (temporary, expires in 72 hours)
SuppressedEmail.add_suppression(
    email="full-mailbox@example.com",
    reason="bounce",
    bounce_type="soft",
    expires_at=timezone.now() + timedelta(hours=72),
)

# User unsubscribe
SuppressedEmail.add_suppression(
    email="user@example.com",
    reason="unsubscribe",
)

# Manual suppression with source tracking
SuppressedEmail.add_suppression(
    email="problem@example.com",
    reason="manual",
    source_email=email_message_instance,
)
```

`add_suppression` uses `update_or_create`, so calling it for an already-suppressed address updates the reason and metadata.

### Automatic Filtering in EmailService

The `EmailService.send()` method automatically filters suppressed recipients:

```python
from django_matt.email.service import send_email

# If alice@example.com is suppressed, only bob gets the email.
# If ALL recipients are suppressed, the email is marked FAILED.
email = send_email(
    to=["alice@example.com", "bob@example.com"],
    subject="Newsletter",
    html="<p>Content</p>",
)
```

The internal flow:
1. `EmailService._send_email()` calls `provider.filter_suppressed(email.to_emails)`
2. Suppressed addresses are removed from the recipient list
3. If no valid recipients remain, the email is marked `FAILED` with error `"All recipients are suppressed"`
4. Otherwise, the email sends to valid recipients only

### Bounce Handling

When email providers report bounces via webhooks, the system automatically adds suppressions:

```python
from django_matt.email.models import EmailMessage, SuppressedEmail
from django_matt.email.enums import BounceType

# Called by webhook handler
email = EmailMessage.objects.get(tracking_id=tracking_id)
email.mark_bounced(bounce_type=BounceType.HARD)

# Add to suppression list
for recipient in email.to_emails:
    SuppressedEmail.add_suppression(
        email=recipient,
        reason="bounce",
        bounce_type="hard",
        source_email=email,
    )
```

### Email Statistics

Track suppression impact through the email stats API:

```python
from django_matt.email.service import EmailService

stats = EmailService.get_email_stats(
    start_date=start,
    end_date=end,
)
# Returns: total, sent, delivered, opened, clicked, bounced, failed, pending
# Plus calculated rates: delivery_rate, open_rate, click_rate, bounce_rate
```

## Practical Example

A management command to audit and clean the suppression list:

```python
from django.core.management.base import BaseCommand
from django.utils import timezone
from django_matt.email.models import SuppressedEmail

class Command(BaseCommand):
    help = "Audit the email suppression list"

    def handle(self, *args, **options):
        total = SuppressedEmail.objects.count()
        by_reason = {}
        for reason in ["bounce", "complaint", "unsubscribe", "manual"]:
            by_reason[reason] = SuppressedEmail.objects.filter(reason=reason).count()

        # Remove expired soft bounces
        expired = SuppressedEmail.objects.filter(
            expires_at__lt=timezone.now(),
        ).delete()

        self.stdout.write(f"Total suppressed: {total}")
        for reason, count in by_reason.items():
            self.stdout.write(f"  {reason}: {count}")
        self.stdout.write(f"Expired entries removed: {expired[0]}")
```
