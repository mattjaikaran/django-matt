"""
Tests for the Django Matt notifications module.

Tests cover:
- Notification enums (NotificationType, NotificationChannel, NotificationPriority, NotificationStatus)
- Notification model (CRUD, mark_as_read, dismiss, properties)
- NotificationDelivery model (mark_sent, mark_delivered, mark_failed, schedule_retry)
- NotificationPreferences model (channel enablement, quiet hours, get_enabled_channels)
- NotificationRule model (is_muted, is_channel_enabled)
- NotificationManager (unread, read, for_user, by_type)
- NotificationService (create, bulk create, get, mark_read, dismiss, delete_old, collapse)
- DeliveryService (deliver_notification, register_handler, retry_failed)
- InAppDeliveryHandler, EmailDeliveryHandler, PushDeliveryHandler, SMSDeliveryHandler
- NotificationController (list, get, mark_read, dismiss, preferences, rules)
"""

from __future__ import annotations

from datetime import time, timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import RequestFactory, override_settings
from django.utils import timezone

import pytest

from django_matt.notifications.enums import (
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
    NotificationType,
)
from django_matt.notifications.models import (
    Notification,
    NotificationDelivery,
    NotificationPreferences,
    NotificationRule,
    PushToken,
)
from django_matt.notifications.services.delivery import (
    DeliveryService,
    EmailDeliveryHandler,
    InAppDeliveryHandler,
    PushDeliveryHandler,
    SMSDeliveryHandler,
    WebhookDeliveryHandler,
)
from django_matt.notifications.services.notification import NotificationService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
@pytest.mark.django_db
def user(db):
    return User.objects.create_user(
        username="notifuser",
        email="notif@example.com",
        password="testpass123",
    )


@pytest.fixture
@pytest.mark.django_db
def sender(db):
    return User.objects.create_user(
        username="sender",
        email="sender@example.com",
        password="testpass123",
    )


@pytest.fixture
@pytest.mark.django_db
def notification(user):
    return Notification.objects.create(
        recipient=user,
        title="Test Notification",
        message="This is a test notification.",
        notification_type=NotificationType.SYSTEM,
        priority=NotificationPriority.NORMAL,
    )


# ---------------------------------------------------------------------------
# Tests: Notification Enums
# ---------------------------------------------------------------------------


class TestNotificationEnums:
    """Test notification enum definitions."""

    def test_notification_type_values(self):
        assert NotificationType.SYSTEM == "system"
        assert NotificationType.MENTION == "mention"
        assert NotificationType.MESSAGE == "message"
        assert NotificationType.INVITATION == "invitation"
        assert NotificationType.CUSTOM == "custom"
        assert NotificationType.COMMENT == "comment"

    def test_notification_channel_values(self):
        assert NotificationChannel.IN_APP == "in_app"
        assert NotificationChannel.EMAIL == "email"
        assert NotificationChannel.PUSH == "push"
        assert NotificationChannel.SMS == "sms"
        assert NotificationChannel.WEBHOOK == "webhook"

    def test_notification_priority_values(self):
        assert NotificationPriority.LOW == "low"
        assert NotificationPriority.NORMAL == "normal"
        assert NotificationPriority.HIGH == "high"
        assert NotificationPriority.URGENT == "urgent"

    def test_notification_status_values(self):
        assert NotificationStatus.PENDING == "pending"
        assert NotificationStatus.SENT == "sent"
        assert NotificationStatus.DELIVERED == "delivered"
        assert NotificationStatus.READ == "read"
        assert NotificationStatus.FAILED == "failed"
        assert NotificationStatus.DISMISSED == "dismissed"


# ---------------------------------------------------------------------------
# Tests: Notification Model
# ---------------------------------------------------------------------------


