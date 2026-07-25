"""Tests for SSO authentication (SAML, OIDC, base provider, models)."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory

import pytest

from django_matt.auth.sso.config import SSOConfig, get_sso_config, reset_sso_config
from django_matt.auth.sso.models import SSOConnection, SSOUserLink
from django_matt.auth.sso.providers.base import (
    SSOAuthenticationError,
    SSOConfigError,
    SSOProvider,
    SSOUserInfo,
)
from django_matt.auth.sso.providers.oidc import OIDCProvider

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_connection(**overrides) -> MagicMock:
    """Build a MagicMock SSOConnection with sensible SAML/OIDC defaults."""
    defaults = dict(
        id=1,
        organization_id="acme",
        provider_type="oidc",
        name="Acme OIDC",
        is_active=True,
        is_required=False,
        domains=["acme.com"],
        # SAML
        idp_entity_id="https://idp.acme.com",
        idp_sso_url="https://idp.acme.com/sso",
        idp_slo_url="https://idp.acme.com/slo",
        idp_certificate="MIIC...",
        # OIDC
        client_id="client-123",
        client_secret="secret-456",
        discovery_url="",
        authorization_url="https://idp.acme.com/authorize",
        token_url="https://idp.acme.com/token",
        userinfo_url="https://idp.acme.com/userinfo",
        # Mapping / config
        attribute_mapping={},
        default_role="member",
        extra_config={},
    )
    defaults.update(overrides)
    conn = MagicMock(**defaults)
    conn.get_callback_url.return_value = "https://app.acme.com/auth/sso/acme/callback"
    conn.get_sp_entity_id.return_value = "https://app.acme.com/auth/sso/acme/metadata"
    return conn


def _make_sso_config(**overrides) -> SSOConfig:
    """Return a test SSOConfig with sensible defaults."""
    defaults = dict(
        enabled=True,
        callback_url_base="https://app.acme.com",
        state_cache_prefix="sso_state",
        state_timeout=600,
    )
    defaults.update(overrides)
    return SSOConfig(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the Django cache before and after each test."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _reset_config():
    """Reset the global SSO config singleton between tests."""
    reset_sso_config()
    yield
    reset_sso_config()


@pytest.fixture
def mock_connection():
    return _make_mock_connection()


@pytest.fixture
def sso_config():
    return _make_sso_config()


# ===================================================================
# Base SSOProvider Tests
# ===================================================================


class TestBaseProvider:
    """Tests for SSOProvider base class (generate_state, verify_state, map_attributes)."""

    def _make_provider(self, connection=None, config=None):
        """Instantiate a concrete subclass of SSOProvider for testing."""
        conn = connection or _make_mock_connection()
        cfg = config or _make_sso_config()
        with patch("django_matt.auth.sso.config.get_sso_config", return_value=cfg):
            # Use OIDCProvider as a concrete subclass
            provider = OIDCProvider.__new__(OIDCProvider)
            SSOProvider.__init__(provider, conn)
            provider._discovered_config = None
            return provider

    def test_generate_state_returns_string(self):
        provider = self._make_provider()
        state = provider.generate_state()
        assert isinstance(state, str)
        assert len(state) > 20

    def test_generate_state_stores_in_cache(self):
        provider = self._make_provider()
        state = provider.generate_state()
        cache_key = f"sso_state:{state}"
        data = cache.get(cache_key)
        assert data is not None
        assert data["organization_id"] == "acme"

    def test_generate_state_with_extra_data(self):
        provider = self._make_provider()
        state = provider.generate_state(extra_data={"redirect": "/dashboard"})
        cache_key = f"sso_state:{state}"
        data = cache.get(cache_key)
        assert data["redirect"] == "/dashboard"
        assert data["organization_id"] == "acme"

    def test_verify_state_returns_data_and_deletes(self):
        provider = self._make_provider()
        state = provider.generate_state()
        data = provider.verify_state(state)
        assert data is not None
        assert data["organization_id"] == "acme"
        # One-time use: second call returns None
        assert provider.verify_state(state) is None

    def test_verify_state_invalid_returns_none(self):
        provider = self._make_provider()
        assert provider.verify_state("bogus-token") is None

    def test_validate_connection_inactive_raises(self):
        conn = _make_mock_connection(is_active=False)
        provider = self._make_provider(connection=conn)
        with pytest.raises(SSOConfigError, match="not active"):
            provider._validate_connection()

    def test_map_attributes_default_mapping(self):
        provider = self._make_provider()
        raw = {
            "sub": "user-42",
            "email": "alice@acme.com",
            "email_verified": True,
            "name": "Alice Acme",
            "given_name": "Alice",
            "family_name": "Acme",
            "groups": ["engineering", "platform"],
            "roles": ["admin"],
        }
        info = provider.map_attributes(raw)
        assert info.idp_user_id == "user-42"
        assert info.email == "alice@acme.com"
        assert info.email_verified is True
        assert info.name == "Alice Acme"
        assert info.first_name == "Alice"
        assert info.last_name == "Acme"
        assert info.groups == ["engineering", "platform"]
        assert info.roles == ["admin"]

    def test_map_attributes_custom_mapping(self):
        conn = _make_mock_connection(attribute_mapping={"email": "custom_email", "name": "display"})
        provider = self._make_provider(connection=conn)
        raw = {
            "sub": "u-1",
            "custom_email": "bob@acme.com",
            "display": "Bob Builder",
        }
        info = provider.map_attributes(raw)
        assert info.email == "bob@acme.com"
        assert info.name == "Bob Builder"

    def test_map_attributes_list_values_takes_first(self):
        """SAML attributes often come as lists; scalar fields take first element."""
        provider = self._make_provider()
        raw = {
            "sub": "u-1",
            "email": ["alice@acme.com", "secondary@acme.com"],
        }
        info = provider.map_attributes(raw)
        assert info.email == "alice@acme.com"

    def test_map_attributes_email_verified_string(self):
        """email_verified can arrive as string 'true'."""
        provider = self._make_provider()
        raw = {"sub": "u-1", "email_verified": "true"}
        info = provider.map_attributes(raw)
        assert info.email_verified is True

    def test_map_attributes_missing_fields(self):
        provider = self._make_provider()
        raw = {"sub": "u-1"}
        info = provider.map_attributes(raw)
        assert info.idp_user_id == "u-1"
        assert info.email is None
        assert info.name is None
        assert info.groups is None


# ===================================================================
# OIDC Provider Tests
# ===================================================================


class TestOIDCProvider:
    """Tests for OIDCProvider (login URL, PKCE, token decode, callback)."""

    def _make_provider(self, connection=None, config=None):
        conn = connection or _make_mock_connection(provider_type="oidc")
        cfg = config or _make_sso_config()
        with patch("django_matt.auth.sso.config.get_sso_config", return_value=cfg):
            provider = OIDCProvider(conn)
        return provider

    # -- get_login_url -------------------------------------------------

    def test_get_login_url_has_required_params(self):
        provider = self._make_provider()
        url = provider.get_login_url()
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert parsed.netloc == "idp.acme.com"
        assert parsed.path == "/authorize"

        assert params["client_id"] == ["client-123"]
        assert params["response_type"] == ["code"]
        assert "state" in params
        assert "nonce" in params
        assert params["code_challenge_method"] == ["S256"]
        assert "code_challenge" in params
        assert "openid" in params["scope"][0]

    def test_get_login_url_stores_pkce_and_nonce_in_cache(self):
        provider = self._make_provider()
        url = provider.get_login_url()
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        state = params["state"][0]

        pkce_key = f"sso_state:pkce:{state}"
        nonce_key = f"sso_state:nonce:{state}"

        assert cache.get(pkce_key) is not None  # code_verifier stored
        assert cache.get(nonce_key) is not None  # nonce stored

    def test_get_login_url_with_custom_relay_state(self):
        provider = self._make_provider()
        # Pre-store state data so generate_state is not called
        cache.set("sso_state:my-relay", {"organization_id": "acme"}, 600)
        url = provider.get_login_url(relay_state="my-relay")
        params = parse_qs(urlparse(url).query)
        assert params["state"] == ["my-relay"]

    def test_get_login_url_missing_client_id_raises(self):
        conn = _make_mock_connection(client_id="")
        provider = self._make_provider(connection=conn)
        with pytest.raises(SSOConfigError, match="client_id"):
            provider.get_login_url()

    def test_get_login_url_inactive_connection_raises(self):
        conn = _make_mock_connection(is_active=False)
        provider = self._make_provider(connection=conn)
        with pytest.raises(SSOConfigError, match="not active"):
            provider.get_login_url()

    # -- PKCE ----------------------------------------------------------

    def test_generate_code_verifier_produces_valid_pair(self):
        provider = self._make_provider()
        verifier, challenge = provider._generate_code_verifier()

        # Verifier should be a URL-safe string
        assert isinstance(verifier, str)
        assert len(verifier) > 40

        # Challenge is base64url(sha256(verifier)) without padding
        expected = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        assert challenge == expected

    # -- _decode_id_token ----------------------------------------------

    @pytest.mark.asyncio
    async def test_decode_id_token_valid(self):
        import hmac as _hmac

        provider = self._make_provider()
        payload = {"sub": "user-42", "email": "alice@acme.com", "nonce": "n-123"}

        # Build a real HS256 JWT so signature verification passes
        header = {"alg": "HS256", "typ": "JWT"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        sig = _hmac.new(b"secret-456", signing_input, hashlib.sha256).digest()
        sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
        fake_jwt = f"{header_b64}.{payload_b64}.{sig_b64}"

        decoded = await provider._decode_id_token(fake_jwt)
        assert decoded["sub"] == "user-42"
        assert decoded["email"] == "alice@acme.com"
        assert decoded["nonce"] == "n-123"

    @pytest.mark.asyncio
    async def test_decode_id_token_invalid_format(self):
        provider = self._make_provider()
        with pytest.raises(SSOAuthenticationError, match="Invalid id_token"):
            await provider._decode_id_token("not.a.valid.jwt.here")

    @pytest.mark.asyncio
    async def test_decode_id_token_corrupt_payload(self):
        provider = self._make_provider()
        with pytest.raises(SSOAuthenticationError, match="Failed to decode"):
            await provider._decode_id_token("header.!!!invalid!!!.signature")

    # -- process_callback ----------------------------------------------

    @pytest.mark.asyncio
    async def test_process_callback_success(self):
        provider = self._make_provider()

        state = provider.generate_state()
        code_verifier = "test-verifier"
        nonce = "test-nonce"
        cache.set(f"sso_state:pkce:{state}", code_verifier, 600)
        cache.set(f"sso_state:nonce:{state}", nonce, 600)

        # Build a fake id_token with the nonce
        id_payload = {"sub": "user-42", "email": "alice@acme.com", "nonce": nonce}
        id_b64 = base64.urlsafe_b64encode(json.dumps(id_payload).encode()).decode().rstrip("=")
        fake_id_token = f"h.{id_b64}.s"

        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {
            "access_token": "at-xyz",
            "id_token": fake_id_token,
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=token_response)

        request = RequestFactory().get("/callback", {"code": "auth-code-123", "state": state})

        # Mock _decode_id_token to return the payload directly (skips signature verification)
        async def mock_decode(token):
            return id_payload

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch.object(provider, "_decode_id_token", side_effect=mock_decode),
        ):
            user_info = await provider.process_callback(request)

        assert isinstance(user_info, SSOUserInfo)
        assert user_info.idp_user_id == "user-42"
        assert user_info.email == "alice@acme.com"

    @pytest.mark.asyncio
    async def test_process_callback_nonce_mismatch_raises(self):
        """Nonce mismatch now correctly raises SSOAuthenticationError
        because id_token signature verification errors are re-raised."""
        provider = self._make_provider()

        state = provider.generate_state()
        cache.set(f"sso_state:pkce:{state}", "verifier", 600)
        cache.set(f"sso_state:nonce:{state}", "expected-nonce", 600)

        # id_token has a wrong nonce but a valid sub
        id_payload = {"sub": "user-42", "email": "alice@acme.com", "nonce": "wrong-nonce"}
        id_b64 = base64.urlsafe_b64encode(json.dumps(id_payload).encode()).decode().rstrip("=")
        fake_id_token = f"h.{id_b64}.s"

        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {
            "access_token": "at",
            "id_token": fake_id_token,
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=token_response)

        request = RequestFactory().get("/callback", {"code": "code", "state": state})

        # Mock _decode_id_token to return payload with wrong nonce
        async def mock_decode(token):
            return id_payload

        # SSOAuthenticationError is now re-raised on nonce mismatch
        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch.object(provider, "_decode_id_token", side_effect=mock_decode),
            pytest.raises(SSOAuthenticationError, match="Invalid nonce"),
        ):
            await provider.process_callback(request)

    @pytest.mark.asyncio
    async def test_process_callback_no_id_token_uses_userinfo(self):
        """When no id_token is returned, the provider falls back to userinfo."""
        provider = self._make_provider()

        state = provider.generate_state()
        cache.set(f"sso_state:pkce:{state}", "verifier", 600)
        cache.set(f"sso_state:nonce:{state}", "nonce", 600)

        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {
            "access_token": "at-xyz",
            # No id_token
        }

        userinfo_response = MagicMock()
        userinfo_response.status_code = 200
        userinfo_response.json.return_value = {
            "sub": "user-99",
            "email": "bob@acme.com",
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=token_response)
        mock_client.get = AsyncMock(return_value=userinfo_response)

        request = RequestFactory().get("/callback", {"code": "code", "state": state})

        with patch("httpx.AsyncClient", return_value=mock_client):
            user_info = await provider.process_callback(request)

        assert user_info.idp_user_id == "user-99"
        assert user_info.email == "bob@acme.com"

    @pytest.mark.asyncio
    async def test_process_callback_missing_code(self):
        provider = self._make_provider()
        request = RequestFactory().get("/callback", {"state": "s"})
        with pytest.raises(SSOAuthenticationError, match="No authorization code"):
            await provider.process_callback(request)

    @pytest.mark.asyncio
    async def test_process_callback_idp_error(self):
        provider = self._make_provider()
        request = RequestFactory().get(
            "/callback",
            {"error": "access_denied", "error_description": "User denied"},
        )
        with pytest.raises(SSOAuthenticationError, match="User denied"):
            await provider.process_callback(request)

    # -- discovery caching ---------------------------------------------

    def test_discovery_sync_uses_cache(self):
        conn = _make_mock_connection(
            discovery_url="https://idp.acme.com/.well-known/openid-configuration"
        )
        provider = self._make_provider(connection=conn)

        discovery_data = {
            "authorization_endpoint": "https://idp.acme.com/authorize",
            "token_endpoint": "https://idp.acme.com/token",
            "userinfo_endpoint": "https://idp.acme.com/userinfo",
        }
        # Pre-seed cache
        cache.set(f"oidc_discovery:{conn.id}", discovery_data, 3600)

        config = provider._get_discovery_config_sync()
        assert config["authorization_endpoint"] == "https://idp.acme.com/authorize"
        # No HTTP call was made

    def test_discovery_sync_falls_back_to_manual_urls(self):
        """When no discovery_url, manual URLs are returned."""
        conn = _make_mock_connection(
            discovery_url="",
            authorization_url="https://manual.auth/authorize",
            token_url="https://manual.auth/token",
            userinfo_url="https://manual.auth/userinfo",
        )
        provider = self._make_provider(connection=conn)
        config = provider._get_discovery_config_sync()
        assert config["authorization_endpoint"] == "https://manual.auth/authorize"
        assert config["token_endpoint"] == "https://manual.auth/token"

    # -- get_logout_url ------------------------------------------------

    def test_get_logout_url_with_end_session_endpoint(self):
        conn = _make_mock_connection(
            discovery_url="https://idp.acme.com/.well-known/openid-configuration"
        )
        provider = self._make_provider(connection=conn)
        # Seed discovery cache with end_session_endpoint
        cache.set(
            f"oidc_discovery:{conn.id}",
            {"end_session_endpoint": "https://idp.acme.com/logout"},
            3600,
        )
        url = provider.get_logout_url(relay_state="https://app.acme.com/logged-out")
        assert "idp.acme.com/logout" in url
        assert "post_logout_redirect_uri" in url

    def test_get_logout_url_none_when_no_endpoint(self):
        conn = _make_mock_connection(discovery_url="")
        provider = self._make_provider(connection=conn)
        # Manual config has no end_session_endpoint
        assert provider.get_logout_url() is None


# ===================================================================
# SAML Provider Tests
# ===================================================================


class TestSAMLProvider:
    """Tests for SAMLProvider (settings build, login URL, prepare_request)."""

    @pytest.fixture(autouse=True)
    def _check_saml(self):
        pytest.importorskip("onelogin")

    def _make_provider(self, connection=None, config=None):
        from django_matt.auth.sso.providers.saml import SAMLProvider

        conn = connection or _make_mock_connection(provider_type="saml")
        cfg = config or _make_sso_config()
        with patch("django_matt.auth.sso.config.get_sso_config", return_value=cfg):
            provider = SAMLProvider(conn)
        return provider

    # -- _get_saml_settings -------------------------------------------

    def test_get_saml_settings_structure(self):
        provider = self._make_provider()
        settings = provider._get_saml_settings()

        assert settings["strict"] is True
        assert settings["debug"] is False
        assert settings["sp"]["entityId"] == "https://app.acme.com/auth/sso/acme/metadata"
        assert settings["sp"]["assertionConsumerService"]["url"] == (
            "https://app.acme.com/auth/sso/acme/callback"
        )
        assert settings["idp"]["entityId"] == "https://idp.acme.com"
        assert settings["idp"]["singleSignOnService"]["url"] == "https://idp.acme.com/sso"
        assert settings["idp"]["x509cert"] == "MIIC..."

    def test_get_saml_settings_includes_slo_when_configured(self):
        provider = self._make_provider()
        settings = provider._get_saml_settings()
        assert "singleLogoutService" in settings["idp"]
        assert settings["idp"]["singleLogoutService"]["url"] == "https://idp.acme.com/slo"

    def test_get_saml_settings_no_slo_when_empty(self):
        conn = _make_mock_connection(provider_type="saml", idp_slo_url="")
        provider = self._make_provider(connection=conn)
        settings = provider._get_saml_settings()
        assert "singleLogoutService" not in settings["idp"]

    def test_get_saml_settings_missing_entity_id_raises(self):
        conn = _make_mock_connection(provider_type="saml", idp_entity_id="")
        provider = self._make_provider(connection=conn)
        with pytest.raises(SSOConfigError, match="Entity ID"):
            provider._get_saml_settings()

    def test_get_saml_settings_missing_certificate_raises(self):
        conn = _make_mock_connection(provider_type="saml", idp_certificate="")
        provider = self._make_provider(connection=conn)
        with pytest.raises(SSOConfigError, match="Certificate"):
            provider._get_saml_settings()

    def test_get_saml_settings_missing_sso_url_raises(self):
        conn = _make_mock_connection(provider_type="saml", idp_sso_url="")
        provider = self._make_provider(connection=conn)
        with pytest.raises(SSOConfigError, match="SSO URL"):
            provider._get_saml_settings()

    # -- _prepare_request ----------------------------------------------

    def test_prepare_request_extracts_values(self):
        provider = self._make_provider()
        rf = RequestFactory()
        request = rf.post(
            "/auth/sso/acme/callback",
            data={"SAMLResponse": "base64data"},
            HTTP_X_FORWARDED_HOST="proxy.acme.com",
            HTTP_X_FORWARDED_PORT="443",
            HTTP_X_FORWARDED_PROTO="https",
        )
        result = provider._prepare_request(request)

        assert result["https"] == "on"
        assert result["http_host"] == "proxy.acme.com"
        assert result["server_port"] == "443"
        assert result["script_name"] == "/auth/sso/acme/callback"

    def test_prepare_request_defaults_without_forwarded_headers(self):
        provider = self._make_provider()
        rf = RequestFactory()
        request = rf.get("/callback", SERVER_PORT="8000")
        result = provider._prepare_request(request)

        assert result["https"] == "off"
        assert result["server_port"] == "8000"

    # -- get_login_url -------------------------------------------------

    def test_get_login_url_returns_url_with_saml_request(self):
        provider = self._make_provider()

        mock_authn_request = MagicMock()
        mock_authn_request.get_request.return_value = "base64EncodedRequest=="

        with (
            patch(
                "django_matt.auth.sso.providers.saml.OneLogin_Saml2_AuthnRequest",
                return_value=mock_authn_request,
            ),
            patch(
                "django_matt.auth.sso.providers.saml.OneLogin_Saml2_Settings",
            ),
        ):
            url = provider.get_login_url()

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert parsed.netloc == "idp.acme.com"
        assert parsed.path == "/sso"
        assert "SAMLRequest" in params
        assert "RelayState" in params

    # -- get_logout_url ------------------------------------------------

    def test_get_logout_url_with_slo(self):
        provider = self._make_provider()
        url = provider.get_logout_url(relay_state="https://app.acme.com")
        assert url is not None
        assert "idp.acme.com/slo" in url
        assert "RelayState" in url

    def test_get_logout_url_none_without_slo(self):
        conn = _make_mock_connection(provider_type="saml", idp_slo_url="")
        provider = self._make_provider(connection=conn)
        assert provider.get_logout_url() is None

    # -- inactive connection -------------------------------------------

    def test_get_login_url_inactive_raises(self):
        conn = _make_mock_connection(provider_type="saml", is_active=False)
        provider = self._make_provider(connection=conn)
        with pytest.raises(SSOConfigError, match="not active"):
            provider.get_login_url()


# ===================================================================
# Model Tests (require DB)
# ===================================================================


@pytest.mark.django_db
class TestSSOConnectionModel:
    """Tests for the SSOConnection database model."""

    def test_create_sso_connection(self):
        conn = SSOConnection.objects.create(
            organization_id="org-1",
            provider_type="oidc",
            name="Test OIDC",
            client_id="cid",
            client_secret="csec",
            authorization_url="https://idp.test/authorize",
            token_url="https://idp.test/token",
            domains=["test.com"],
        )
        assert conn.pk is not None
        assert conn.is_active is True
        assert str(conn) == "org-1 - oidc"

    def test_get_for_organization(self):
        SSOConnection.objects.create(
            organization_id="org-find",
            provider_type="saml",
            idp_entity_id="https://idp.test",
            idp_sso_url="https://idp.test/sso",
            idp_certificate="cert",
        )
        found = SSOConnection.get_for_organization("org-find")
        assert found is not None
        assert found.organization_id == "org-find"

    def test_get_for_organization_not_found(self):
        assert SSOConnection.get_for_organization("nonexistent") is None

    def test_get_for_organization_inactive_excluded(self):
        SSOConnection.objects.create(
            organization_id="org-inactive",
            provider_type="saml",
            is_active=False,
        )
        assert SSOConnection.get_for_organization("org-inactive") is None

    def test_get_for_domain(self):
        SSOConnection.objects.create(
            organization_id="org-domain",
            provider_type="oidc",
            domains=["example.com", "example.org"],
        )
        found = SSOConnection.get_for_domain("example.com")
        assert found is not None
        assert found.organization_id == "org-domain"

    def test_get_for_domain_case_insensitive(self):
        SSOConnection.objects.create(
            organization_id="org-case",
            provider_type="oidc",
            domains=["CaseDomain.COM"],
        )
        found = SSOConnection.get_for_domain("casedomain.com")
        assert found is not None

    def test_get_for_domain_not_found(self):
        assert SSOConnection.get_for_domain("no-such-domain.io") is None

    def test_organization_id_unique(self):
        SSOConnection.objects.create(
            organization_id="org-unique",
            provider_type="oidc",
        )
        with pytest.raises(Exception):
            SSOConnection.objects.create(
                organization_id="org-unique",
                provider_type="saml",
            )


@pytest.mark.django_db
class TestSSOUserLinkModel:
    """Tests for the SSOUserLink database model."""

    @pytest.fixture
    def connection(self):
        return SSOConnection.objects.create(
            organization_id="link-org",
            provider_type="oidc",
        )

    @pytest.fixture
    def user(self):
        return User.objects.create_user(
            username="sso-user",
            email="sso@test.com",
            password="pass123",
        )

    def test_create_user_link(self, connection, user):
        link = SSOUserLink.objects.create(
            user=user,
            connection=connection,
            idp_user_id="idp-u-1",
            idp_email="sso@test.com",
            last_attributes={"groups": ["eng"]},
        )
        assert link.pk is not None
        assert str(link) == f"{user} - {connection}"

    def test_get_user(self, connection, user):
        SSOUserLink.objects.create(
            user=user,
            connection=connection,
            idp_user_id="idp-u-find",
        )
        found = SSOUserLink.get_user(connection, "idp-u-find")
        assert found is not None
        assert found.pk == user.pk

    def test_get_user_not_found(self, connection):
        assert SSOUserLink.get_user(connection, "nonexistent") is None

    def test_unique_constraint(self, connection, user):
        SSOUserLink.objects.create(
            user=user,
            connection=connection,
            idp_user_id="idp-u-dup",
        )
        user2 = User.objects.create_user(username="sso-user-2", password="pass")
        with pytest.raises(Exception):
            SSOUserLink.objects.create(
                user=user2,
                connection=connection,
                idp_user_id="idp-u-dup",
            )


# ===================================================================
# OIDC End-to-End Integration Tests
# ===================================================================


@pytest.mark.django_db(transaction=True)
class TestOIDCIntegration:
    """End-to-end integration tests for the OIDC SSO flow (HTTP mocked)."""

    @pytest.fixture
    def oidc_connection(self):
        """Create a real OIDC SSOConnection in the DB."""
        return SSOConnection.objects.create(
            organization_id="oidc-org",
            provider_type="oidc",
            name="Test OIDC Provider",
            client_id="oidc-client-123",
            client_secret="oidc-secret-456",
            authorization_url="https://idp.example.com/authorize",
            token_url="https://idp.example.com/token",
            userinfo_url="https://idp.example.com/userinfo",
            domains=["oidctest.com"],
            is_active=True,
        )

    @pytest.fixture
    def sso_cfg(self):
        return _make_sso_config()

    @pytest.mark.asyncio
    async def test_login_returns_oidc_authorization_url(self, oidc_connection, sso_cfg):
        """SSOController.login returns a login_url pointing to the OIDC IdP."""
        from urllib.parse import parse_qs, urlparse

        from django.test import RequestFactory as RF

        from django_matt.auth.sso.controllers import SSOController

        request = RF().post("/auth/sso/oidc-org/login")

        with (
            patch("django_matt.auth.sso.controllers.get_sso_config", return_value=sso_cfg),
            patch("django_matt.auth.sso.config.get_sso_config", return_value=sso_cfg),
        ):
            response = await SSOController.login(request, org_id="oidc-org")

        assert response.organization_id == "oidc-org"
        assert response.provider_type == "oidc"
        assert "idp.example.com" in response.login_url

        parsed = urlparse(response.login_url)
        params = parse_qs(parsed.query)
        assert params["client_id"] == ["oidc-client-123"]
        assert params["response_type"] == ["code"]
        assert "state" in params
        assert "nonce" in params
        assert "code_challenge" in params

    @pytest.mark.asyncio
    async def test_callback_creates_user_and_links_sso(self, oidc_connection, sso_cfg):
        """Full OIDC callback: process code -> map user attributes -> create user -> JWT tokens."""
        from django.core.cache import cache as django_cache
        from django.test import RequestFactory as RF

        from django_matt.auth.sso.controllers import SSOController
        from django_matt.auth.sso.models import SSOUserLink
        from django_matt.auth.sso.providers.oidc import OIDCProvider

        # Prepare state, PKCE and nonce in cache (as login would)
        with patch("django_matt.auth.sso.config.get_sso_config", return_value=sso_cfg):
            provider = OIDCProvider(oidc_connection)
            state = provider.generate_state()
            code_verifier = "test-verifier-xyz"
            nonce = "test-nonce-abc"
            django_cache.set(f"sso_state:pkce:{state}", code_verifier, 600)
            django_cache.set(f"sso_state:nonce:{state}", nonce, 600)

        # Mock the OIDC token endpoint
        id_payload = {
            "sub": "oidc-user-001",
            "email": "oidcuser@oidctest.com",
            "email_verified": True,
            "name": "OIDC User",
            "given_name": "OIDC",
            "family_name": "User",
            "nonce": nonce,
        }

        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {
            "access_token": "oidc-at",
            "token_type": "Bearer",
            # No id_token — force fallback to userinfo endpoint
        }

        userinfo_response = MagicMock()
        userinfo_response.status_code = 200
        userinfo_response.json.return_value = id_payload

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=token_response)
        mock_client.get = AsyncMock(return_value=userinfo_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        request = RF().get(
            "/auth/sso/oidc-org/callback",
            {"code": "oidc-auth-code", "state": state},
        )

        with (
            patch("django_matt.auth.sso.controllers.get_sso_config", return_value=sso_cfg),
            patch("django_matt.auth.sso.config.get_sso_config", return_value=sso_cfg),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            response = await SSOController.callback(request, org_id="oidc-org")

        assert response.success is True
        assert response.organization_id == "oidc-org"
        assert response.access_token is not None
        assert response.refresh_token is not None

        # Verify SSOUserLink was created
        link = await SSOUserLink.objects.aget(
            connection=oidc_connection,
            idp_user_id="oidc-user-001",
        )
        assert link is not None
        assert link.idp_email == "oidcuser@oidctest.com"

    @pytest.mark.asyncio
    async def test_callback_links_existing_user_by_email(self, oidc_connection, sso_cfg):
        """OIDC callback links to existing user when email matches."""
        from django.core.cache import cache as django_cache
        from django.test import RequestFactory as RF

        from django_matt.auth.sso.controllers import SSOController
        from django_matt.auth.sso.providers.oidc import OIDCProvider

        # Pre-create user
        existing_user = await User.objects.acreate_user(
            username="existing_oidc",
            email="existing@oidctest.com",
            password="pass",
        )

        with patch("django_matt.auth.sso.config.get_sso_config", return_value=sso_cfg):
            provider = OIDCProvider(oidc_connection)
            state = provider.generate_state()
            nonce = "nonce-link"
            django_cache.set(f"sso_state:pkce:{state}", "verifier", 600)
            django_cache.set(f"sso_state:nonce:{state}", nonce, 600)

        userinfo_response = MagicMock()
        userinfo_response.status_code = 200
        userinfo_response.json.return_value = {
            "sub": "oidc-user-existing",
            "email": "existing@oidctest.com",
            "email_verified": True,
            "name": "Existing User",
            "nonce": nonce,
        }

        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {"access_token": "at"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=token_response)
        mock_client.get = AsyncMock(return_value=userinfo_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        request = RF().get("/auth/sso/oidc-org/callback", {"code": "c", "state": state})

        with (
            patch("django_matt.auth.sso.controllers.get_sso_config", return_value=sso_cfg),
            patch("django_matt.auth.sso.config.get_sso_config", return_value=sso_cfg),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            response = await SSOController.callback(request, org_id="oidc-org")

        # Linked to existing user, not created
        assert response.created is False
        assert response.user_id == existing_user.pk

    @pytest.mark.asyncio
    async def test_domain_check_returns_sso_enabled(self, oidc_connection, sso_cfg):
        """check_domain returns sso_enabled=True for a domain with SSO configured."""
        from django.test import RequestFactory as RF

        from django_matt.auth.sso.controllers import SSOController
        from django_matt.auth.sso.schemas import SSODomainCheckRequest

        request = RF().post("/auth/sso/check")
        data = SSODomainCheckRequest(email="user@oidctest.com")

        with patch("django_matt.auth.sso.controllers.get_sso_config", return_value=sso_cfg):
            response = await SSOController.check_domain(request, data=data)

        assert response.sso_enabled is True
        assert response.organization_id == "oidc-org"
        assert response.provider_type == "oidc"

    @pytest.mark.asyncio
    async def test_domain_check_returns_sso_disabled_for_unknown(self, oidc_connection, sso_cfg):
        """check_domain returns sso_enabled=False for domain without SSO."""
        from django.test import RequestFactory as RF

        from django_matt.auth.sso.controllers import SSOController
        from django_matt.auth.sso.schemas import SSODomainCheckRequest

        request = RF().post("/auth/sso/check")
        data = SSODomainCheckRequest(email="user@unregistered-domain.io")

        with patch("django_matt.auth.sso.controllers.get_sso_config", return_value=sso_cfg):
            response = await SSOController.check_domain(request, data=data)

        assert response.sso_enabled is False
