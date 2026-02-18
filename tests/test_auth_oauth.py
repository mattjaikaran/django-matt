"""Tests for OAuth authentication providers, config, model, and registry."""
from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from django_matt.auth.oauth.config import (
    OAuthConfig,
    OAuthProviderConfig,
    get_oauth_config,
    reset_oauth_config,
)
from django_matt.auth.oauth.models import OAuthConnection
from django_matt.auth.oauth.providers import (
    PROVIDERS,
    get_provider,
    get_provider_instance,
)
from django_matt.auth.oauth.providers.apple import AppleOAuthProvider
from django_matt.auth.oauth.providers.base import (
    OAuthAuthenticationError,
    OAuthConfigError,
    OAuthToken,
    OAuthUserInfo,
    OAuthUserInfoError,
)
from django_matt.auth.oauth.providers.github import GitHubOAuthProvider
from django_matt.auth.oauth.providers.google import GoogleOAuthProvider
from django_matt.auth.oauth.providers.microsoft import MicrosoftOAuthProvider

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_oauth_config(**overrides) -> OAuthConfig:
    """Build an OAuthConfig with sensible test defaults."""
    defaults = dict(
        redirect_uri_base="https://example.com",
        google=OAuthProviderConfig(
            client_id="google-id",
            client_secret="google-secret",
            scopes=["openid", "email", "profile"],
        ),
        github=OAuthProviderConfig(
            client_id="github-id",
            client_secret="github-secret",
            scopes=["user:email", "read:user"],
        ),
        apple=OAuthProviderConfig(
            client_id="com.example.app",
            client_secret="apple-secret",
            scopes=["name", "email"],
            extra={
                "team_id": "TEAM123",
                "key_id": "KEY123",
                "private_key": "-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----",
            },
        ),
        microsoft=OAuthProviderConfig(
            client_id="ms-id",
            client_secret="ms-secret",
            scopes=["openid", "email", "profile", "User.Read"],
            extra={"tenant": "my-tenant-id"},
        ),
    )
    defaults.update(overrides)
    return OAuthConfig(**defaults)