class TestNotificationModel:
    """Test Notification model."""

    @pytest.mark.django_db
    def test_create_notification(self, notification):
        assert notification.title == "Test Notification"
        assert notification.notification_type == NotificationType.SYSTEM
        assert notification.is_read is False
        assert notification.is_dismissed is False

    @pytest.mark.django_db
    def test_mark_as_read(self, notification):
        assert notification.read_at is None
        notification.mark_as_read()
        notification.refresh_from_db()
        assert notification.is_read is True
        assert notification.read_at is not None

    @pytest.mark.django_db
    def test_mark_as_read_idempotent(self, notification):
        notification.mark_as_read()
        first_read_at = notification.read_at
        notification.mark_as_read()
        assert notification.read_at == first_read_at

    @pytest.mark.django_db
    def test_mark_as_unread(self, notification):
        notification.mark_as_read()
        assert notification.is_read is True
        notification.mark_as_unread()
        notification.refresh_from_db()
        assert notification.is_read is False

    @pytest.mark.django_db
    def test_dismiss(self, notification):
        notification.dismiss()
        notification.refresh_from_db()
        assert notification.is_dismissed is True
        assert notification.dismissed_at is not None

    @pytest.mark.django_db
    def test_is_expired_false(self, notification):
        assert notification.is_expired is False

    @pytest.mark.django_db
    def test_is_expired_true(self, user):
        n = Notification.objects.create(
            recipient=user,
            title="Expired",
            message="body",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        assert n.is_expired is True

    @pytest.mark.django_db
    def test_is_expired_not_set(self, notification):
        assert notification.expires_at is None
        assert notification.is_expired is False

    @pytest.mark.django_db
    def test_str_representation(self, notification):
        s = str(notification)
        assert "Test Notification" in s


# ---------------------------------------------------------------------------
# Tests: NotificationDelivery Model
# ---------------------------------------------------------------------------


class TestNotificationDeliveryModel:
    """Test NotificationDelivery model."""

    @pytest.mark.django_db
    def test_mark_sent(self, notification):
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.EMAIL,
        )
        delivery.mark_sent(external_id="ext-123")
        delivery.refresh_from_db()
        assert delivery.status == NotificationStatus.SENT
        assert delivery.sent_at is not None
        assert delivery.external_id == "ext-123"

    @pytest.mark.django_db
    def test_mark_delivered(self, notification):
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.IN_APP,
        )
        delivery.mark_delivered()
        delivery.refresh_from_db()
        assert delivery.status == NotificationStatus.DELIVERED
        assert delivery.delivered_at is not None

    @pytest.mark.django_db
    def test_mark_failed(self, notification):
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.PUSH,
        )
        delivery.mark_failed("Token expired")
        delivery.refresh_from_db()
        assert delivery.status == NotificationStatus.FAILED
        assert delivery.error_message == "Token expired"
        assert delivery.retry_count == 1

    @pytest.mark.django_db
    def test_schedule_retry(self, notification):
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.SMS,
        )
        delivery.schedule_retry(delay_seconds=600)
        delivery.refresh_from_db()
        assert delivery.status == NotificationStatus.PENDING
        assert delivery.next_retry_at is not None

    @pytest.mark.django_db
    def test_to_dict(self, notification):
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.EMAIL,
        )
        d = delivery.to_dict()
        assert d["channel"] == NotificationChannel.EMAIL
        assert d["status"] == NotificationStatus.PENDING


# ---------------------------------------------------------------------------
# Tests: NotificationPreferences Model
# ---------------------------------------------------------------------------


class TestNotificationPreferences:
    """Test NotificationPreferences model."""

    @pytest.mark.django_db
    def test_get_or_create_for_user(self, user):
        prefs = NotificationPreferences.get_or_create_for_user(user)
        assert prefs.user == user
        assert prefs.in_app_enabled is True
        assert prefs.email_enabled is True

    @pytest.mark.django_db
    def test_is_channel_enabled(self, user):
        prefs = NotificationPreferences.get_or_create_for_user(user)
        assert prefs.is_channel_enabled(NotificationChannel.IN_APP) is True
        assert prefs.is_channel_enabled(NotificationChannel.SMS) is False

    @pytest.mark.django_db
    def test_unsubscribed_disables_all(self, user):
        prefs = NotificationPreferences.get_or_create_for_user(user)
        prefs.unsubscribed = True
        prefs.save()
        assert prefs.is_channel_enabled(NotificationChannel.IN_APP) is False
        assert prefs.is_channel_enabled(NotificationChannel.EMAIL) is False

    @pytest.mark.django_db
    def test_get_enabled_channels(self, user):
        prefs = NotificationPreferences.get_or_create_for_user(user)
        channels = prefs.get_enabled_channels()
        assert NotificationChannel.IN_APP in channels
        assert NotificationChannel.EMAIL in channels
        assert NotificationChannel.PUSH in channels
        assert NotificationChannel.SMS not in channels

    @pytest.mark.django_db
    def test_get_enabled_channels_unsubscribed(self, user):
        prefs = NotificationPreferences.get_or_create_for_user(user)
        prefs.unsubscribed = True
        prefs.save()
        channels = prefs.get_enabled_channels()
        assert channels == []

    @pytest.mark.django_db
    def test_is_in_quiet_hours_disabled(self, user):
        prefs = NotificationPreferences.get_or_create_for_user(user)
        assert prefs.is_in_quiet_hours() is False

    @pytest.mark.django_db
    def test_email_frequency_never_disables_email_channel(self, user):
        prefs = NotificationPreferences.get_or_create_for_user(user)
        prefs.email_frequency = "never"
        prefs.save()
        channels = prefs.get_enabled_channels()
        assert NotificationChannel.EMAIL not in channels

    @pytest.mark.django_db
    def test_str_representation(self, user):
        prefs = NotificationPreferences.get_or_create_for_user(user)
        assert str(user) in str(prefs)


