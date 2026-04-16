from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.core.mail import EmailMessage, EmailMultiAlternatives

from django_matt_resend.backend import ResendEmailBackend
from django_matt_resend.config import ResendConfig
from django_matt_resend.plugin import ResendPlugin


class TestResendConfig:
    def test_default_config(self) -> None:
        config = ResendConfig()
        assert config.api_key == ""
        assert config.default_from == ""
        assert config.reply_to == ""

    def test_validation_missing_api_key(self) -> None:
        config = ResendConfig(default_from="test@example.com")
        errors = config.validate()
        assert len(errors) == 1
        assert "API_KEY" in errors[0]

    def test_validation_missing_default_from(self) -> None:
        config = ResendConfig(api_key="re_test_123")
        errors = config.validate()
        assert len(errors) == 1
        assert "DEFAULT_FROM" in errors[0]

    def test_validation_passes(self) -> None:
        config = ResendConfig(
            api_key="re_test_123", default_from="test@example.com"
        )
        assert config.validate() == []


class TestResendEmailBackend:
    @patch("django_matt_resend.backend.get_resend_config")
    def test_backend_init(self, mock_config: MagicMock) -> None:
        mock_config.return_value = ResendConfig(
            api_key="re_test_123",
            default_from="test@example.com",
        )
        backend = ResendEmailBackend()
        assert backend._api_key == "re_test_123"
        assert backend._default_from == "test@example.com"

    @patch("django_matt_resend.backend.get_resend_config")
    def test_backend_custom_api_key(self, mock_config: MagicMock) -> None:
        mock_config.return_value = ResendConfig()
        backend = ResendEmailBackend(api_key="re_custom")
        assert backend._api_key == "re_custom"

    @patch("django_matt_resend.backend.get_resend_config")
    def test_open_close(self, mock_config: MagicMock) -> None:
        mock_config.return_value = ResendConfig(api_key="re_test_123")
        backend = ResendEmailBackend()
        assert backend.open() is True
        assert backend._opened is True
        assert backend.open() is False  # already open
        backend.close()
        assert backend._opened is False

    @patch("django_matt_resend.backend.get_resend_config")
    @patch("django_matt_resend.backend.resend.Emails.send")
    def test_send_plain_text(
        self, mock_send: MagicMock, mock_config: MagicMock
    ) -> None:
        mock_config.return_value = ResendConfig(
            api_key="re_test_123",
            default_from="sender@example.com",
        )
        mock_send.return_value = {"id": "email_123"}

        backend = ResendEmailBackend()
        msg = EmailMessage(
            subject="Test",
            body="Hello",
            to=["user@example.com"],
        )
        sent = backend.send_messages([msg])
        assert sent == 1

        call_args = mock_send.call_args[0][0]
        assert call_args["from_"] == "sender@example.com"
        assert call_args["to"] == ["user@example.com"]
        assert call_args["subject"] == "Test"
        assert call_args["text"] == "Hello"

    @patch("django_matt_resend.backend.get_resend_config")
    @patch("django_matt_resend.backend.resend.Emails.send")
    def test_send_html_email(
        self, mock_send: MagicMock, mock_config: MagicMock
    ) -> None:
        mock_config.return_value = ResendConfig(
            api_key="re_test_123",
            default_from="sender@example.com",
        )
        mock_send.return_value = {"id": "email_456"}

        backend = ResendEmailBackend()
        msg = EmailMultiAlternatives(
            subject="HTML Test",
            body="Fallback text",
            to=["user@example.com"],
        )
        msg.attach_alternative("<h1>Hello</h1>", "text/html")
        sent = backend.send_messages([msg])
        assert sent == 1

        call_args = mock_send.call_args[0][0]
        assert call_args["html"] == "<h1>Hello</h1>"
        assert call_args["text"] == "Fallback text"

    @patch("django_matt_resend.backend.get_resend_config")
    @patch("django_matt_resend.backend.resend.Emails.send")
    def test_send_with_cc_bcc(
        self, mock_send: MagicMock, mock_config: MagicMock
    ) -> None:
        mock_config.return_value = ResendConfig(
            api_key="re_test_123",
            default_from="sender@example.com",
        )
        mock_send.return_value = {"id": "email_789"}

        backend = ResendEmailBackend()
        msg = EmailMessage(
            subject="CC Test",
            body="Hello",
            to=["user@example.com"],
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
        )
        sent = backend.send_messages([msg])
        assert sent == 1

        call_args = mock_send.call_args[0][0]
        assert call_args["cc"] == ["cc@example.com"]
        assert call_args["bcc"] == ["bcc@example.com"]

    @patch("django_matt_resend.backend.get_resend_config")
    @patch("django_matt_resend.backend.resend.Emails.send")
    def test_send_with_attachments(
        self, mock_send: MagicMock, mock_config: MagicMock
    ) -> None:
        mock_config.return_value = ResendConfig(
            api_key="re_test_123",
            default_from="sender@example.com",
        )
        mock_send.return_value = {"id": "email_att"}

        backend = ResendEmailBackend()
        msg = EmailMessage(
            subject="Attachment Test",
            body="See attached",
            to=["user@example.com"],
        )
        msg.attach("report.csv", "a,b,c\n1,2,3", "text/csv")
        sent = backend.send_messages([msg])
        assert sent == 1

        call_args = mock_send.call_args[0][0]
        assert len(call_args["attachments"]) == 1
        assert call_args["attachments"][0]["filename"] == "report.csv"

    @patch("django_matt_resend.backend.get_resend_config")
    def test_send_empty_list(self, mock_config: MagicMock) -> None:
        mock_config.return_value = ResendConfig(api_key="re_test_123")
        backend = ResendEmailBackend()
        assert backend.send_messages([]) == 0

    @patch("django_matt_resend.backend.get_resend_config")
    @patch("django_matt_resend.backend.resend.Emails.send")
    def test_send_failure_raises(
        self, mock_send: MagicMock, mock_config: MagicMock
    ) -> None:
        mock_config.return_value = ResendConfig(
            api_key="re_test_123",
            default_from="sender@example.com",
        )
        mock_send.side_effect = Exception("API error")

        backend = ResendEmailBackend(fail_silently=False)
        msg = EmailMessage(
            subject="Fail", body="boom", to=["user@example.com"]
        )
        with pytest.raises(Exception, match="API error"):
            backend.send_messages([msg])

    @patch("django_matt_resend.backend.get_resend_config")
    @patch("django_matt_resend.backend.resend.Emails.send")
    def test_send_failure_silent(
        self, mock_send: MagicMock, mock_config: MagicMock
    ) -> None:
        mock_config.return_value = ResendConfig(
            api_key="re_test_123",
            default_from="sender@example.com",
        )
        mock_send.side_effect = Exception("API error")

        backend = ResendEmailBackend(fail_silently=True)
        msg = EmailMessage(
            subject="Fail", body="boom", to=["user@example.com"]
        )
        sent = backend.send_messages([msg])
        assert sent == 0


class TestPluginMeta:
    def test_plugin_name(self) -> None:
        plugin = ResendPlugin()
        assert plugin.name == "resend"

    def test_plugin_version(self) -> None:
        plugin = ResendPlugin()
        assert plugin.version == "0.1.0"

    def test_settings_schema(self) -> None:
        plugin = ResendPlugin()
        schema = plugin.get_settings_schema()
        assert "API_KEY" in schema["properties"]
        assert "DEFAULT_FROM" in schema["properties"]
        assert "API_KEY" in schema["required"]