def _make_id_token(payload: dict) -> str:
    """Create a fake JWT id_token (header.payload.signature) with given payload."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256"}).encode()).rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(b"fakesig").rstrip(b"=").decode()
    return f"{header}.{body}.{sig}"


def _patch_config(config: OAuthConfig | None = None):
    """Return a patch context manager that overrides get_oauth_config."""
    if config is None:
        config = _make_oauth_config()
    return patch("django_matt.auth.oauth.config.get_oauth_config", return_value=config)


# ---------------------------------------------------------------------------
# Google provider
# ---------------------------------------------------------------------------


class TestGoogleOAuthProvider:
    """Tests for GoogleOAuthProvider."""

    def test_get_user_info(self):
        """Google get_user_info parses standard OIDC claims."""
        with _patch_config():
            provider = GoogleOAuthProvider()

        data = {
            "sub": "112233",
            "email": "alice@gmail.com",
            "email_verified": True,
            "name": "Alice Smith",
            "given_name": "Alice",
            "family_name": "Smith",
            "picture": "https://lh3.google.com/photo",
            "locale": "en",
        }
        info = provider.get_user_info(data)
        assert info.provider == "google"
        assert info.provider_user_id == "112233"
        assert info.email == "alice@gmail.com"
        assert info.email_verified is True
        assert info.first_name == "Alice"
        assert info.last_name == "Smith"
        assert info.picture == "https://lh3.google.com/photo"
        assert info.locale == "en"
        assert info.raw is data

    def test_get_user_info_fallback_id(self):
        """Google falls back to 'id' when 'sub' is absent."""
        with _patch_config():
            provider = GoogleOAuthProvider()

        info = provider.get_user_info({"id": "99"})
        assert info.provider_user_id == "99"

    def test_get_authorization_url(self):
        """Google auth URL includes access_type=offline and prompt=consent."""
        with _patch_config():
            provider = GoogleOAuthProvider()

        url, state = provider.get_authorization_url(state="test-state")
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert "accounts.google.com" in parsed.netloc
        assert params["client_id"] == ["google-id"]
        assert params["response_type"] == ["code"]
        assert params["access_type"] == ["offline"]
        assert params["prompt"] == ["consent"]
        assert params["state"] == ["test-state"]
        assert "openid" in params["scope"][0]

    @pytest.mark.asyncio
    async def test_exchange_code(self):
        """Google exchange_code sends correct POST and returns OAuthToken."""
        with _patch_config():
            provider = GoogleOAuthProvider()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "goog-access",
            "token_type": "Bearer",
            "refresh_token": "goog-refresh",
            "expires_in": 3600,
            "scope": "openid email profile",
            "id_token": "goog-id-token",
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            token = await provider.exchange_code("auth-code-123")

        assert token.access_token == "goog-access"
        assert token.refresh_token == "goog-refresh"
        assert token.expires_in == 3600
        assert token.id_token == "goog-id-token"

        # Verify the POST was called with the token URL
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://oauth2.googleapis.com/token"

    @pytest.mark.asyncio
    async def test_exchange_code_failure(self):
        """exchange_code raises OAuthAuthenticationError on non-200."""
        with _patch_config():
            provider = GoogleOAuthProvider()

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Code expired",
        }
        mock_response.text = "Code expired"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(OAuthAuthenticationError, match="Code expired"):
                await provider.exchange_code("bad-code")

    @pytest.mark.asyncio
    async def test_fetch_user_info_via_id_token(self):
        """OIDC providers parse user info from id_token without HTTP call."""
        with _patch_config():
            provider = GoogleOAuthProvider()

        payload = {
            "sub": "id-from-token",
            "email": "token@example.com",
            "email_verified": True,
            "name": "Token User",
            "given_name": "Token",
            "family_name": "User",
        }
        id_token = _make_id_token(payload)
        token = OAuthToken(access_token="acc", id_token=id_token)

        info = await provider.fetch_user_info(token)
        assert info.provider_user_id == "id-from-token"
        assert info.email == "token@example.com"


# ---------------------------------------------------------------------------
# GitHub provider
# ---------------------------------------------------------------------------


class TestGitHubOAuthProvider:
    """Tests for GitHubOAuthProvider."""

    def test_get_user_info(self):
        """GitHub get_user_info splits name into first/last."""
        with _patch_config():
            provider = GitHubOAuthProvider()

        data = {
            "id": 42,
            "login": "octocat",
            "email": "octo@github.com",
            "email_verified": True,
            "name": "Octo Cat",
            "avatar_url": "https://avatars.github.com/42",
        }
        info = provider.get_user_info(data)
        assert info.provider == "github"
        assert info.provider_user_id == "42"
        assert info.email == "octo@github.com"
        assert info.first_name == "Octo"
        assert info.last_name == "Cat"
        assert info.picture == "https://avatars.github.com/42"
        assert info.locale is None

    def test_get_user_info_single_name(self):
        """GitHub handles single-word names (no last name)."""
        with _patch_config():
            provider = GitHubOAuthProvider()

        info = provider.get_user_info({"id": 1, "name": "Monalisa", "login": "mona"})
        assert info.first_name == "Monalisa"
        assert info.last_name == ""

    def test_get_user_info_no_name_uses_login(self):
        """GitHub falls back to login when name is empty."""
        with _patch_config():
            provider = GitHubOAuthProvider()

        info = provider.get_user_info({"id": 1, "login": "mona", "name": ""})
        assert info.name == "mona"

    @pytest.mark.asyncio
    async def test_fetch_user_info_private_email_fallback(self):
        """GitHub fetches private email from /user/emails when profile email is null."""
        with _patch_config():
            provider = GitHubOAuthProvider()

        user_response = MagicMock()
        user_response.status_code = 200
        user_response.json.return_value = {
            "id": 7,
            "login": "secretuser",
            "email": None,
            "name": "Secret User",
            "avatar_url": "https://avatars.github.com/7",
        }

        emails_response = MagicMock()
        emails_response.status_code = 200
        emails_response.json.return_value = [
            {"email": "secondary@example.com", "primary": False, "verified": True},
            {"email": "primary@example.com", "primary": True, "verified": True},
        ]

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[user_response, emails_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        token = OAuthToken(access_token="gh-token")
        with patch("httpx.AsyncClient", return_value=mock_client):
            info = await provider.fetch_user_info(token)

        assert info.email == "primary@example.com"
        assert info.email_verified is True

    @pytest.mark.asyncio
    async def test_fetch_user_info_verified_email_fallback(self):
        """GitHub falls back to first verified email when no primary email exists."""
        with _patch_config():
            provider = GitHubOAuthProvider()

        user_response = MagicMock()
        user_response.status_code = 200
        user_response.json.return_value = {
            "id": 8,
            "login": "noprimary",
            "email": None,
            "name": "No Primary",
        }

        emails_response = MagicMock()
        emails_response.status_code = 200
        emails_response.json.return_value = [
            {"email": "unverified@example.com", "primary": False, "verified": False},
            {"email": "verified@example.com", "primary": False, "verified": True},
        ]

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[user_response, emails_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        token = OAuthToken(access_token="gh-token")
        with patch("httpx.AsyncClient", return_value=mock_client):
            info = await provider.fetch_user_info(token)

        assert info.email == "verified@example.com"
        assert info.email_verified is True

    def test_get_authorization_url(self):
        """GitHub auth URL does not include OIDC-only params."""
        with _patch_config():
            provider = GitHubOAuthProvider()

        url, state = provider.get_authorization_url(state="gh-state")
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert "github.com" in parsed.netloc
        assert params["client_id"] == ["github-id"]
        assert "access_type" not in params  # Google-specific, not here


# ---------------------------------------------------------------------------
# Apple provider
# ---------------------------------------------------------------------------


class TestAppleOAuthProvider:
    """Tests for AppleOAuthProvider."""

    def test_get_user_info_email_verified_as_string(self):
        """Apple sends email_verified as 'true'/'false' string."""
        with _patch_config():
            provider = AppleOAuthProvider()

        data = {
            "sub": "apple-uid",
            "email": "user@privaterelay.appleid.com",
            "email_verified": "true",
        }
        info = provider.get_user_info(data)
        assert info.provider == "apple"
        assert info.provider_user_id == "apple-uid"
        assert info.email_verified is True

    def test_get_user_info_email_verified_false_string(self):
        """Apple email_verified='false' parses to False."""
        with _patch_config():
            provider = AppleOAuthProvider()

        info = provider.get_user_info({"sub": "uid", "email_verified": "false"})
        assert info.email_verified is False

    def test_get_user_info_with_user_name_data(self):
        """Apple first-login user data includes name from POST body."""
        with _patch_config():
            provider = AppleOAuthProvider()

        data = {
            "sub": "apple-first",
            "email": "first@apple.com",
            "email_verified": True,
            "user": {"name": {"firstName": "Jane", "lastName": "Doe"}},
        }
        info = provider.get_user_info(data)
        assert info.first_name == "Jane"
        assert info.last_name == "Doe"

    def test_get_user_info_user_as_json_string(self):
        """Apple user data can come as a JSON string."""
        with _patch_config():
            provider = AppleOAuthProvider()

        data = {
            "sub": "apple-str",
            "email": "str@apple.com",
            "email_verified": "true",
            "user": json.dumps({"name": {"firstName": "Json", "lastName": "Str"}}),
        }
        info = provider.get_user_info(data)
        assert info.first_name == "Json"
        assert info.last_name == "Str"

    def test_customize_auth_params_adds_response_mode(self):
        """Apple adds response_mode=form_post to authorization params."""
        with _patch_config():
            provider = AppleOAuthProvider()

        url, _ = provider.get_authorization_url(state="apple-state")
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert params["response_mode"] == ["form_post"]

    def test_generate_client_secret(self):
        """Apple _generate_client_secret calls encode_jwt with ES256."""
        with _patch_config():
            provider = AppleOAuthProvider()

        with patch("django_matt.auth.jwt_builtin.encode_jwt", return_value="fake-jwt") as mock_encode:
            secret = provider._generate_client_secret()

        assert secret == "fake-jwt"
        mock_encode.assert_called_once()
        call_kwargs = mock_encode.call_args
        # encode_jwt is called with positional/keyword args — check both styles
        assert call_kwargs.kwargs.get("algorithm") or call_kwargs[1].get("algorithm") == "ES256"
        payload = call_kwargs.kwargs.get("payload") or call_kwargs[1].get("payload")
        assert payload["iss"] == "TEAM123"
        assert payload["sub"] == "com.example.app"
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert headers["kid"] == "KEY123"

    def test_ensure_configured_missing_team_id(self):
        """Apple raises OAuthConfigError when team_id is missing."""
        config = _make_oauth_config(
            apple=OAuthProviderConfig(
                client_id="apple-id",
                client_secret="apple-secret",
                extra={"key_id": "K", "private_key": "pk"},
            ),
        )
        with _patch_config(config):
            provider = AppleOAuthProvider()

        with pytest.raises(OAuthConfigError, match="team_id"):
            provider._ensure_configured()

    def test_ensure_configured_missing_key_id(self):
        """Apple raises OAuthConfigError when key_id is missing."""
        config = _make_oauth_config(
            apple=OAuthProviderConfig(
                client_id="apple-id",
                client_secret="apple-secret",
                extra={"team_id": "T", "private_key": "pk"},
            ),
        )
        with _patch_config(config):
            provider = AppleOAuthProvider()

        with pytest.raises(OAuthConfigError, match="key_id"):
            provider._ensure_configured()


# ---------------------------------------------------------------------------
# Microsoft provider
# ---------------------------------------------------------------------------


class TestMicrosoftOAuthProvider:
    """Tests for MicrosoftOAuthProvider."""

    def test_tenant_from_extra_config(self):
        """Microsoft uses tenant from extra config."""
        with _patch_config():
            provider = MicrosoftOAuthProvider()

        assert provider.tenant == "my-tenant-id"

    def test_tenant_defaults_to_common(self):
        """Microsoft tenant defaults to 'common' when not set."""
        config = _make_oauth_config(
            microsoft=OAuthProviderConfig(
                client_id="ms-id",
                client_secret="ms-secret",
                extra={},
            ),
        )
        with _patch_config(config):
            provider = MicrosoftOAuthProvider()

        assert provider.tenant == "common"

    def test_tenant_aware_urls(self):
        """Microsoft authorization and token URLs include tenant."""
        with _patch_config():
            provider = MicrosoftOAuthProvider()

        assert "my-tenant-id" in provider.authorization_url
        assert "my-tenant-id" in provider.token_url
        assert provider.userinfo_url == "https://graph.microsoft.com/v1.0/me"

    def test_get_user_info_oidc_format(self):
        """Microsoft get_user_info handles OIDC response (sub, given_name, etc.)."""
        with _patch_config():
            provider = MicrosoftOAuthProvider()

        data = {
            "sub": "ms-oidc-id",
            "email": "user@outlook.com",
            "name": "Bob Jones",
            "given_name": "Bob",
            "family_name": "Jones",
            "locale": "en-US",
        }
        info = provider.get_user_info(data)
        assert info.provider == "microsoft"
        assert info.provider_user_id == "ms-oidc-id"
        assert info.email == "user@outlook.com"
        assert info.email_verified is True  # has @ in email
        assert info.first_name == "Bob"
        assert info.last_name == "Jones"

    def test_get_user_info_graph_api_format(self):
        """Microsoft get_user_info handles Graph API response (id, givenName, etc.)."""
        with _patch_config():
            provider = MicrosoftOAuthProvider()

        data = {
            "id": "ms-graph-id",
            "mail": "graph@contoso.com",
            "displayName": "Graph User",
            "givenName": "Graph",
            "surname": "User",
            "userPrincipalName": "graph@contoso.com",
        }
        info = provider.get_user_info(data)
        assert info.provider_user_id == "ms-graph-id"
        assert info.email == "graph@contoso.com"
        assert info.name == "Graph User"
        assert info.first_name == "Graph"
        assert info.last_name == "User"

    def test_get_user_info_oid_fallback(self):
        """Microsoft falls back to 'oid' for user ID."""
        with _patch_config():
            provider = MicrosoftOAuthProvider()

        info = provider.get_user_info({"oid": "oid-value"})
        assert info.provider_user_id == "oid-value"

    def test_get_authorization_url_includes_response_mode(self):
        """Microsoft adds response_mode=query to auth params."""
        with _patch_config():
            provider = MicrosoftOAuthProvider()

        url, _ = provider.get_authorization_url(state="ms-state")
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert params["response_mode"] == ["query"]
        assert "my-tenant-id" in parsed.path


# ---------------------------------------------------------------------------
# Base provider behavior
# ---------------------------------------------------------------------------


class TestOAuthProviderBase:
    """Tests for shared OAuthProvider base class functionality."""

    def test_ensure_configured_no_config(self):
        """Raises OAuthConfigError when provider is not configured."""
        config = _make_oauth_config(
            google=OAuthProviderConfig(client_id="", client_secret=""),
        )
        with _patch_config(config):
            provider = GoogleOAuthProvider()

        with pytest.raises(OAuthConfigError, match="not configured"):
            provider._ensure_configured()

    def test_ensure_configured_no_client_secret(self):
        """Raises OAuthConfigError when client_secret is missing."""
        config = _make_oauth_config(
            google=OAuthProviderConfig(client_id="id-only", client_secret=""),
        )
        # get_provider_config returns None when client_id is set but we need to
        # bypass that — set it manually
        with _patch_config(config):
            provider = GoogleOAuthProvider()
            # Force provider_config so _ensure_configured checks client_secret
            provider.provider_config = OAuthProviderConfig(client_id="id-only", client_secret="")

        with pytest.raises(OAuthConfigError, match="client_secret"):
            provider._ensure_configured()

    def test_get_redirect_uri(self):
        """Redirect URI is built from config base + provider name."""
        with _patch_config():
            provider = GoogleOAuthProvider()

        assert provider.get_redirect_uri() == "https://example.com/auth/oauth/google/callback"

    def test_generate_and_verify_state(self):
        """State generation and verification round-trips through cache."""
        with _patch_config():
            provider = GoogleOAuthProvider()

        state = provider.generate_state(extra_data={"next": "/dashboard"})
        assert isinstance(state, str)
        assert len(state) > 20

        data = provider.verify_state(state)
        assert data is not None
        assert data["provider"] == "google"
        assert data["next"] == "/dashboard"

    def test_verify_state_one_time_use(self):
        """State is deleted after first verification (one-time use)."""
        with _patch_config():
            provider = GoogleOAuthProvider()

        state = provider.generate_state()
        assert provider.verify_state(state) is not None
        assert provider.verify_state(state) is None

    def test_verify_state_invalid(self):
        """Invalid state returns None."""
        with _patch_config():
            provider = GoogleOAuthProvider()

        assert provider.verify_state("nonexistent-state") is None

    def test_parse_id_token_invalid_format(self):
        """_parse_id_token raises OAuthUserInfoError for invalid JWT."""
        with _patch_config():
            provider = GoogleOAuthProvider()

        with pytest.raises(OAuthUserInfoError, match="Invalid id_token"):
            provider._parse_id_token("not.a.valid.jwt.token")

    @pytest.mark.asyncio
    async def test_fetch_user_info_no_userinfo_url(self):
        """fetch_user_info raises when no userinfo_url and no id_token."""
        with _patch_config():
            provider = AppleOAuthProvider()

        token = OAuthToken(access_token="acc")  # no id_token
        with pytest.raises(OAuthUserInfoError, match="No userinfo URL"):
            await provider.fetch_user_info(token)


# ---------------------------------------------------------------------------
# OAuthConnection model
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOAuthConnectionModel:
    """Tests for OAuthConnection Django model."""

    def test_create_connection(self):
        """Can create an OAuth connection for a user."""
        user = User.objects.create_user(username="oauth_user", password="pass")
        conn = OAuthConnection.objects.create(
            user=user,
            provider="google",
            provider_user_id="goog-123",
            email="oauth@example.com",
            name="OAuth User",
        )
        assert conn.pk is not None
        assert str(conn) == f"{user} - google"
        assert conn.provider == "google"
        assert conn.provider_user_id == "goog-123"

    def test_unique_together_constraint(self):
        """Cannot create two connections for same user + provider."""
        user = User.objects.create_user(username="unique_user", password="pass")
        OAuthConnection.objects.create(
            user=user, provider="github", provider_user_id="gh-1"
        )
        with pytest.raises(IntegrityError):
            OAuthConnection.objects.create(
                user=user, provider="github", provider_user_id="gh-2"
            )

    def test_get_or_none_found(self):
        """get_or_none returns the connection when it exists."""
        user = User.objects.create_user(username="found_user", password="pass")
        OAuthConnection.objects.create(
            user=user, provider="google", provider_user_id="goog-found"
        )
        result = OAuthConnection.get_or_none("google", "goog-found")
        assert result is not None
        assert result.user == user

    def test_get_or_none_not_found(self):
        """get_or_none returns None when no match."""
        result = OAuthConnection.get_or_none("google", "nonexistent-id")
        assert result is None

    def test_get_for_user_found(self):
        """get_for_user returns the connection for a user+provider pair."""
        user = User.objects.create_user(username="for_user", password="pass")
        OAuthConnection.objects.create(
            user=user, provider="microsoft", provider_user_id="ms-1"
        )
        result = OAuthConnection.get_for_user(user, "microsoft")
        assert result is not None
        assert result.provider_user_id == "ms-1"

    def test_get_for_user_not_found(self):
        """get_for_user returns None when user has no connection for that provider."""
        user = User.objects.create_user(username="no_conn_user", password="pass")
        result = OAuthConnection.get_for_user(user, "apple")
        assert result is None

    def test_multiple_providers_per_user(self):
        """A user can have connections to multiple providers."""
        user = User.objects.create_user(username="multi_user", password="pass")
        OAuthConnection.objects.create(user=user, provider="google", provider_user_id="g1")
        OAuthConnection.objects.create(user=user, provider="github", provider_user_id="gh1")

        assert OAuthConnection.objects.filter(user=user).count() == 2
        assert OAuthConnection.get_for_user(user, "google") is not None
        assert OAuthConnection.get_for_user(user, "github") is not None


# ---------------------------------------------------------------------------
# OAuthConfig
# ---------------------------------------------------------------------------


class TestOAuthConfig:
    """Tests for OAuthConfig and related config functions."""

    def test_from_settings(self):
        """OAuthConfig.from_settings loads from DJANGO_MATT_OAUTH setting."""
        settings_dict = {
            "REDIRECT_URI_BASE": "https://myapp.com",
            "SUCCESS_REDIRECT": "/home",
            "AUTO_CREATE_USER": False,
            "GOOGLE": {
                "client_id": "gid",
                "client_secret": "gsecret",
            },
        }
        with patch("django_matt.auth.oauth.config.settings") as mock_settings:
            mock_settings.DJANGO_MATT_OAUTH = settings_dict
            config = OAuthConfig.from_settings()

        assert config.redirect_uri_base == "https://myapp.com"
        assert config.success_redirect == "/home"
        assert config.auto_create_user is False
        assert config.google.client_id == "gid"
        assert config.google.client_secret == "gsecret"

    def test_get_provider_config_enabled(self):
        """get_provider_config returns config for enabled provider with client_id."""
        config = _make_oauth_config()
        result = config.get_provider_config("google")
        assert result is not None
        assert result.client_id == "google-id"

    def test_get_provider_config_disabled(self):
        """get_provider_config returns None for disabled provider."""
        config = _make_oauth_config(
            google=OAuthProviderConfig(client_id="id", client_secret="sec", enabled=False),
        )
        assert config.get_provider_config("google") is None

    def test_get_provider_config_no_client_id(self):
        """get_provider_config returns None when client_id is empty."""
        config = _make_oauth_config(
            github=OAuthProviderConfig(client_id="", client_secret="sec"),
        )
        assert config.get_provider_config("github") is None

    def test_get_provider_config_unknown(self):
        """get_provider_config returns None for unknown provider name."""
        config = _make_oauth_config()
        assert config.get_provider_config("twitter") is None

    def test_get_enabled_providers(self):
        """get_enabled_providers returns names of providers with client_id + enabled."""
        config = _make_oauth_config(
            github=OAuthProviderConfig(client_id="", client_secret=""),
        )
        enabled = config.get_enabled_providers()
        assert "google" in enabled
        assert "apple" in enabled
        assert "microsoft" in enabled
        assert "github" not in enabled

    def test_get_oauth_config_singleton(self):
        """get_oauth_config caches the config instance."""
        reset_oauth_config()
        with patch("django_matt.auth.oauth.config.settings") as mock_settings:
            mock_settings.DJANGO_MATT_OAUTH = {
                "REDIRECT_URI_BASE": "https://test.com",
                "GOOGLE": {"client_id": "singleton-id", "client_secret": "s"},
            }
            c1 = get_oauth_config()
            c2 = get_oauth_config()

        assert c1 is c2
        assert c1.google.client_id == "singleton-id"
        reset_oauth_config()  # cleanup

    def test_reset_oauth_config(self):
        """reset_oauth_config clears the cached config."""
        reset_oauth_config()
        with patch("django_matt.auth.oauth.config.settings") as mock_settings:
            mock_settings.DJANGO_MATT_OAUTH = {
                "GOOGLE": {"client_id": "first", "client_secret": "s"},
            }
            c1 = get_oauth_config()

        reset_oauth_config()

        with patch("django_matt.auth.oauth.config.settings") as mock_settings:
            mock_settings.DJANGO_MATT_OAUTH = {
                "GOOGLE": {"client_id": "second", "client_secret": "s"},
            }
            c2 = get_oauth_config()

        assert c1.google.client_id == "first"
        assert c2.google.client_id == "second"
        reset_oauth_config()  # cleanup

    def test_validate_missing_redirect_uri(self):
        """validate reports error when redirect_uri_base is empty."""
        config = OAuthConfig(redirect_uri_base="")
        errors = config.validate()
        assert any("REDIRECT_URI_BASE" in e for e in errors)


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------


class TestProviderRegistry:
    """Tests for provider registry functions."""

    def test_providers_dict_contains_all(self):
        """PROVIDERS dict maps all four provider names to classes."""
        assert set(PROVIDERS.keys()) == {"google", "github", "apple", "microsoft"}
        assert PROVIDERS["google"] is GoogleOAuthProvider
        assert PROVIDERS["github"] is GitHubOAuthProvider
        assert PROVIDERS["apple"] is AppleOAuthProvider
        assert PROVIDERS["microsoft"] is MicrosoftOAuthProvider

    def test_get_provider_by_name(self):
        """get_provider returns the correct class."""
        assert get_provider("google") is GoogleOAuthProvider
        assert get_provider("GitHub") is GitHubOAuthProvider  # case-insensitive

    def test_get_provider_unknown(self):
        """get_provider returns None for unknown provider."""
        assert get_provider("twitter") is None

    def test_get_provider_instance(self):
        """get_provider_instance returns an instantiated provider."""
        with _patch_config():
            instance = get_provider_instance("google")

        assert instance is not None
        assert isinstance(instance, GoogleOAuthProvider)
        assert instance.name == "google"

    def test_get_provider_instance_unknown(self):
        """get_provider_instance returns None for unknown provider."""
        assert get_provider_instance("twitter") is None


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


class TestDataClasses:
    """Tests for OAuthToken and OAuthUserInfo dataclasses."""

    def test_oauth_token_defaults(self):
        """OAuthToken has sensible defaults."""
        token = OAuthToken(access_token="abc")
        assert token.access_token == "abc"
        assert token.token_type == "Bearer"
        assert token.refresh_token is None
        assert token.expires_in is None
        assert token.scope is None
        assert token.id_token is None
        assert token.raw is None

    def test_oauth_user_info_defaults(self):
        """OAuthUserInfo has sensible defaults."""
        info = OAuthUserInfo(provider="test", provider_user_id="123")
        assert info.email is None
        assert info.email_verified is False
        assert info.name is None
        assert info.first_name is None
        assert info.last_name is None
        assert info.picture is None
        assert info.locale is None
        assert info.raw is None


# ---------------------------------------------------------------------------
# Error classes
# ---------------------------------------------------------------------------


class TestOAuthErrors:
    """Tests for OAuth error hierarchy."""

    def test_oauth_error_message(self):
        """OAuthError stores message and error_code."""
        err = OAuthAuthenticationError("bad token", error_code="invalid_token")
        assert err.message == "bad token"
        assert err.error_code == "invalid_token"
        assert str(err) == "bad token"

    def test_error_hierarchy(self):
        """All OAuth errors inherit from OAuthError."""
        from django_matt.auth.oauth.providers.base import OAuthError

        assert issubclass(OAuthConfigError, OAuthError)
        assert issubclass(OAuthAuthenticationError, OAuthError)
        assert issubclass(OAuthUserInfoError, OAuthError)