# ---------------------------------------------------------------------------
# Tests: NotificationRule Model
# ---------------------------------------------------------------------------


class TestNotificationRule:
    """Test NotificationRule model."""

    @pytest.mark.django_db
    def test_is_muted_false(self, user):
        prefs = NotificationPreferences.get_or_create_for_user(user)
        rule = NotificationRule.objects.create(
            preferences=prefs,
            notification_type=NotificationType.MENTION,
            muted=False,
        )
        assert rule.is_muted() is False

    @pytest.mark.django_db
    def test_is_muted_true(self, user):
        prefs = NotificationPreferences.get_or_create_for_user(user)
        rule = NotificationRule.objects.create(
            preferences=prefs,
            notification_type=NotificationType.MENTION,
            muted=True,
        )
        assert rule.is_muted() is True

    @pytest.mark.django_db
    def test_is_muted_expired(self, user):
        prefs = NotificationPreferences.get_or_create_for_user(user)
        rule = NotificationRule.objects.create(
            preferences=prefs,
            notification_type=NotificationType.MENTION,
            muted=True,
            muted_until=timezone.now() - timedelta(hours=1),
        )
        assert rule.is_muted() is False

    @pytest.mark.django_db
    def test_is_channel_enabled_with_override(self, user):
        prefs = NotificationPreferences.get_or_create_for_user(user)
        rule = NotificationRule.objects.create(
            preferences=prefs,
            notification_type=NotificationType.MESSAGE,
            email_enabled=False,
        )
        # Rule says email disabled even if global is enabled
        assert rule.is_channel_enabled(NotificationChannel.EMAIL, global_enabled=True) is False

    @pytest.mark.django_db
    def test_is_channel_enabled_falls_back_to_global(self, user):
        prefs = NotificationPreferences.get_or_create_for_user(user)
        rule = NotificationRule.objects.create(
            preferences=prefs,
            notification_type=NotificationType.COMMENT,
            # email_enabled is None (not set)
        )
        assert rule.is_channel_enabled(NotificationChannel.EMAIL, global_enabled=True) is True
        assert rule.is_channel_enabled(NotificationChannel.EMAIL, global_enabled=False) is False


# ---------------------------------------------------------------------------
# Tests: NotificationManager
# ---------------------------------------------------------------------------


class TestNotificationManager:
    """Test custom manager methods."""

    @pytest.mark.django_db
    def test_unread(self, user):
        Notification.objects.create(
            recipient=user, title="Unread", message="msg"
        )
        n2 = Notification.objects.create(
            recipient=user, title="Read", message="msg"
        )
        n2.mark_as_read()

        assert Notification.objects.unread().count() == 1

    @pytest.mark.django_db
    def test_read(self, user):
        n = Notification.objects.create(
            recipient=user, title="Test", message="msg"
        )
        n.mark_as_read()
        assert Notification.objects.read().count() == 1

    @pytest.mark.django_db
    def test_for_user(self, user, sender):
        Notification.objects.create(
            recipient=user, title="For User", message="msg"
        )
        Notification.objects.create(
            recipient=sender, title="For Sender", message="msg"
        )
        assert Notification.objects.for_user(user).count() == 1

    @pytest.mark.django_db
    def test_by_type(self, user):
        Notification.objects.create(
            recipient=user, title="System", message="msg",
            notification_type=NotificationType.SYSTEM,
        )
        Notification.objects.create(
            recipient=user, title="Mention", message="msg",
            notification_type=NotificationType.MENTION,
        )
        assert Notification.objects.by_type(NotificationType.SYSTEM).count() == 1


# ---------------------------------------------------------------------------
# Tests: NotificationService
# ---------------------------------------------------------------------------


