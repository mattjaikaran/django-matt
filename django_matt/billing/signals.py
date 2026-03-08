"""
Django signals for billing subscription lifecycle events.

Connect to these signals to add custom post-sync logic without
subclassing WebhookController.

Example::

    from django_matt.billing.signals import subscription_synced

    @receiver(subscription_synced)
    def on_subscription_synced(sender, subscription, provider, event_type, **kwargs):
        # Grant/revoke feature access, send emails, etc.
        ...
"""

from django.dispatch import Signal

# Fires after any subscription create/update/cancel has been synced to the DB.
# Kwargs: subscription (Subscription instance), provider (str), event_type (str),
#         raw_data (dict)
subscription_synced = Signal()

# Fires specifically when a subscription transitions to "canceled" status.
# Kwargs: subscription (Subscription instance), provider (str), raw_data (dict)
subscription_canceled = Signal()

# Fires after an invoice.paid webhook has been synced to the DB.
# Kwargs: invoice (Invoice instance | None), provider (str), raw_data (dict)
invoice_paid = Signal()

# Fires immediately after a webhook has been received and signature-verified,
# before any DB sync occurs.
# Kwargs: event_id (str), event_type (str), provider (str), raw_data (dict)
webhook_received = Signal()

__all__ = [
    "subscription_synced",
    "subscription_canceled",
    "invoice_paid",
    "webhook_received",
]
