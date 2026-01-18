# Email Service Overview

django-matt provides a comprehensive email service with multiple provider support, templates, tracking, and delivery management.

## Features

- Multiple email providers (SMTP, SES, SendGrid, Mailgun)
- Template-based emails with variable interpolation
- Delivery tracking (opens, clicks, bounces)
- Suppression list management
- Scheduled sending
- Retry logic for failures

## Architecture

```mermaid
flowchart TB
    subgraph "Application"
        APP[Application Code]
        SVC[EmailService]
    end

    subgraph "Provider Layer"
        FACTORY[Provider Factory]
        SMTP[SMTP Provider]
        SES[SES Provider]
        SG[SendGrid Provider]
        MG[Mailgun Provider]
        CONSOLE[Console Provider]
    end

    subgraph "External"
        DJANGO[Django Email Backend]
        AWS[Amazon SES]
        SENDGRID[SendGrid API]
        MAILGUN[Mailgun API]
        STDOUT[Console Output]
    end

    subgraph "Storage"
        DB[(PostgreSQL)]
        CACHE[(Redis)]
    end

    APP --> SVC
    SVC --> FACTORY

    FACTORY --> SMTP
    FACTORY --> SES
    FACTORY --> SG
    FACTORY --> MG
    FACTORY --> CONSOLE

    SMTP --> DJANGO
    SES --> AWS
    SG --> SENDGRID
    MG --> MAILGUN
    CONSOLE --> STDOUT

    SVC --> DB
    SVC --> CACHE
```

## Email Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Pending: Email created
    Pending --> Queued: Scheduled
    Pending --> Sent: Send immediately
    Queued --> Sent: Schedule time reached

    Sent --> Delivered: Provider confirms
    Sent --> Bounced: Delivery failed
    Sent --> Failed: Send error

    Delivered --> Opened: Tracking pixel loaded
    Opened --> Clicked: Link clicked

    Bounced --> Suppressed: Add to list
    Failed --> Pending: Retry

    Clicked --> [*]
    Suppressed --> [*]
```

## Data Model

```mermaid
erDiagram
    EmailMessage ||--o{ EmailEvent : has
    EmailTemplate ||--o{ EmailMessage : used_by
    SuppressedEmail ||--o| EmailMessage : from

    EmailMessage {
        uuid id PK
        uuid tracking_id UK
        string from_email
        json to_emails
        string subject
        text text_body
        text html_body
        string status
        string provider
        string provider_message_id
        datetime scheduled_at
        datetime sent_at
        int retry_count
    }

    EmailEvent {
        uuid id PK
        uuid email_id FK
        string event_type
        datetime occurred_at
        string ip_address
        string user_agent
        string url
    }

    EmailTemplate {
        uuid id PK
        string name UK
        string subject
        text html_body
        text text_body
        json variables
        boolean is_active
        int version
    }

    SuppressedEmail {
        uuid id PK
        string email UK
        string reason
        string bounce_type
        datetime expires_at
    }
```

## Quick Start

### 1. Add to INSTALLED_APPS

```python
INSTALLED_APPS = [
    ...
    'django_matt.email',
]
```

### 2. Configure Provider

```python
DJANGO_MATT = {
    "EMAIL": {
        "DEFAULT_PROVIDER": "sendgrid",  # or smtp, ses, mailgun, console
        "DEFAULT_FROM": "noreply@example.com",

        # Provider-specific settings
        "SENDGRID_API_KEY": env("SENDGRID_API_KEY"),

        # Or for SES
        "AWS_SES_REGION": "us-east-1",

        # Or for Mailgun
        "MAILGUN_API_KEY": env("MAILGUN_API_KEY"),
        "MAILGUN_DOMAIN": "mg.example.com",
    }
}
```

### 3. Run Migrations

```bash
python manage.py migrate
```

### 4. Send an Email

```python
from django_matt.email import send_email

email = await send_email(
    to="user@example.com",
    subject="Welcome!",
    text="Thanks for signing up.",
    html="<h1>Thanks for signing up!</h1>",
)
```

## Related Documentation

- [Providers](./providers.md)
- [Templates](./templates.md)
- [Tracking](./tracking.md)
- [Suppression](./suppression.md)