class TestNotificationService:
    """Test NotificationService business logic."""

    @pytest.mark.django_db
    def test_create_notification(self, user):
        with patch.object(DeliveryService, "deliver_notification", return_value={}):
            notif = NotificationService.create_notification(
                recipient=user,
                title="Hello",
                message="World",
                notification_type=NotificationType.SYSTEM,
                channels=[NotificationChannel.IN_APP],
            )
        assert notif.title == "Hello"
        assert notif.recipient == user
        assert notif.deliveries.count() == 1

    @pytest.mark.django_db
    def test_create_notification_with_sender(self, user, sender):
        with patch.object(DeliveryService, "deliver_notification", return_value={}):
            notif = NotificationService.create_notification(
                recipient=user,
                sender=sender,
                title="From sender",
                message="Hi",
                channels=[NotificationChannel.IN_APP],
            )
        assert notif.sender == sender

    @pytest.mark.django_db
    def test_create_bulk_notifications(self, user, sender):
        with patch.object(DeliveryService, "deliver_notification", return_value={}):
            results = NotificationService.create_bulk_notifications(
                recipients=[user, sender],
                title="Bulk",
                message="Hello all",
                channels=[NotificationChannel.IN_APP],
            )
        assert len(results) == 2

    @pytest.mark.django_db
    def test_get_notifications(self, user):
        Notification.objects.create(
            recipient=user, title="N1", message="msg"
        )
        Notification.objects.create(
            recipient=user, title="N2", message="msg"
        )
        results = NotificationService.get_notifications(user)
        assert len(results) == 2

    @pytest.mark.django_db
    def test_get_notifications_unread_only(self, user):
        n1 = Notification.objects.create(
            recipient=user, title="Unread", message="msg"
        )
        n2 = Notification.objects.create(
            recipient=user, title="Read", message="msg"
        )
        n2.mark_as_read()
        results = NotificationService.get_notifications(user, unread_only=True)
        assert len(results) == 1
        assert results[0].title == "Unread"

    @pytest.mark.django_db
    def test_get_unread_count(self, user):
        Notification.objects.create(
            recipient=user, title="N1", message="msg"
        )
        Notification.objects.create(
            recipient=user, title="N2", message="msg"
        )
        n3 = Notification.objects.create(
            recipient=user, title="N3", message="msg"
        )
        n3.mark_as_read()
        assert NotificationService.get_unread_count(user) == 2

    @pytest.mark.django_db
    def test_mark_as_read(self, notification):
        NotificationService.mark_as_read(notification)
        notification.refresh_from_db()
        assert notification.is_read is True

    @pytest.mark.django_db
    def test_mark_all_as_read(self, user):
        Notification.objects.create(
            recipient=user, title="N1", message="msg"
        )
        Notification.objects.create(
            recipient=user, title="N2", message="msg"
        )
        count = NotificationService.mark_all_as_read(user)
        assert count == 2
        assert Notification.objects.filter(recipient=user, read_at__isnull=True).count() == 0

    @pytest.mark.django_db
    def test_dismiss_notification(self, notification):
        NotificationService.dismiss_notification(notification)
        notification.refresh_from_db()
        assert notification.is_dismissed is True

    @pytest.mark.django_db
    def test_dismiss_all(self, user):
        Notification.objects.create(
            recipient=user, title="N1", message="msg"
        )
        Notification.objects.create(
            recipient=user, title="N2", message="msg"
        )
        count = NotificationService.dismiss_all(user)
        assert count == 2

    @pytest.mark.django_db
    def test_delete_old_notifications(self, user):
        old_notif = Notification.objects.create(
            recipient=user, title="Old", message="msg"
        )
        # Manually set created_at to 100 days ago
        Notification.objects.filter(pk=old_notif.pk).update(
            created_at=timezone.now() - timedelta(days=100)
        )
        deleted = NotificationService.delete_old_notifications(days=90)
        assert deleted == 1

    @pytest.mark.django_db
    def test_get_unread_counts_by_type(self, user):
        Notification.objects.create(
            recipient=user, title="S1", message="msg",
            notification_type=NotificationType.SYSTEM,
        )
        Notification.objects.create(
            recipient=user, title="S2", message="msg",
            notification_type=NotificationType.SYSTEM,
        )
        Notification.objects.create(
            recipient=user, title="M1", message="msg",
            notification_type=NotificationType.MENTION,
        )
        counts = NotificationService.get_unread_counts_by_type(user)
        assert counts.get(NotificationType.SYSTEM) == 2
        assert counts.get(NotificationType.MENTION) == 1


# ---------------------------------------------------------------------------
# Tests: DeliveryService
# ---------------------------------------------------------------------------


