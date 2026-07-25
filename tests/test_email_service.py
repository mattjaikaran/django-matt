"""
Tests for the Django Matt email module.

Tests cover:
- ConsoleProvider (no mock needed, just verify it doesn't crash)
- SendGridProvider (mock HTTP calls)
- SESProvider (mock boto3)
- MailgunProvider (mock HTTP calls)
- EmailService (provider selection, send, batch send)
- Email template rendering
- EmailResult dataclass
- Email enums
- get_provider factory
- SuppressedEmail model
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import RequestFactory, override_settings
from django.utils import timezone

import pytest

from django_matt.email.enums import BounceType, EmailProvider, EmailStatus, EmailType
from django_matt.email.models import (
    EmailEvent,
    EmailMessage,
    EmailTemplate,
    SuppressedEmail,
)
from django_matt.email.providers.base import EmailProviderBase, EmailResult
from django_matt.email.providers.console import ConsoleProvider
from django_matt.email.providers.mailgun import MailgunProvider
from django_matt.email.providers.sendgrid import SendGridProvider
from django_matt.email.providers.ses import SESProvider
from django_matt.email.providers.smtp import SMTPProvider
from django_matt.email.service import EmailService, send_email, send_template_email

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
        username="emailtester",
        email="tester@example.com",
        password="testpass123",
    )


# ---------------------------------------------------------------------------
# Tests: Email Enums
# ---------------------------------------------------------------------------


class TestEmailEnums:
    """Test email enum definitions."""

    def test_email_provider_choices(self):
        assert EmailProvider.SMTP == "smtp"
        assert EmailProvider.SES == "ses"
        assert EmailProvider.SENDGRID == "sendgrid"
        assert EmailProvider.MAILGUN == "mailgun"
        assert EmailProvider.CONSOLE == "console"
        assert EmailProvider.RESEND == "resend"

    def test_email_status_choices(self):
        assert EmailStatus.PENDING == "pending"
        assert EmailStatus.QUEUED == "queued"
        assert EmailStatus.SENT == "sent"
        assert EmailStatus.DELIVERED == "delivered"
        assert EmailStatus.OPENED == "opened"
        assert EmailStatus.CLICKED == "clicked"
        assert EmailStatus.BOUNCED == "bounced"
        assert EmailStatus.FAILED == "failed"

    def test_email_type_choices(self):
        assert EmailType.TRANSACTIONAL == "transactional"
        assert EmailType.MARKETING == "marketing"
        assert EmailType.NOTIFICATION == "notification"

    def test_bounce_type_choices(self):
        assert BounceType.HARD == "hard"
        assert BounceType.SOFT == "soft"
        assert BounceType.UNDETERMINED == "undetermined"


# ---------------------------------------------------------------------------
# Tests: EmailResult dataclass
# ---------------------------------------------------------------------------


class TestEmailResult:
    """Test EmailResult dataclass."""

    def test_success_result(self):
        result = EmailResult(success=True, message_id="msg-123", provider="sendgrid")
        assert result.success is True
        assert result.message_id == "msg-123"
        assert result.provider == "sendgrid"
        assert result.error == ""
        assert result.raw_response == {}

    def test_failure_result(self):
        result = EmailResult(success=False, provider="ses", error="Rate limit exceeded")
        assert result.success is False
        assert result.error == "Rate limit exceeded"

    def test_result_with_raw_response(self):
        raw = {"status_code": 202, "headers": {"X-Id": "abc"}}
        result = EmailResult(success=True, provider="sendgrid", raw_response=raw)
        assert result.raw_response["status_code"] == 202


# ---------------------------------------------------------------------------
# Tests: ConsoleProvider
# ---------------------------------------------------------------------------


class TestConsoleProvider:
    """Test ConsoleProvider sends to stdout without crashing."""

    def test_send_basic(self, capsys):
        provider = ConsoleProvider()
        result = provider.send(
            to=["user@example.com"],
            subject="Hello",
            text="Test body",
        )
        assert result.success is True
        assert result.provider == "console"
        assert result.message_id  # non-empty UUID
        captured = capsys.readouterr()
        assert "user@example.com" in captured.out
        assert "Hello" in captured.out

    def test_send_with_html(self, capsys):
        provider = ConsoleProvider()
        result = provider.send(
            to=["user@example.com"],
            subject="HTML Email",
            html="<h1>Hello</h1>",
        )
        assert result.success is True
        captured = capsys.readouterr()
        assert "<h1>Hello</h1>" in captured.out

    def test_send_with_cc_bcc(self, capsys):
        provider = ConsoleProvider()
        result = provider.send(
            to=["a@example.com"],
            subject="CC Test",
            text="body",
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
        )
        assert result.success is True
        captured = capsys.readouterr()
        assert "cc@example.com" in captured.out
        assert "bcc@example.com" in captured.out

    def test_send_with_attachments(self, capsys):
        provider = ConsoleProvider()
        result = provider.send(
            to=["a@example.com"],
            subject="Attachment Test",
            text="body",
            attachments=[
                {"filename": "test.pdf", "content_type": "application/pdf", "content": b"data"},
            ],
        )
        assert result.success is True
        captured = capsys.readouterr()
        assert "test.pdf" in captured.out

    def test_send_with_tags_metadata(self, capsys):
        provider = ConsoleProvider()
        result = provider.send(
            to=["a@example.com"],
            subject="Tags Test",
            text="body",
            tags=["welcome", "onboarding"],
            metadata={"campaign_id": "abc123"},
        )
        assert result.success is True
        captured = capsys.readouterr()
        assert "welcome" in captured.out
        assert "abc123" in captured.out

    def test_name_attribute(self):
        provider = ConsoleProvider()
        assert provider.name == "console"

    def test_get_default_from_email(self):
        provider = ConsoleProvider()
        from_email = provider.get_default_from_email()
        assert isinstance(from_email, str)
        assert "@" in from_email

    def test_validate_email_valid(self):
        provider = ConsoleProvider()
        assert provider.validate_email("test@example.com") is True

    def test_validate_email_invalid(self):
        provider = ConsoleProvider()
        assert provider.validate_email("notanemail") is False
        assert provider.validate_email("@example.com") is False


# ---------------------------------------------------------------------------
# Tests: SendGridProvider
# ---------------------------------------------------------------------------


class TestSendGridProvider:
    """Test SendGridProvider with mocked sendgrid client."""

    def _make_sendgrid_mocks(self):
        """Create mock sendgrid module objects."""
        mock_sg = MagicMock()
        # The send() method imports from sendgrid.helpers.mail inline,
        # so we need to patch sys.modules before the provider calls send().
        return mock_sg

    @override_settings(SENDGRID_API_KEY="sg-test-key-123")
    def test_send_success(self):
        import sys

        mock_sg_module = MagicMock()
        mock_helpers = MagicMock()
        mock_mail = MagicMock()

        with patch.dict(
            sys.modules,
            {
                "sendgrid": mock_sg_module,
                "sendgrid.helpers": mock_helpers,
                "sendgrid.helpers.mail": mock_mail,
            },
        ):
            provider = SendGridProvider()
            mock_response = MagicMock()
            mock_response.status_code = 202
            mock_response.body = ""
            mock_response.headers = {"X-Message-Id": "sg-msg-123"}

            mock_client = MagicMock()
            mock_client.send.return_value = mock_response
            provider._client = mock_client

            with patch.object(provider, "filter_suppressed", return_value=["user@example.com"]):
                result = provider.send(
                    to=["user@example.com"],
                    subject="Test",
                    text="Hello",
                )
        assert result.success is True
        assert result.provider == "sendgrid"

    @override_settings(SENDGRID_API_KEY="sg-test-key-123")
    def test_send_failure_status(self):
        import sys

        with patch.dict(
            sys.modules,
            {
                "sendgrid": MagicMock(),
                "sendgrid.helpers": MagicMock(),
                "sendgrid.helpers.mail": MagicMock(),
            },
        ):
            provider = SendGridProvider()
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.body = "Bad Request"
            mock_response.headers = {}

            mock_client = MagicMock()
            mock_client.send.return_value = mock_response
            provider._client = mock_client

            with patch.object(provider, "filter_suppressed", return_value=["user@example.com"]):
                result = provider.send(
                    to=["user@example.com"],
                    subject="Test",
                    text="Hello",
                )
        assert result.success is False
        assert "400" in result.error

    @override_settings(SENDGRID_API_KEY="sg-test-key-123")
    def test_send_all_suppressed(self):
        import sys

        with patch.dict(
            sys.modules,
            {
                "sendgrid": MagicMock(),
                "sendgrid.helpers": MagicMock(),
                "sendgrid.helpers.mail": MagicMock(),
            },
        ):
            provider = SendGridProvider()
            with patch.object(provider, "filter_suppressed", return_value=[]):
                result = provider.send(
                    to=["suppressed@example.com"],
                    subject="Test",
                    text="Hello",
                )
        assert result.success is False
        assert "suppressed" in result.error.lower()

    @override_settings(SENDGRID_API_KEY="sg-test-key-123")
    def test_send_exception_handling(self):
        import sys

        with patch.dict(
            sys.modules,
            {
                "sendgrid": MagicMock(),
                "sendgrid.helpers": MagicMock(),
                "sendgrid.helpers.mail": MagicMock(),
            },
        ):
            provider = SendGridProvider()
            with patch.object(
                provider, "filter_suppressed", side_effect=Exception("Network error")
            ):
                result = provider.send(
                    to=["user@example.com"],
                    subject="Test",
                    text="Hello",
                )
        assert result.success is False
        assert "Network error" in result.error

    def test_name_attribute(self):
        provider = SendGridProvider()
        assert provider.name == "sendgrid"


# ---------------------------------------------------------------------------
# Tests: SESProvider
# ---------------------------------------------------------------------------


class TestSESProvider:
    """Test SESProvider with mocked boto3 client."""

    @override_settings(AWS_SES_REGION_NAME="us-west-2")
    def test_send_success(self):
        provider = SESProvider()
        mock_client = MagicMock()
        mock_client.send_email.return_value = {"MessageId": "ses-msg-456"}

        provider._client = mock_client
        with patch.object(provider, "filter_suppressed", return_value=["user@example.com"]):
            result = provider.send(
                to=["user@example.com"],
                subject="Test",
                text="Hello world",
                from_email="sender@example.com",
            )
        assert result.success is True
        assert result.message_id == "ses-msg-456"
        assert result.provider == "ses"
        mock_client.send_email.assert_called_once()

    @override_settings(AWS_SES_REGION_NAME="us-east-1")
    def test_send_with_cc_bcc_reply_to(self):
        provider = SESProvider()
        mock_client = MagicMock()
        mock_client.send_email.return_value = {"MessageId": "ses-msg-789"}

        provider._client = mock_client
        with patch.object(provider, "filter_suppressed", return_value=["user@example.com"]):
            result = provider.send(
                to=["user@example.com"],
                subject="Test",
                html="<p>Hello</p>",
                from_email="sender@example.com",
                cc=["cc@example.com"],
                bcc=["bcc@example.com"],
                reply_to="reply@example.com",
            )
        assert result.success is True
        call_kwargs = mock_client.send_email.call_args[1]
        assert call_kwargs["Destination"]["CcAddresses"] == ["cc@example.com"]
        assert call_kwargs["Destination"]["BccAddresses"] == ["bcc@example.com"]
        assert call_kwargs["ReplyToAddresses"] == ["reply@example.com"]

    @override_settings(AWS_SES_REGION_NAME="us-east-1")
    def test_send_with_tags(self):
        provider = SESProvider()
        mock_client = MagicMock()
        mock_client.send_email.return_value = {"MessageId": "ses-tagged"}

        provider._client = mock_client
        with patch.object(provider, "filter_suppressed", return_value=["user@example.com"]):
            result = provider.send(
                to=["user@example.com"],
                subject="Test",
                text="Hello",
                from_email="sender@example.com",
                tags=["welcome"],
                metadata={"tracking_id": "track-123"},
            )
        assert result.success is True
        call_kwargs = mock_client.send_email.call_args[1]
        assert "Tags" in call_kwargs

    @override_settings(AWS_SES_REGION_NAME="us-east-1")
    def test_send_all_suppressed(self):
        provider = SESProvider()
        with patch.object(provider, "filter_suppressed", return_value=[]):
            result = provider.send(
                to=["suppressed@example.com"],
                subject="Test",
                text="Hello",
            )
        assert result.success is False
        assert "suppressed" in result.error.lower()

    @override_settings(AWS_SES_REGION_NAME="us-east-1")
    def test_send_exception(self):
        provider = SESProvider()
        mock_client = MagicMock()
        mock_client.send_email.side_effect = Exception("SES quota exceeded")

        provider._client = mock_client
        with patch.object(provider, "filter_suppressed", return_value=["user@example.com"]):
            result = provider.send(
                to=["user@example.com"],
                subject="Test",
                text="Hello",
                from_email="sender@example.com",
            )
        assert result.success is False
        assert "quota" in result.error.lower()

    def test_name_attribute(self):
        provider = SESProvider()
        assert provider.name == "ses"

    @override_settings(AWS_SES_REGION_NAME="eu-west-1")
    def test_region_from_settings(self):
        provider = SESProvider()
        assert provider.region == "eu-west-1"


# ---------------------------------------------------------------------------
# Tests: MailgunProvider
# ---------------------------------------------------------------------------


class TestMailgunProvider:
    """Test MailgunProvider with mocked requests."""

    @override_settings(
        MAILGUN_API_KEY="mg-test-key",
        MAILGUN_DOMAIN="mail.example.com",
    )
    def test_send_success(self):
        provider = MailgunProvider()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "<msg-id@mail.example.com>",
            "message": "Queued",
        }

        with (
            patch.object(provider, "filter_suppressed", return_value=["user@example.com"]),
            patch(
                "requests.post",
                return_value=mock_response,
            ) as mock_post,
        ):
            result = provider.send(
                to=["user@example.com"],
                subject="Hello",
                text="Test body",
            )
        assert result.success is True
        assert result.provider == "mailgun"
        mock_post.assert_called_once()

    @override_settings(
        MAILGUN_API_KEY="mg-test-key",
        MAILGUN_DOMAIN="mail.example.com",
    )
    def test_send_with_html_and_tags(self):
        provider = MailgunProvider()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "<msg-id>", "message": "Queued"}

        with (
            patch.object(provider, "filter_suppressed", return_value=["user@example.com"]),
            patch(
                "requests.post",
                return_value=mock_response,
            ) as mock_post,
        ):
            result = provider.send(
                to=["user@example.com"],
                subject="HTML",
                html="<h1>Hi</h1>",
                tags=["tag1", "tag2"],
                metadata={"key": "val"},
            )
        assert result.success is True
        call_kwargs = mock_post.call_args
        data = call_kwargs.kwargs.get("data") or call_kwargs[1].get("data")
        assert data["html"] == "<h1>Hi</h1>"

    @override_settings(
        MAILGUN_API_KEY="mg-test-key",
        MAILGUN_DOMAIN="mail.example.com",
    )
    def test_send_failure(self):
        provider = MailgunProvider()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"message": "Forbidden"}

        with (
            patch.object(provider, "filter_suppressed", return_value=["user@example.com"]),
            patch(
                "requests.post",
                return_value=mock_response,
            ),
        ):
            result = provider.send(
                to=["user@example.com"],
                subject="Test",
                text="body",
            )
        assert result.success is False

    @override_settings(
        MAILGUN_API_KEY="mg-test-key",
        MAILGUN_DOMAIN="mail.example.com",
    )
    def test_send_all_suppressed(self):
        provider = MailgunProvider()
        with patch.object(provider, "filter_suppressed", return_value=[]):
            result = provider.send(
                to=["suppressed@example.com"],
                subject="Test",
                text="body",
            )
        assert result.success is False

    @override_settings(MAILGUN_API_KEY=None, MAILGUN_DOMAIN="mail.example.com")
    def test_send_missing_api_key(self):
        provider = MailgunProvider()
        with patch.object(provider, "filter_suppressed", return_value=["user@example.com"]):
            result = provider.send(
                to=["user@example.com"],
                subject="Test",
                text="body",
            )
        assert result.success is False

    @override_settings(MAILGUN_DOMAIN=None, MAILGUN_API_KEY="key")
    def test_get_api_url_no_domain(self):
        provider = MailgunProvider()
        with pytest.raises(ValueError, match="MAILGUN_DOMAIN"):
            provider._get_api_url()

    def test_name_attribute(self):
        provider = MailgunProvider()
        assert provider.name == "mailgun"


# ---------------------------------------------------------------------------
# Tests: get_provider factory
# ---------------------------------------------------------------------------


class TestGetProvider:
    """Test the get_provider factory function."""

    @override_settings(EMAIL_PROVIDER="console")
    def test_get_default_provider(self):
        from django_matt.email.providers import get_provider

        provider = get_provider()
        assert isinstance(provider, ConsoleProvider)

    def test_get_provider_by_name(self):
        from django_matt.email.providers import get_provider

        provider = get_provider("console")
        assert isinstance(provider, ConsoleProvider)

    def test_get_provider_ses(self):
        from django_matt.email.providers import get_provider

        provider = get_provider("ses")
        assert isinstance(provider, SESProvider)

    def test_get_provider_sendgrid(self):
        from django_matt.email.providers import get_provider

        provider = get_provider("sendgrid")
        assert isinstance(provider, SendGridProvider)

    def test_get_provider_mailgun(self):
        from django_matt.email.providers import get_provider

        provider = get_provider("mailgun")
        assert isinstance(provider, MailgunProvider)

    def test_get_provider_unknown_raises(self):
        from django_matt.email.providers import get_provider

        with pytest.raises(ValueError, match="Unknown email provider"):
            get_provider("nonexistent")


# ---------------------------------------------------------------------------
# Tests: EmailService
# ---------------------------------------------------------------------------


class TestEmailService:
    """Test the EmailService high-level API."""

    @pytest.mark.django_db
    def test_send_creates_email_record(self):
        mock_provider = MagicMock(spec=EmailProviderBase)
        mock_provider.get_default_from_email.return_value = "noreply@example.com"
        mock_provider.filter_suppressed.return_value = ["user@example.com"]
        mock_provider.send.return_value = EmailResult(
            success=True, message_id="msg-1", provider="mock"
        )

        email = EmailService.send(
            to="user@example.com",
            subject="Welcome",
            text="Hello there",
            provider=mock_provider,
        )
        assert isinstance(email, EmailMessage)
        assert email.subject == "Welcome"
        assert "user@example.com" in email.to_emails
        assert email.status == EmailStatus.SENT

    @pytest.mark.django_db
    def test_send_normalizes_string_to_list(self):
        mock_provider = MagicMock(spec=EmailProviderBase)
        mock_provider.get_default_from_email.return_value = "noreply@example.com"
        mock_provider.filter_suppressed.return_value = ["single@example.com"]
        mock_provider.send.return_value = EmailResult(
            success=True, message_id="msg-2", provider="mock"
        )

        email = EmailService.send(
            to="single@example.com",
            subject="Test",
            text="Body",
            provider=mock_provider,
        )
        assert isinstance(email.to_emails, list)

    @pytest.mark.django_db
    def test_send_failed_provider(self):
        mock_provider = MagicMock(spec=EmailProviderBase)
        mock_provider.get_default_from_email.return_value = "noreply@example.com"
        mock_provider.filter_suppressed.return_value = ["user@example.com"]
        mock_provider.send.return_value = EmailResult(
            success=False, provider="mock", error="Provider down"
        )

        email = EmailService.send(
            to="user@example.com",
            subject="Fail Test",
            text="Body",
            provider=mock_provider,
        )
        assert email.status == EmailStatus.FAILED

    @pytest.mark.django_db
    def test_send_all_suppressed(self):
        mock_provider = MagicMock(spec=EmailProviderBase)
        mock_provider.get_default_from_email.return_value = "noreply@example.com"
        mock_provider.filter_suppressed.return_value = []

        email = EmailService.send(
            to="suppressed@example.com",
            subject="Suppressed",
            text="Body",
            provider=mock_provider,
        )
        assert email.status == EmailStatus.FAILED
        assert "suppressed" in email.error_message.lower()

    @pytest.mark.django_db
    def test_send_bulk(self):
        mock_provider = MagicMock(spec=EmailProviderBase)
        mock_provider.get_default_from_email.return_value = "noreply@example.com"
        mock_provider.filter_suppressed.side_effect = lambda x: x
        mock_provider.send.return_value = EmailResult(
            success=True, message_id="msg-bulk", provider="mock"
        )

        emails_data = [
            {"to": "a@example.com", "subject": "First", "text": "Body 1"},
            {"to": "b@example.com", "subject": "Second", "text": "Body 2"},
        ]
        results = EmailService.send_bulk(emails_data, provider=mock_provider)
        assert len(results) == 2
        assert all(isinstance(e, EmailMessage) for e in results)

    @pytest.mark.django_db
    @override_settings(EMAIL_PROVIDER="console")
    def test_send_with_string_provider_name(self):
        """EmailService.send should accept a provider name string."""
        email = EmailService.send(
            to="user@example.com",
            subject="String provider",
            text="Body",
            provider="console",
        )
        assert isinstance(email, EmailMessage)
        assert email.status == EmailStatus.SENT

    @pytest.mark.django_db
    def test_send_scheduled(self):
        mock_provider = MagicMock(spec=EmailProviderBase)
        mock_provider.get_default_from_email.return_value = "noreply@example.com"

        future = timezone.now() + timedelta(hours=1)
        email = EmailService.send(
            to="user@example.com",
            subject="Scheduled",
            text="Body",
            provider=mock_provider,
            scheduled_at=future,
        )
        # Scheduled emails should be queued, not sent
        assert email.status == EmailStatus.QUEUED
        assert email.scheduled_at == future
        # Provider.send should NOT have been called
        mock_provider.send.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: EmailTemplate rendering
# ---------------------------------------------------------------------------


class TestEmailTemplate:
    """Test EmailTemplate model rendering."""

    @pytest.mark.django_db
    def test_render_basic(self):
        template = EmailTemplate.objects.create(
            name="welcome",
            subject="Welcome {{ name }}",
            text_body="Hello {{ name }}, welcome!",
            html_body="<h1>Hello {{ name }}</h1>",
        )
        subject, text, html = template.render({"name": "Alice"})
        assert "Alice" in subject
        assert "Alice" in text
        assert "Alice" in html

    @pytest.mark.django_db
    def test_render_with_defaults(self):
        template = EmailTemplate.objects.create(
            name="default_ctx",
            subject="Hi {{ name }}",
            text_body="",
            html_body="<p>{{ greeting }}, {{ name }}</p>",
            default_context={"greeting": "Hey"},
        )
        subject, text, html = template.render({"name": "Bob"})
        assert "Bob" in subject
        assert "Hey" in html
        assert "Bob" in html

    @pytest.mark.django_db
    def test_render_override_defaults(self):
        template = EmailTemplate.objects.create(
            name="override_ctx",
            subject="{{ title }}",
            text_body="",
            html_body="<p>{{ body }}</p>",
            default_context={"title": "Default Title", "body": "Default Body"},
        )
        subject, text, html = template.render({"title": "Custom Title"})
        assert subject == "Custom Title"
        assert "Default Body" in html


# ---------------------------------------------------------------------------
# Tests: EmailMessage model
# ---------------------------------------------------------------------------


class TestEmailMessageModel:
    """Test EmailMessage model methods."""

    @pytest.mark.django_db
    def test_mark_sent(self):
        email = EmailMessage.objects.create(
            from_email="sender@example.com",
            to_emails=["user@example.com"],
            subject="Test",
        )
        email.mark_sent(provider="ses", message_id="ses-123")
        email.refresh_from_db()
        assert email.status == EmailStatus.SENT
        assert email.provider == "ses"
        assert email.provider_message_id == "ses-123"
        assert email.sent_at is not None

    @pytest.mark.django_db
    def test_mark_delivered(self):
        email = EmailMessage.objects.create(
            from_email="sender@example.com",
            to_emails=["user@example.com"],
            subject="Test",
            status=EmailStatus.SENT,
        )
        email.mark_delivered()
        email.refresh_from_db()
        assert email.status == EmailStatus.DELIVERED
        assert email.delivered_at is not None

    @pytest.mark.django_db
    def test_mark_failed(self):
        email = EmailMessage.objects.create(
            from_email="sender@example.com",
            to_emails=["user@example.com"],
            subject="Test",
        )
        email.mark_failed("Connection timeout")
        email.refresh_from_db()
        assert email.status == EmailStatus.FAILED
        assert email.error_message == "Connection timeout"
        assert email.retry_count == 1

    @pytest.mark.django_db
    def test_mark_bounced(self):
        email = EmailMessage.objects.create(
            from_email="sender@example.com",
            to_emails=["user@example.com"],
            subject="Test",
        )
        email.mark_bounced(BounceType.HARD)
        email.refresh_from_db()
        assert email.status == EmailStatus.BOUNCED
        assert email.metadata["bounce_type"] == BounceType.HARD

    @pytest.mark.django_db
    def test_to_dict(self):
        email = EmailMessage.objects.create(
            from_email="sender@example.com",
            to_emails=["user@example.com"],
            subject="Test Subject",
            text_body="Body text",
        )
        d = email.to_dict()
        assert d["from_email"] == "sender@example.com"
        assert d["to"] == ["user@example.com"]
        assert d["subject"] == "Test Subject"
        assert "tracking_id" in d["metadata"]

    @pytest.mark.django_db
    def test_str_representation(self):
        email = EmailMessage.objects.create(
            from_email="sender@example.com",
            to_emails=["user@example.com"],
            subject="A test subject",
        )
        assert "user@example.com" in str(email)


# ---------------------------------------------------------------------------
# Tests: SuppressedEmail model
# ---------------------------------------------------------------------------


class TestSuppressedEmail:
    """Test SuppressedEmail model."""

    @pytest.mark.django_db
    def test_add_suppression(self):
        suppressed = SuppressedEmail.add_suppression(
            email="BOUNCED@Example.com",
            reason="bounce",
            bounce_type=BounceType.HARD,
        )
        assert suppressed.email == "bounced@example.com"  # lowercased

    @pytest.mark.django_db
    def test_is_suppressed_true(self):
        SuppressedEmail.add_suppression(email="bad@example.com", reason="bounce")
        assert SuppressedEmail.is_suppressed("bad@example.com") is True

    @pytest.mark.django_db
    def test_is_suppressed_false(self):
        assert SuppressedEmail.is_suppressed("good@example.com") is False

    @pytest.mark.django_db
    def test_expired_suppression_not_suppressed(self):
        SuppressedEmail.add_suppression(
            email="expired@example.com",
            reason="bounce",
            bounce_type=BounceType.SOFT,
            expires_at=timezone.now() - timedelta(days=1),
        )
        assert SuppressedEmail.is_suppressed("expired@example.com") is False


# ---------------------------------------------------------------------------
# Tests: EmailMessageManager
# ---------------------------------------------------------------------------


class TestEmailMessageManager:
    """Test custom manager methods."""

    @pytest.mark.django_db
    def test_pending(self):
        EmailMessage.objects.create(
            from_email="s@e.com",
            to_emails=["a@e.com"],
            subject="p",
            status=EmailStatus.PENDING,
        )
        EmailMessage.objects.create(
            from_email="s@e.com",
            to_emails=["b@e.com"],
            subject="s",
            status=EmailStatus.SENT,
        )
        assert EmailMessage.objects.pending().count() == 1

    @pytest.mark.django_db
    def test_sent(self):
        EmailMessage.objects.create(
            from_email="s@e.com",
            to_emails=["a@e.com"],
            subject="s",
            status=EmailStatus.SENT,
        )
        EmailMessage.objects.create(
            from_email="s@e.com",
            to_emails=["b@e.com"],
            subject="d",
            status=EmailStatus.DELIVERED,
        )
        assert EmailMessage.objects.sent().count() == 2

    @pytest.mark.django_db
    def test_failed(self):
        EmailMessage.objects.create(
            from_email="s@e.com",
            to_emails=["a@e.com"],
            subject="f",
            status=EmailStatus.FAILED,
        )
        EmailMessage.objects.create(
            from_email="s@e.com",
            to_emails=["b@e.com"],
            subject="b",
            status=EmailStatus.BOUNCED,
        )
        assert EmailMessage.objects.failed().count() == 2


# ---------------------------------------------------------------------------
# Tests: Convenience functions
# ---------------------------------------------------------------------------


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    @pytest.mark.django_db
    @override_settings(EMAIL_PROVIDER="console")
    def test_send_email_function(self):
        email = send_email(to="user@example.com", subject="Quick Send", text="Body")
        assert isinstance(email, EmailMessage)
        assert email.status == EmailStatus.SENT

    @pytest.mark.django_db
    @override_settings(EMAIL_PROVIDER="console")
    def test_send_template_email_function(self):
        EmailTemplate.objects.create(
            name="test_tmpl",
            subject="Hello {{ name }}",
            text_body="Hi {{ name }}",
            html_body="<p>Hi {{ name }}</p>",
            is_active=True,
        )
        email = send_template_email(
            to="user@example.com",
            template_name="test_tmpl",
            context={"name": "World"},
        )
        assert isinstance(email, EmailMessage)
        assert "World" in email.subject

    @pytest.mark.django_db
    @override_settings(EMAIL_PROVIDER="console")
    def test_send_template_email_not_found(self):
        with pytest.raises(ValueError, match="Template not found"):
            send_template_email(
                to="user@example.com",
                template_name="nonexistent_template",
            )


# ---------------------------------------------------------------------------
# Tests: SMTPProvider
# ---------------------------------------------------------------------------


class TestSMTPProvider:
    """Test SMTPProvider with Django's locmem backend."""

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_send_success(self):
        from django.core import mail

        provider = SMTPProvider()
        with patch.object(provider, "filter_suppressed", return_value=["user@example.com"]):
            result = provider.send(
                to=["user@example.com"],
                subject="SMTP Test",
                text="Hello from SMTP",
                from_email="sender@example.com",
            )
        assert result.success is True
        assert result.provider == "smtp"
        assert result.message_id  # non-empty UUID
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "SMTP Test"
        assert mail.outbox[0].to == ["user@example.com"]

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_send_with_html(self):
        from django.core import mail

        provider = SMTPProvider()
        with patch.object(provider, "filter_suppressed", return_value=["user@example.com"]):
            result = provider.send(
                to=["user@example.com"],
                subject="HTML SMTP",
                html="<h1>Hello</h1>",
                from_email="sender@example.com",
            )
        assert result.success is True
        assert len(mail.outbox) == 1
        assert "<h1>Hello</h1>" in mail.outbox[0].alternatives[0][0]

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_send_with_cc_bcc_reply_to(self):
        from django.core import mail

        provider = SMTPProvider()
        with patch.object(provider, "filter_suppressed", return_value=["user@example.com"]):
            result = provider.send(
                to=["user@example.com"],
                subject="CC SMTP",
                text="body",
                from_email="sender@example.com",
                cc=["cc@example.com"],
                bcc=["bcc@example.com"],
                reply_to="reply@example.com",
            )
        assert result.success is True
        msg = mail.outbox[0]
        assert msg.cc == ["cc@example.com"]
        assert msg.bcc == ["bcc@example.com"]
        assert msg.reply_to == ["reply@example.com"]

    def test_send_all_suppressed(self):
        provider = SMTPProvider()
        with patch.object(provider, "filter_suppressed", return_value=[]):
            result = provider.send(
                to=["suppressed@example.com"],
                subject="Test",
                text="body",
            )
        assert result.success is False
        assert "suppressed" in result.error.lower()

    def test_send_exception_handling(self):
        provider = SMTPProvider()
        with (
            patch.object(provider, "filter_suppressed", return_value=["user@example.com"]),
            patch(
                "django_matt.email.providers.smtp.EmailMultiAlternatives.send",
                side_effect=Exception("SMTP connection refused"),
            ),
        ):
            result = provider.send(
                to=["user@example.com"],
                subject="Test",
                text="body",
                from_email="sender@example.com",
            )
        assert result.success is False
        assert "connection refused" in result.error.lower()

    def test_name_attribute(self):
        provider = SMTPProvider()
        assert provider.name == "smtp"


