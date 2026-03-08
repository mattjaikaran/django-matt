"""
Notification delivery service.

Handles delivery to different channels (in-app, email, push, SMS).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import orjson

from django_matt.notifications.enums import NotificationChannel, NotificationStatus
from django_matt.notifications.models import Notification, NotificationDelivery

logger = logging.getLogger(__name__)


def _get_webhook_secret() -> str:
    """
    Get the webhook signing secret from Django settings.

    Looks for DJANGO_MATT_NOTIFICATIONS['WEBHOOK_SECRET'] first,
    then falls back to Django SECRET_KEY.
    """
    from django.conf import settings

    notifications_config = getattr(settings, "DJANGO_MATT_NOTIFICATIONS", {})
    secret = notifications_config.get("WEBHOOK_SECRET")
    if secret:
        return secret
    return settings.SECRET_KEY


class DeliveryHandler(ABC):
    """Abstract base class for delivery handlers."""

    channel: NotificationChannel

    @abstractmethod
    def deliver(self, delivery: NotificationDelivery) -> bool:
        """
        Deliver a notification.

        Returns True if successful, False otherwise.
        """

    def format_notification(self, notification: Notification) -> dict[str, Any]:
        """Format notification for this channel."""
        return {
            "title": notification.title,
            "message": notification.message,
            "action_url": notification.action_url,
            "action_label": notification.action_label,
            "priority": notification.priority,
            "metadata": notification.metadata,
        }


class InAppDeliveryHandler(DeliveryHandler):
    """Handler for in-app notifications."""

    channel = NotificationChannel.IN_APP

    def deliver(self, delivery: NotificationDelivery) -> bool:
        """
        In-app notifications are stored in the database.

        Delivery means the notification is created and available.
        We can also broadcast via WebSocket if configured.
        """
        try:
            # Mark as delivered (in-app is immediate)
            delivery.mark_delivered()

            # Optionally broadcast via WebSocket
            self._broadcast_websocket(delivery.notification)

            return True

        except Exception as e:
            logger.exception(f"In-app delivery failed: {e}")
            delivery.mark_failed(str(e))
            return False

    def _broadcast_websocket(self, notification: Notification) -> None:
        """Broadcast notification via WebSocket if available."""
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer

            channel_layer = get_channel_layer()
            if not channel_layer:
                return

            # Send to user's personal channel
            async_to_sync(channel_layer.group_send)(
                f"user_{notification.recipient.id}",
                {
                    "type": "notification",
                    "data": {
                        "id": notification.id,
                        "type": notification.notification_type,
                        "title": notification.title,
                        "message": notification.message,
                        "action_url": notification.action_url,
                        "created_at": notification.created_at.isoformat(),
                        "sender_id": notification.sender_id if notification.sender else None,
                    },
                },
            )

        except ImportError:
            # Channels not installed
            pass
        except Exception as e:
            logger.warning(f"WebSocket broadcast failed: {e}")


class EmailDeliveryHandler(DeliveryHandler):
    """Handler for email notifications."""

    channel = NotificationChannel.EMAIL

    def deliver(self, delivery: NotificationDelivery) -> bool:
        """Deliver notification via email."""
        notification = delivery.notification
        recipient = notification.recipient

        try:
            # Check if user has email
            if not recipient.email:
                delivery.mark_failed("User has no email address")
                return False

            # Check email preferences
            from django_matt.notifications.models import NotificationPreferences

            try:
                prefs = NotificationPreferences.objects.get(user=recipient)
                if prefs.email_frequency == "never":
                    delivery.status = NotificationStatus.DISMISSED
                    delivery.save(update_fields=["status"])
                    return True
                if prefs.email_frequency in ("daily", "weekly"):
                    # Queue for digest
                    delivery.metadata["queued_for_digest"] = True
                    delivery.save(update_fields=["metadata"])
                    return True
            except NotificationPreferences.DoesNotExist:
                pass

            # Send email
            self._send_email(notification, recipient.email)

            delivery.mark_sent()
            return True

        except Exception as e:
            logger.exception(f"Email delivery failed: {e}")
            delivery.mark_failed(str(e))
            return False

    def _send_email(self, notification: Notification, email: str) -> str:
        """Send the actual email via EmailService for tracking and suppression."""
        try:
            from django_matt.email.service import EmailService

            text_content = f"{notification.title}\n\n{notification.message}"
            if notification.action_url:
                text_content += (
                    f"\n\n{notification.action_label or 'View'}: {notification.action_url}"
                )

            email_msg = EmailService.send(
                to=email,
                subject=notification.title,
                text=text_content,
                metadata={"notification_id": notification.id},
            )
            return str(email_msg.id) if email_msg else ""
        except ImportError:
            # Fallback to django.core.mail if email module not available
            from django.conf import settings as django_settings
            from django.core.mail import send_mail

            text_content = f"{notification.title}\n\n{notification.message}"
            if notification.action_url:
                text_content += (
                    f"\n\n{notification.action_label or 'View'}: {notification.action_url}"
                )

            from_email = getattr(
                django_settings,
                "NOTIFICATION_FROM_EMAIL",
                django_settings.DEFAULT_FROM_EMAIL,
            )

            send_mail(
                subject=notification.title,
                message=text_content,
                from_email=from_email,
                recipient_list=[email],
                fail_silently=False,
            )
            return ""


class PushDeliveryHandler(DeliveryHandler):
    """Handler for push notifications."""

    channel = NotificationChannel.PUSH

    def deliver(self, delivery: NotificationDelivery) -> bool:
        """Deliver notification via push."""
        notification = delivery.notification
        recipient = notification.recipient

        try:
            # Get user's push tokens
            push_tokens = self._get_push_tokens(recipient)

            if not push_tokens:
                delivery.mark_failed("No push tokens registered")
                return False

            # Send to each token
            for token in push_tokens:
                self._send_push(notification, token)

            delivery.mark_sent()
            return True

        except Exception as e:
            logger.exception(f"Push delivery failed: {e}")
            delivery.mark_failed(str(e))
            return False

    def _get_push_tokens(self, user) -> list[str]:
        """Get push notification tokens for a user."""
        # This should be implemented based on your push token storage
        # For example, from a PushToken model
        try:
            from django.apps import apps

            PushToken = apps.get_model("django_matt", "PushToken")
            return list(
                PushToken.objects.filter(user=user, active=True).values_list("token", flat=True)
            )
        except Exception:
            return []

    def _send_push(self, notification: Notification, token: str) -> None:
        """
        Send push notification to a specific token.

        Override this method or register a custom PushDeliveryHandler
        with your FCM/APNs integration:

            from firebase_admin import messaging
            message = messaging.Message(
                notification=messaging.Notification(
                    title=notification.title,
                    body=notification.message,
                ),
                token=token,
            )
            messaging.send(message)
        """
        logger.warning(
            "Push delivery not configured — _send_push() is a no-op. "
            "Subclass PushDeliveryHandler or register a custom handler."
        )


class SMSDeliveryHandler(DeliveryHandler):
    """Handler for SMS notifications."""

    channel = NotificationChannel.SMS

    def deliver(self, delivery: NotificationDelivery) -> bool:
        """Deliver notification via SMS."""
        notification = delivery.notification
        recipient = notification.recipient

        try:
            # Get user's phone number
            phone = self._get_phone_number(recipient)

            if not phone:
                delivery.mark_failed("No phone number registered")
                return False

            # Format and send SMS
            message = self._format_sms(notification)
            self._send_sms(phone, message)

            delivery.mark_sent()
            return True

        except Exception as e:
            logger.exception(f"SMS delivery failed: {e}")
            delivery.mark_failed(str(e))
            return False

    def _get_phone_number(self, user) -> str | None:
        """Get phone number for a user."""
        # Check common phone field names
        for field in ["phone", "phone_number", "mobile"]:
            if hasattr(user, field):
                return getattr(user, field)
        return None

    def _format_sms(self, notification: Notification) -> str:
        """Format notification for SMS (limited to 160 chars typically)."""
        message = f"{notification.title}: {notification.message}"
        if len(message) > 155 and notification.action_url:
            message = message[:150] + "..."
        elif notification.action_url:
            message += f" {notification.action_url}"
        return message[:160]

    def _send_sms(self, phone: str, message: str) -> None:
        """
        Send SMS to a phone number.

        Override this method or register a custom SMSDeliveryHandler
        with your Twilio/SNS integration:

            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone,
            )
        """
        logger.warning(
            "SMS delivery not configured — _send_sms() is a no-op. "
            "Subclass SMSDeliveryHandler or register a custom handler."
        )


class WebhookDeliveryHandler(DeliveryHandler):
    """Handler for webhook notifications."""

    channel = NotificationChannel.WEBHOOK

    def deliver(self, delivery: NotificationDelivery) -> bool:
        """Deliver notification via webhook."""
        notification = delivery.notification

        try:
            # Get webhook URL from metadata or user settings
            webhook_url = delivery.metadata.get("webhook_url")

            if not webhook_url:
                # Try to get from user profile or organization
                webhook_url = self._get_webhook_url(notification.recipient)

            if not webhook_url:
                delivery.mark_failed("No webhook URL configured")
                return False

            # Send webhook
            self._send_webhook(notification, webhook_url)

            delivery.mark_sent()
            return True

        except Exception as e:
            logger.exception(f"Webhook delivery failed: {e}")
            delivery.mark_failed(str(e))
            return False

    def _get_webhook_url(self, user) -> str | None:
        """Get webhook URL for a user."""
        # Check user profile for webhook URL
        if hasattr(user, "webhook_url"):
            return user.webhook_url
        return None

    def _send_webhook(self, notification: Notification, url: str) -> None:
        """Send webhook POST request with HMAC-SHA256 signature."""
        import requests

        payload = {
            "id": notification.id,
            "type": notification.notification_type,
            "title": notification.title,
            "message": notification.message,
            "recipient_id": notification.recipient_id,
            "sender_id": notification.sender_id if notification.sender else None,
            "action_url": notification.action_url,
            "metadata": notification.metadata,
            "created_at": notification.created_at.isoformat(),
        }

        # Serialize payload to JSON for signing
        payload_json = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS).decode()

        # Generate HMAC-SHA256 signature: sign "timestamp.payload"
        timestamp = str(int(time.time()))
        signature_input = f"{timestamp}.{payload_json}"
        secret = _get_webhook_secret()
        signature = hmac.new(
            secret.encode("utf-8"),
            signature_input.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        response = requests.post(
            url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": timestamp,
            },
            timeout=10,
        )
        response.raise_for_status()


class DeliveryService:
    """Main service for notification delivery."""

    # Registry of channel handlers
    _handlers: dict[NotificationChannel, DeliveryHandler] = {
        NotificationChannel.IN_APP: InAppDeliveryHandler(),
        NotificationChannel.EMAIL: EmailDeliveryHandler(),
        NotificationChannel.PUSH: PushDeliveryHandler(),
        NotificationChannel.SMS: SMSDeliveryHandler(),
        NotificationChannel.WEBHOOK: WebhookDeliveryHandler(),
    }

    @classmethod
    def register_handler(
        cls,
        channel: NotificationChannel,
        handler: DeliveryHandler,
    ) -> None:
        """Register a custom delivery handler."""
        cls._handlers[channel] = handler

    @classmethod
    def deliver_notification(cls, notification: Notification) -> dict[str, bool]:
        """
        Deliver notification to all configured channels.

        Returns dict of channel -> success status.
        """
        results = {}

        for delivery in notification.deliveries.filter(status=NotificationStatus.PENDING):
            handler = cls._handlers.get(delivery.channel)

            if handler:
                try:
                    success = handler.deliver(delivery)
                    results[delivery.channel] = success
                except Exception as e:
                    logger.exception(f"Delivery error for {delivery.channel}: {e}")
                    delivery.mark_failed(str(e))
                    results[delivery.channel] = False
            else:
                logger.warning(f"No handler for channel: {delivery.channel}")
                delivery.mark_failed(f"No handler for channel: {delivery.channel}")
                results[delivery.channel] = False

        return results

    @classmethod
    def retry_failed_deliveries(cls, max_retries: int = 3) -> int:
        """
        Retry failed deliveries that are scheduled for retry.

        Returns count of retried deliveries.
        """
        from django.utils import timezone

        now = timezone.now()
        retried = 0

        pending_retries = NotificationDelivery.objects.filter(
            status=NotificationStatus.PENDING,
            next_retry_at__lte=now,
            retry_count__lt=max_retries,
        ).select_related("notification")

        for delivery in pending_retries:
            handler = cls._handlers.get(delivery.channel)
            if handler:
                try:
                    handler.deliver(delivery)
                    retried += 1
                except Exception as e:
                    logger.exception(f"Retry failed for delivery {delivery.id}: {e}")

        return retried