class TestDeliveryService:
    """Test DeliveryService."""

    @pytest.mark.django_db
    def test_deliver_notification_in_app(self, notification):
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.IN_APP,
        )
        # Patch _broadcast_websocket to avoid channels dependency
        with patch.object(InAppDeliveryHandler, "_broadcast_websocket"):
            results = DeliveryService.deliver_notification(notification)
        assert results.get(NotificationChannel.IN_APP) is True

    @pytest.mark.django_db
    def test_deliver_notification_email(self, notification):
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.EMAIL,
        )
        mock_msg = MagicMock()
        mock_msg.id = 42
        with patch("django_matt.email.service.EmailService.send", return_value=mock_msg) as mock_send:
            results = DeliveryService.deliver_notification(notification)
        assert results.get(NotificationChannel.EMAIL) is True
        mock_send.assert_called_once()

    @pytest.mark.django_db
    def test_deliver_notification_push_no_tokens(self, notification):
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.PUSH,
        )
        with patch.object(PushDeliveryHandler, "_get_push_tokens", return_value=[]):
            results = DeliveryService.deliver_notification(notification)
        assert results.get(NotificationChannel.PUSH) is False

    @pytest.mark.django_db
    def test_deliver_notification_sms_no_phone(self, notification):
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.SMS,
        )
        results = DeliveryService.deliver_notification(notification)
        # User model has no phone field, so delivery should fail
        assert results.get(NotificationChannel.SMS) is False

    @pytest.mark.django_db
    def test_register_custom_handler(self, notification):
        mock_handler = MagicMock()
        mock_handler.deliver.return_value = True
        mock_handler.channel = NotificationChannel.WEBHOOK

        original = DeliveryService._handlers.get(NotificationChannel.WEBHOOK)
        try:
            DeliveryService.register_handler(NotificationChannel.WEBHOOK, mock_handler)

            delivery = NotificationDelivery.objects.create(
                notification=notification,
                channel=NotificationChannel.WEBHOOK,
            )
            results = DeliveryService.deliver_notification(notification)
            assert results.get(NotificationChannel.WEBHOOK) is True
            mock_handler.deliver.assert_called_once()
        finally:
            # Restore original handler
            if original:
                DeliveryService._handlers[NotificationChannel.WEBHOOK] = original


# ---------------------------------------------------------------------------
# Tests: Delivery Handlers
# ---------------------------------------------------------------------------


class TestInAppDeliveryHandler:
    """Test InAppDeliveryHandler."""

    @pytest.mark.django_db
    def test_deliver_success(self, notification):
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.IN_APP,
        )
        handler = InAppDeliveryHandler()
        with patch.object(handler, "_broadcast_websocket"):
            result = handler.deliver(delivery)
        assert result is True
        delivery.refresh_from_db()
        assert delivery.status == NotificationStatus.DELIVERED

    @pytest.mark.django_db
    def test_format_notification(self, notification):
        handler = InAppDeliveryHandler()
        formatted = handler.format_notification(notification)
        assert formatted["title"] == "Test Notification"
        assert formatted["message"] == "This is a test notification."


class TestEmailDeliveryHandler:
    """Test EmailDeliveryHandler."""

    @pytest.mark.django_db
    def test_deliver_success(self, notification):
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.EMAIL,
        )
        handler = EmailDeliveryHandler()
        mock_msg = MagicMock()
        mock_msg.id = 42
        with patch("django_matt.email.service.EmailService.send", return_value=mock_msg):
            result = handler.deliver(delivery)
        assert result is True
        delivery.refresh_from_db()
        assert delivery.status == NotificationStatus.SENT

    @pytest.mark.django_db
    def test_deliver_no_email(self, user, notification):
        user.email = ""
        user.save()
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.EMAIL,
        )
        handler = EmailDeliveryHandler()
        result = handler.deliver(delivery)
        assert result is False
        delivery.refresh_from_db()
        assert delivery.status == NotificationStatus.FAILED

    @pytest.mark.django_db
    def test_deliver_with_never_email_frequency(self, user, notification):
        prefs = NotificationPreferences.objects.create(
            user=user, email_frequency="never"
        )
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.EMAIL,
        )
        handler = EmailDeliveryHandler()
        result = handler.deliver(delivery)
        assert result is True  # dismissed but returns True
        delivery.refresh_from_db()
        assert delivery.status == NotificationStatus.DISMISSED


class TestSMSDeliveryHandler:
    """Test SMSDeliveryHandler."""

    @pytest.mark.django_db
    def test_format_sms_truncation(self, notification):
        handler = SMSDeliveryHandler()
        notification.title = "T" * 100
        notification.message = "M" * 100
        notification.action_url = ""
        msg = handler._format_sms(notification)
        assert len(msg) <= 160

    @pytest.mark.django_db
    def test_get_phone_number_none(self, notification):
        handler = SMSDeliveryHandler()
        phone = handler._get_phone_number(notification.recipient)
        assert phone is None