# ---------------------------------------------------------------------------
# Tests: EMAIL Requirement Success Criteria
# ---------------------------------------------------------------------------


class TestEmailRequirements:
    """Tests aligned with EMAIL-01 through EMAIL-05 success criteria."""

    @pytest.mark.django_db
    @override_settings(SENDGRID_API_KEY="sg-test-key-123")
    def test_email_01_sendgrid_backend_sends(self):
        """EMAIL-01: SendGrid email backend sends via mock HTTP and returns success."""
        import sys

        with patch.dict(
            sys.modules,
            {
                "sendgrid": MagicMock(),
                "sendgrid.helpers": MagicMock(),
                "sendgrid.helpers.mail": MagicMock(),
            },
        ):
            provider = SendGridProvider()
            mock_response = MagicMock()
            mock_response.status_code = 202
            mock_response.body = ""
            mock_response.headers = {"X-Message-Id": "sg-req-test"}

            mock_client = MagicMock()
            mock_client.send.return_value = mock_response
            provider._client = mock_client

            with patch.object(provider, "filter_suppressed", return_value=["alice@example.com"]):
                result = provider.send(
                    to=["alice@example.com"],
                    subject="SendGrid Requirement Test",
                    text="EMAIL-01 verification",
                )
        assert result.success is True
        assert result.provider == "sendgrid"
        mock_client.send.assert_called_once()

    @pytest.mark.django_db
    @override_settings(
        MAILGUN_API_KEY="mg-test-key",
        MAILGUN_DOMAIN="mail.example.com",
    )
    def test_email_02_mailgun_backend_sends(self):
        """EMAIL-02: Mailgun email backend sends via mock HTTP and returns success."""
        provider = MailgunProvider()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "<req-test@mail.example.com>",
            "message": "Queued",
        }

        with (
            patch.object(provider, "filter_suppressed", return_value=["alice@example.com"]),
            patch("requests.post", return_value=mock_response) as mock_post,
        ):
            result = provider.send(
                to=["alice@example.com"],
                subject="Mailgun Requirement Test",
                text="EMAIL-02 verification",
            )
        assert result.success is True
        assert result.provider == "mailgun"
        mock_post.assert_called_once()

    @pytest.mark.django_db
    @override_settings(AWS_SES_REGION_NAME="us-east-1")
    def test_email_03_ses_backend_sends(self):
        """EMAIL-03: AWS SES email backend sends via mock boto3 and returns success."""
        provider = SESProvider()
        mock_client = MagicMock()
        mock_client.send_email.return_value = {"MessageId": "ses-req-test"}

        provider._client = mock_client
        with patch.object(provider, "filter_suppressed", return_value=["alice@example.com"]):
            result = provider.send(
                to=["alice@example.com"],
                subject="SES Requirement Test",
                text="EMAIL-03 verification",
                from_email="sender@example.com",
            )
        assert result.success is True
        assert result.message_id == "ses-req-test"
        assert result.provider == "ses"
        mock_client.send_email.assert_called_once()

    @pytest.mark.django_db
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_email_04_smtp_backend_sends(self):
        """EMAIL-04: SMTP fallback backend sends via Django mail backend."""
        from django.core import mail

        provider = SMTPProvider()
        with patch.object(provider, "filter_suppressed", return_value=["alice@example.com"]):
            result = provider.send(
                to=["alice@example.com"],
                subject="SMTP Requirement Test",
                text="EMAIL-04 verification",
                from_email="sender@example.com",
            )
        assert result.success is True
        assert result.provider == "smtp"
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "SMTP Requirement Test"
        assert mail.outbox[0].body == "EMAIL-04 verification"

    @pytest.mark.django_db
    @override_settings(EMAIL_PROVIDER="console")
    def test_email_05_template_variable_substitution(self):
        """EMAIL-05: Email templates with {{ variable }} substitution render and dispatch correctly."""
        # Create a template with variable placeholders
        EmailTemplate.objects.create(
            name="req_test_welcome",
            subject="Hello {{ first_name }}",
            text_body="Welcome, {{ first_name }}! Your account {{ email }} is ready.",
            html_body="<p>Welcome, {{ first_name }}! Your account {{ email }} is ready.</p>",
            is_active=True,
        )

        # Send through the template pipeline
        email = send_template_email(
            to="alice@example.com",
            template_name="req_test_welcome",
            context={"first_name": "Alice", "email": "alice@example.com"},
        )

        # Verify rendered subject
        assert email.subject == "Hello Alice"
        # Verify rendered text body contains substituted values
        assert "Welcome, Alice!" in email.text_body
        assert "alice@example.com" in email.text_body
        # Verify rendered HTML body
        assert "Welcome, Alice!" in email.html_body
        # Verify the email was sent successfully
        assert email.status == EmailStatus.SENT
