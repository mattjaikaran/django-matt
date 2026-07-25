from __future__ import annotations

import base64
import hashlib
import hmac
from unittest.mock import MagicMock

from django_matt_clerk_auth.config import ClerkConfig
from django_matt_clerk_auth.controllers import ClerkWebhookController
from django_matt_clerk_auth.middleware import (
    ClerkAuthMiddleware,
)
from django_matt_clerk_auth.plugin import ClerkAuthPlugin


class TestClerkConfig:
    def test_default_config(self) -> None:
        config = ClerkConfig()
        assert config.api_base_url == "https://api.clerk.com/v1"
        assert config.auto_create_user is True
        assert config.webhook_path == "/webhooks/clerk"

    def test_validation_missing_secret_key(self) -> None:
        config = ClerkConfig(publishable_key="pk_test_abc")
        errors = config.validate()
        assert len(errors) == 1
        assert "SECRET_KEY" in errors[0]

    def test_validation_missing_jwks_and_publishable(self) -> None:
        config = ClerkConfig(secret_key="sk_test_abc")
        errors = config.validate()
        assert len(errors) == 1
        assert "JWKS_URL" in errors[0]

    def test_validation_passes(self) -> None:
        config = ClerkConfig(
            secret_key="sk_test_abc",
            publishable_key="pk_test_abc",
        )
        assert config.validate() == []


class TestSvixSignatureVerification:
    def _make_request(
        self,
        body: bytes,
        svix_id: str = "msg_123",
        svix_timestamp: str = "1234567890",
        svix_signature: str = "",
    ) -> MagicMock:
        request = MagicMock()
        request.body = body
        request.META = {
            "HTTP_SVIX_ID": svix_id,
            "HTTP_SVIX_TIMESTAMP": svix_timestamp,
            "HTTP_SVIX_SIGNATURE": svix_signature,
        }
        return request

    def _sign(
        self,
        body: str,
        secret: str,
        svix_id: str = "msg_123",
        svix_timestamp: str = "1234567890",
    ) -> str:
        raw_secret = secret
        if raw_secret.startswith("whsec_"):
            raw_secret = raw_secret[6:]
        secret_bytes = base64.b64decode(raw_secret)
        signed_content = f"{svix_id}.{svix_timestamp}.{body}"
        sig = hmac.new(
            secret_bytes,
            signed_content.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return f"v1,{base64.b64encode(sig).decode('utf-8')}"

    def test_valid_signature(self) -> None:
        secret = "whsec_" + base64.b64encode(b"testsecret123456").decode()
        body = '{"type":"user.created","data":{}}'
        sig = self._sign(body, secret)
        request = self._make_request(body=body.encode(), svix_signature=sig)

        result = ClerkWebhookController._verify_signature(request, secret)
        assert result is True

    def test_invalid_signature(self) -> None:
        secret = "whsec_" + base64.b64encode(b"testsecret123456").decode()
        body = '{"type":"user.created","data":{}}'
        request = self._make_request(body=body.encode(), svix_signature="v1,invalidsig")

        result = ClerkWebhookController._verify_signature(request, secret)
        assert result is False

    def test_missing_headers(self) -> None:
        secret = "whsec_" + base64.b64encode(b"testsecret123456").decode()
        request = self._make_request(
            body=b"{}", svix_id="", svix_timestamp="", svix_signature=""
        )

        result = ClerkWebhookController._verify_signature(request, secret)
        assert result is False

    def test_no_secret_allows_passthrough(self) -> None:
        request = self._make_request(body=b"{}")
        result = ClerkWebhookController._verify_signature(request, "")
        assert result is True  # dev mode passthrough


class TestPluginMeta:
    def test_plugin_name(self) -> None:
        plugin = ClerkAuthPlugin()
        assert plugin.name == "clerk_auth"

    def test_plugin_version(self) -> None:
        plugin = ClerkAuthPlugin()
        assert plugin.version == "0.1.0"

    def test_middleware_returned(self) -> None:
        plugin = ClerkAuthPlugin()
        middleware = plugin.get_middleware()
        assert ClerkAuthMiddleware in middleware

    def test_settings_schema(self) -> None:
        plugin = ClerkAuthPlugin()
        schema = plugin.get_settings_schema()
        assert "SECRET_KEY" in schema["properties"]
        assert "SECRET_KEY" in schema["required"]
        assert "AUTO_CREATE_USER" in schema["properties"]