# ---------------------------------------------------------------------------
# Tests: NotificationController
# ---------------------------------------------------------------------------


class TestNotificationController:
    """Test NotificationController endpoints."""

    @pytest.mark.django_db
    def test_controller_imports(self):
        from django_matt.notifications.controllers import NotificationController
        assert NotificationController is not None

    @pytest.mark.django_db
    def test_controller_list(self, rf, user):
        from django_matt.notifications.controllers.notification import NotificationController

        Notification.objects.create(
            recipient=user, title="N1", message="msg",
        )
        request = rf.get("/notifications/", {"limit": "10"})
        request.user = user

        controller = NotificationController()
        result = controller.list(request)
        assert result.total == 1
        assert result.unread_count == 1

    @pytest.mark.django_db
    def test_controller_get(self, rf, user, notification):
        from django_matt.notifications.controllers.notification import NotificationController

        request = rf.get(f"/notifications/{notification.id}/")
        request.user = user

        controller = NotificationController()
        result = controller.get(request, notification.id)
        assert result.title == "Test Notification"

    @pytest.mark.django_db
    def test_controller_unread_count(self, rf, user):
        from django_matt.notifications.controllers.notification import NotificationController

        Notification.objects.create(
            recipient=user, title="N1", message="msg",
        )
        request = rf.get("/notifications/unread-count/")
        request.user = user

        controller = NotificationController()
        result = controller.unread_count(request)
        assert result.total == 1

    @pytest.mark.django_db
    def test_controller_get_preferences(self, rf, user):
        from django_matt.notifications.controllers.notification import NotificationController

        request = rf.get("/notifications/preferences/")
        request.user = user

        controller = NotificationController()
        result = controller.get_preferences(request)
        assert result.in_app_enabled is True
        assert result.email_enabled is True

    @pytest.mark.django_db
    def test_controller_get_not_found(self, rf, user):
        from django_matt.core.errors import NotFoundAPIError
        from django_matt.notifications.controllers.notification import NotificationController

        request = rf.get("/notifications/99999/")
        request.user = user

        controller = NotificationController()
        with pytest.raises(NotFoundAPIError):
            controller.get(request, 99999)


# ---------------------------------------------------------------------------
# Tests: Notification Mark Read (NOTIF-01)
# ---------------------------------------------------------------------------


class TestNotificationMarkRead:
    """Test notification create, retrieve, and mark_as_read with timestamp (NOTIF-01)."""

    @pytest.mark.django_db
    def test_create_and_mark_read(self, user):
        """Create Notification, verify read_at is None, mark_as_read, verify read_at is set."""
        notif = Notification.objects.create(
            recipient=user,
            title="NOTIF-01 Test",
            message="Verify mark_as_read sets read_at",
            notification_type=NotificationType.SYSTEM,
        )
        assert notif.read_at is None
        assert notif.is_read is False

        notif.mark_as_read()
        notif.refresh_from_db()

        assert notif.read_at is not None
        assert notif.is_read is True

    @pytest.mark.django_db
    def test_unread_manager_query(self, user):
        """Create 2 notifications (one read, one unread), verify for_user + unread filtering works."""
        n1 = Notification.objects.create(
            recipient=user, title="Unread One", message="msg"
        )
        n2 = Notification.objects.create(
            recipient=user, title="Read One", message="msg"
        )
        n2.mark_as_read()

        # Use manager's for_user and filter for unread
        unread = Notification.objects.for_user(user).filter(
            read_at__isnull=True, dismissed_at__isnull=True
        )
        assert unread.count() == 1
        assert unread.first().pk == n1.pk


# ---------------------------------------------------------------------------
# Tests: PushToken Model (NOTIF-03 prerequisite)
# ---------------------------------------------------------------------------


class TestPushTokenModel:
    """Test PushToken model CRUD and constraints."""

    @pytest.mark.django_db
    def test_create_push_token(self, user):
        """Create PushToken with user, token, platform='fcm', verify fields."""
        pt = PushToken.objects.create(
            user=user,
            token="fcm-token-abc123",
            platform="fcm",
            device_id="device-001",
        )
        assert pt.user == user
        assert pt.token == "fcm-token-abc123"
        assert pt.platform == "fcm"
        assert pt.device_id == "device-001"
        assert pt.active is True
        assert pt.created_at is not None
        assert str(pt) == f"PushToken(fcm) for {user}"

    @pytest.mark.django_db
    def test_push_token_unique_constraint(self, user):
        """Create duplicate (user, token), verify IntegrityError."""
        from django.db import IntegrityError

        PushToken.objects.create(
            user=user, token="dup-token", platform="fcm"
        )
        with pytest.raises(IntegrityError):
            PushToken.objects.create(
                user=user, token="dup-token", platform="apns"
            )


