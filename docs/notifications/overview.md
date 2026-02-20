# Notifications System Overview

django-matt provides a unified notification system supporting multiple delivery channels with user preferences.

## Features

- Multi-channel delivery (in-app, email, push, SMS, webhook)
- User preferences per notification type
- Priority levels and quiet hours
- Delivery tracking and retry
- Real-time in-app notifications

## Architecture

```mermaid
flowchart TB
    subgraph "Notification Sources"
        APP[Application Code]
        SIGNAL[Django Signals]
        WEBHOOK[Incoming Webhooks]
    end

    subgraph "Notification Service"
        SVC[NotificationService]
        PREF[Preferences Engine]
        QUEUE[Delivery Queue]
    end

    subgraph "Delivery Service"
        DEL[DeliveryService]
        INAPP[In-App Handler]
        EMAIL[Email Handler]
        PUSH[Push Handler]
        SMS[SMS Handler]
        WH[Webhook Handler]
    end

    subgraph "External Services"
        MAIL[Email Provider]
        FCM[Firebase FCM]
        APNS[Apple APNs]
        TWILIO[Twilio]
        EXT[External Webhooks]
    end

    APP --> SVC
    SIGNAL --> SVC
    WEBHOOK --> SVC

    SVC --> PREF
    PREF --> QUEUE
    QUEUE --> DEL

    DEL --> INAPP
    DEL --> EMAIL
    DEL --> PUSH
    DEL --> SMS
    DEL --> WH

    EMAIL --> MAIL
    PUSH --> FCM
    PUSH --> APNS
    SMS --> TWILIO
    WH --> EXT
```

## Delivery Flow

```mermaid
sequenceDiagram
    participant A as Application
    participant N as NotificationService
    participant P as Preferences
    participant D as DeliveryService
    participant C as Channels

    A->>N: notify(user, type, data)
    N->>P: Get user preferences
    P->>N: Active channels for type

    loop For each channel
        N->>D: Queue delivery
        D->>D: Check quiet hours
        D->>C: Deliver
        C->>D: Result
        D->>D: Update status
    end

    N->>A: Notification created
```

## Data Model

```mermaid
erDiagram
    User ||--o{ Notification : receives
    User ||--o| NotificationPreferences : has
    User ||--o{ NotificationRule : configures
    Notification ||--o{ NotificationDelivery : has

    Notification {
        uuid id PK
        uuid user_id FK
        string type
        string title
        text body
        string status
        string priority
        json data
        datetime created_at
        datetime read_at
    }

    NotificationDelivery {
        uuid id PK
        uuid notification_id FK
        string channel
        string status
        text error
        datetime sent_at
        datetime delivered_at
    }

    NotificationPreferences {
        uuid id PK
        uuid user_id FK
        boolean enabled
        time quiet_start
        time quiet_end
        string timezone
    }

    NotificationRule {
        uuid id PK
        uuid user_id FK
        string notification_type
        json channels
        string frequency
    }
```

## Quick Start

### 1. Add to INSTALLED_APPS

```python
INSTALLED_APPS = [
    ...
    'django_matt.notifications',
]
```

### 2. Run Migrations

```bash
python manage.py migrate
```

### 3. Register Controller

```python
from django_matt import MattAPI
from django_matt.notifications import NotificationController

api = MattAPI()
api.register_controller(NotificationController)
```

### 4. Send a Notification

```python
from django_matt.notifications import notify

await notify(
    user=user,
    notification_type="order_shipped",
    title="Your order has shipped!",
    body="Track your package...",
    data={"order_id": order.id, "tracking_url": "..."},
)
```

## Related Documentation

- [Channels](./channels.md)
- [Preferences](./preferences.md)
- [Delivery](./delivery.md)
