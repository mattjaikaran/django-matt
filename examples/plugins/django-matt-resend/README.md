# django-matt-resend

Resend email backend for django-matt. Drop-in Django email backend that sends
transactional email via the Resend API.

## Installation

```bash
uv add django-matt-resend
```

## Configuration

```python
# settings.py
EMAIL_BACKEND = "django_matt_resend.backend.ResendEmailBackend"

MATT_RESEND = {
    "API_KEY": "re_...",
    "DEFAULT_FROM": "noreply@yourdomain.com",
    "REPLY_TO": "support@yourdomain.com",  # optional
}
```

## Usage

### Standard Django email

```python
from django.core.mail import send_mail

await send_mail(
    subject="Welcome!",
    message="Thanks for signing up.",
    from_email=None,  # uses DEFAULT_FROM
    recipient_list=["user@example.com"],
)
```

### Resend templates

```python
from django_matt_resend.templates import send_template

await send_template(
    template_id="tmpl_abc123",
    to=["user@example.com"],
    data={"name": "Alice", "action_url": "https://example.com/verify"},
)
```

### Batch sending

```python
from django_matt_resend.backend import ResendEmailBackend

backend = ResendEmailBackend()
messages = [email1, email2, email3]
sent = await backend.asend_messages(messages)
```