# ---------------------------------------------------------------------------
# Tests: PushDeliveryHandler (NOTIF-03)
# ---------------------------------------------------------------------------


class TestPushDeliveryHandler:
    """Test PushDeliveryHandler with real PushToken model (NOTIF-03)."""

    @pytest.mark.django_db
    def test_deliver_with_push_tokens(self, user, notification):
        """Create PushToken, deliver push notification, verify delivery marked sent."""
        PushToken.objects.create(
            user=user, token="test-fcm-token", platform="fcm"
        )
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.PUSH,
        )
        handler = PushDeliveryHandler()
        with patch.object(handler, "_send_push") as mock_send_push:
            result = handler.deliver(delivery)

        assert result is True
        mock_send_push.assert_called_once_with(notification, "test-fcm-token")
        delivery.refresh_from_db()
        assert delivery.status == NotificationStatus.SENT

    @pytest.mark.django_db
    def test_deliver_with_multiple_push_tokens(self, user, notification):
        """Multiple PushTokens triggers _send_push for each token."""
        PushToken.objects.create(user=user, token="token-1", platform="fcm")
        PushToken.objects.create(user=user, token="token-2", platform="apns")
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.PUSH,
        )
        handler = PushDeliveryHandler()
        with patch.object(handler, "_send_push") as mock_send_push:
            result = handler.deliver(delivery)

        assert result is True
        assert mock_send_push.call_count == 2

    @pytest.mark.django_db
    def test_deliver_no_push_tokens(self, user, notification):
        """No PushToken records means delivery fails with 'No push tokens registered'."""
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.PUSH,
        )
        handler = PushDeliveryHandler()
        result = handler.deliver(delivery)

        assert result is False
        delivery.refresh_from_db()
        assert delivery.status == NotificationStatus.FAILED
        assert "No push tokens registered" in delivery.error_message

    @pytest.mark.django_db
    def test_deliver_inactive_tokens_ignored(self, user, notification):
        """Inactive PushTokens are not returned by _get_push_tokens."""
        PushToken.objects.create(
            user=user, token="inactive-token", platform="fcm", active=False
        )
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.PUSH,
        )
        handler = PushDeliveryHandler()
        result = handler.deliver(delivery)

        assert result is False
        delivery.refresh_from_db()
        assert delivery.status == NotificationStatus.FAILED


# ---------------------------------------------------------------------------
# Tests: EmailDeliveryHandler via EmailService (NOTIF-02)
# ---------------------------------------------------------------------------


class TestEmailDeliveryViaEmailService:
    """Test EmailDeliveryHandler dispatches through EmailService (NOTIF-02)."""

    @pytest.mark.django_db
    def test_email_delivery_uses_email_service(self, user, notification):
        """EmailDeliveryHandler calls EmailService.send() with correct to/subject/text."""
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.EMAIL,
        )
        mock_msg = MagicMock()
        mock_msg.id = 99
        handler = EmailDeliveryHandler()

        with patch("django_matt.email.service.EmailService.send", return_value=mock_msg) as mock_send:
            result = handler.deliver(delivery)

        assert result is True
        mock_send.assert_called_once()

        call_kwargs = mock_send.call_args
        assert call_kwargs.kwargs["to"] == user.email
        assert call_kwargs.kwargs["subject"] == notification.title
        assert notification.title in call_kwargs.kwargs["text"]
        assert notification.message in call_kwargs.kwargs["text"]
        assert call_kwargs.kwargs["metadata"]["notification_id"] == notification.id

        delivery.refresh_from_db()
        assert delivery.status == NotificationStatus.SENT

    @pytest.mark.django_db
    def test_email_delivery_with_action_url(self, user):
        """Action URL is included in email text content."""
        notif = Notification.objects.create(
            recipient=user,
            title="Action Required",
            message="Please review",
            action_url="https://example.com/review",
            action_label="Review Now",
        )
        delivery = NotificationDelivery.objects.create(
            notification=notif,
            channel=NotificationChannel.EMAIL,
        )
        mock_msg = MagicMock()
        mock_msg.id = 100
        handler = EmailDeliveryHandler()

        with patch("django_matt.email.service.EmailService.send", return_value=mock_msg) as mock_send:
            handler.deliver(delivery)

        text = mock_send.call_args.kwargs["text"]
        assert "Review Now" in text
        assert "https://example.com/review" in text


