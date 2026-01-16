"""
Base SSO provider class.
"""

import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from django.core.cache import cache


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class SSOUserInfo:
    """Normalized user info from SSO provider."""

    idp_user_id: str  # NameID (SAML) or sub (OIDC)
    email: str | None = None
    email_verified: bool = False
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    groups: list[str] | None = None  # Group memberships from IdP
    roles: list[str] | None = None  # Roles from IdP
    raw_attributes: dict[str, Any] | None = None


# =============================================================================
# Exceptions
# =============================================================================


class SSOError(Exception):
    """Base SSO error."""

    def __init__(self, message: str, error_code: str | None = None):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class SSOConfigError(SSOError):
    """SSO configuration error."""

    pass


class SSOAuthenticationError(SSOError):
    """SSO authentication failed."""

    pass


# =============================================================================
# Base Provider
# =============================================================================


class SSOProvider(ABC):
    """
    Base class for SSO providers.

    Subclasses must implement:
    - get_login_url(): Generate URL to redirect user to IdP
    - process_callback(): Process the callback from IdP
    """

    provider_type: str = ""

    def __init__(self, connection):
        """
        Initialize provider with an SSOConnection.

        Args:
            connection: SSOConnection model instance
        """
        from django_matt.auth.sso.config import get_sso_config

        self.connection = connection
        self.config = get_sso_config()

    def _validate_connection(self):
        """Validate that the connection is properly configured."""
        if not self.connection.is_active:
            raise SSOConfigError("SSO connection is not active")

    def generate_state(self, extra_data: dict | None = None) -> str:
        """
        Generate a secure state/relay state parameter.

        Args:
            extra_data: Optional extra data to store with state

        Returns:
            The state token
        """
        state = secrets.token_urlsafe(32)
        cache_key = f"{self.config.state_cache_prefix}:{state}"

        data = {
            "organization_id": self.connection.organization_id,
            "provider_type": self.connection.provider_type,
        }
        if extra_data:
            data.update(extra_data)

        cache.set(cache_key, data, self.config.state_timeout)
        return state

    def verify_state(self, state: str) -> dict | None:
        """
        Verify a state parameter and return stored data.

        Args:
            state: The state token to verify

        Returns:
            The stored data, or None if invalid/expired
        """
        cache_key = f"{self.config.state_cache_prefix}:{state}"
        data = cache.get(cache_key)

        if data:
            cache.delete(cache_key)  # One-time use

        return data

    def get_callback_url(self) -> str:
        """Get the callback URL for this connection."""
        return self.connection.get_callback_url()

    def map_attributes(self, raw_attributes: dict) -> SSOUserInfo:
        """
        Map IdP attributes to SSOUserInfo using the connection's attribute mapping.

        Args:
            raw_attributes: Raw attributes from IdP

        Returns:
            Normalized SSOUserInfo
        """
        mapping = self.connection.attribute_mapping or {}

        # Default attribute names (common across providers)
        default_mapping = {
            "idp_user_id": ["sub", "nameId", "NameID", "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier"],
            "email": ["email", "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress", "mail"],
            "name": ["name", "displayName", "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name"],
            "first_name": ["given_name", "firstName", "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname"],
            "last_name": ["family_name", "lastName", "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname"],
            "groups": ["groups", "memberOf", "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups"],
            "roles": ["roles", "role", "http://schemas.microsoft.com/ws/2008/06/identity/claims/role"],
        }

        def get_attribute(field: str) -> Any:
            # First check custom mapping
            if field in mapping:
                attr_name = mapping[field]
                if attr_name in raw_attributes:
                    return raw_attributes[attr_name]

            # Then check defaults
            for attr_name in default_mapping.get(field, []):
                if attr_name in raw_attributes:
                    value = raw_attributes[attr_name]
                    # Handle list values (take first)
                    if isinstance(value, list) and len(value) > 0:
                        return value[0] if field not in ["groups", "roles"] else value
                    return value

            return None

        email = get_attribute("email")
        # Check for email_verified attribute
        email_verified = raw_attributes.get("email_verified", False)
        if isinstance(email_verified, str):
            email_verified = email_verified.lower() == "true"

        return SSOUserInfo(
            idp_user_id=get_attribute("idp_user_id") or "",
            email=email,
            email_verified=email_verified,
            name=get_attribute("name"),
            first_name=get_attribute("first_name"),
            last_name=get_attribute("last_name"),
            groups=get_attribute("groups"),
            roles=get_attribute("roles"),
            raw_attributes=raw_attributes,
        )

    @abstractmethod
    def get_login_url(self, relay_state: str | None = None) -> str:
        """
        Generate the URL to redirect the user to the IdP.

        Args:
            relay_state: Optional state to pass through the IdP

        Returns:
            The login URL
        """
        pass

    @abstractmethod
    async def process_callback(self, request) -> SSOUserInfo:
        """
        Process the callback from the IdP.

        Args:
            request: The HTTP request with the callback data

        Returns:
            Normalized SSOUserInfo

        Raises:
            SSOAuthenticationError: If authentication fails
        """
        pass

    def get_metadata(self) -> str | None:
        """
        Generate SP metadata (for SAML).

        Returns:
            XML metadata string, or None if not applicable
        """
        return None

    def get_logout_url(self, relay_state: str | None = None) -> str | None:
        """
        Generate the URL for single logout.

        Args:
            relay_state: Optional state to pass through

        Returns:
            The logout URL, or None if SLO not supported
        """
        return None