# ---------------------------------------------------------------------------
# Tests: SMS Delivery Handler (NOTIF-04)
# ---------------------------------------------------------------------------


class TestSMSDeliveryHandlerChannel:
    """Test SMSDeliveryHandler formats message and calls _send_sms (NOTIF-04)."""

    @pytest.mark.django_db
    def test_sms_format_and_send(self, user, notification):
        """SMSDeliveryHandler formats message and calls _send_sms with phone and message."""
        # Give user a phone attribute
        user.phone = "+15551234567"
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.SMS,
        )
        handler = SMSDeliveryHandler()
        with patch.object(handler, "_send_sms") as mock_sms:
            result = handler.deliver(delivery)

        assert result is True
        mock_sms.assert_called_once()
        phone_arg, msg_arg = mock_sms.call_args[0]
        assert phone_arg == "+15551234567"
        assert notification.title in msg_arg

        delivery.refresh_from_db()
        assert delivery.status == NotificationStatus.SENT


# ---------------------------------------------------------------------------
# Tests: Webhook Delivery Handler (NOTIF-05)
# ---------------------------------------------------------------------------


class TestWebhookDeliveryHandlerChannel:
    """Test WebhookDeliveryHandler sends POST with HMAC-SHA256 signature (NOTIF-05)."""

    @pytest.mark.django_db
    def test_webhook_delivery_with_hmac_signature(self, user, notification):
        """Webhook delivers POST with X-Webhook-Signature and X-Webhook-Timestamp headers."""
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.WEBHOOK,
            metadata={"webhook_url": "https://hooks.example.com/notify"},
        )
        handler = WebhookDeliveryHandler()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = handler.deliver(delivery)

        assert result is True
        mock_post.assert_called_once()

        call_kwargs = mock_post.call_args
        # URL is the first positional argument to requests.post()
        assert call_kwargs.args[0] == "https://hooks.example.com/notify"
        headers = call_kwargs.kwargs["headers"]
        assert "X-Webhook-Signature" in headers
        assert "X-Webhook-Timestamp" in headers
        assert headers["Content-Type"] == "application/json"

        # Verify signature is a hex string (64 chars for SHA256)
        assert len(headers["X-Webhook-Signature"]) == 64

        delivery.refresh_from_db()
        assert delivery.status == NotificationStatus.SENT

    @pytest.mark.django_db
    def test_webhook_delivery_no_url(self, user, notification):
        """Webhook delivery fails when no webhook URL configured."""
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.WEBHOOK,
            metadata={},
        )
        handler = WebhookDeliveryHandler()
        result = handler.deliver(delivery)

        assert result is False
        delivery.refresh_from_db()
        assert delivery.status == NotificationStatus.FAILED
        assert "No webhook URL" in delivery.error_message


# ---------------------------------------------------------------------------
# Tests: DeliveryService Integration
# ---------------------------------------------------------------------------


class TestDeliveryServiceIntegration:
    """Test DeliveryService.deliver_notification dispatches to all pending channels."""

    @pytest.mark.django_db
    def test_deliver_notification_dispatches_all_channels(self, user, notification):
        """Create Notification with 2 deliveries (in_app + email), verify both dispatched."""
        NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.IN_APP,
        )
        NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.EMAIL,
        )

        mock_msg = MagicMock()
        mock_msg.id = 200

        with (
            patch.object(InAppDeliveryHandler, "_broadcast_websocket"),
            patch("django_matt.email.service.EmailService.send", return_value=mock_msg),
        ):
            results = DeliveryService.deliver_notification(notification)

        assert results.get(NotificationChannel.IN_APP) is True
        assert results.get(NotificationChannel.EMAIL) is True

        # Verify delivery statuses in DB
        in_app_delivery = NotificationDelivery.objects.get(
            notification=notification, channel=NotificationChannel.IN_APP
        )
        email_delivery = NotificationDelivery.objects.get(
            notification=notification, channel=NotificationChannel.EMAIL
        )
        assert in_app_delivery.status == NotificationStatus.DELIVERED
        assert email_delivery.status == NotificationStatus.SENT

    @pytest.mark.django_db
    def test_deliver_notification_partial_failure(self, user, notification):
        """If one channel fails, others still succeed."""
        NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.IN_APP,
        )
        NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationChannel.PUSH,
        )
        # No PushToken exists, so push will fail

        with patch.object(InAppDeliveryHandler, "_broadcast_websocket"):
            results = DeliveryService.deliver_notification(notification)

        assert results.get(NotificationChannel.IN_APP) is True
        assert results.get(NotificationChannel.PUSH) is False
