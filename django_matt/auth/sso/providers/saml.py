"""
SAML 2.0 SSO provider.

Supports SAML-based identity providers like:
- Okta (SAML app)
- Azure AD (SAML)
- OneLogin
- Any SAML 2.0 compliant IdP

Requires: pip install python3-saml
"""

from urllib.parse import urlencode

from django_matt.auth.sso.providers.base import (
    SSOAuthenticationError,
    SSOConfigError,
    SSOProvider,
    SSOUserInfo,
)

# Check for python3-saml
try:
    from onelogin.saml2.auth import OneLogin_Saml2_Auth
    from onelogin.saml2.settings import OneLogin_Saml2_Settings
    from onelogin.saml2.utils import OneLogin_Saml2_Utils

    HAS_SAML = True
except ImportError:
    HAS_SAML = False


class SAMLProvider(SSOProvider):
    """
    SAML 2.0 SSO provider.

    Uses python3-saml library for SAML processing.
    """

    provider_type = "saml"

    def _ensure_saml_installed(self):
        """Ensure python3-saml is installed."""
        if not HAS_SAML:
            raise SSOConfigError(
                "python3-saml is required for SAML SSO. Install with: pip install python3-saml"
            )

    def _get_saml_settings(self) -> dict:
        """
        Build SAML settings dict for python3-saml.

        Returns:
            Settings dictionary for OneLogin_Saml2_Auth
        """
        conn = self.connection

        if not conn.idp_entity_id:
            raise SSOConfigError("IdP Entity ID is required for SAML")
        if not conn.idp_sso_url:
            raise SSOConfigError("IdP SSO URL is required for SAML")
        if not conn.idp_certificate:
            raise SSOConfigError("IdP Certificate is required for SAML")

        # Get extra config with defaults
        extra = conn.extra_config or {}

        settings = {
            "strict": extra.get("strict", True),
            "debug": extra.get("debug", False),
            "sp": {
                "entityId": conn.get_sp_entity_id(),
                "assertionConsumerService": {
                    "url": conn.get_callback_url(),
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
                },
                "NameIDFormat": extra.get(
                    "name_id_format", "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
                ),
            },
            "idp": {
                "entityId": conn.idp_entity_id,
                "singleSignOnService": {
                    "url": conn.idp_sso_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
                },
                "x509cert": conn.idp_certificate,
            },
            "security": {
                "nameIdEncrypted": extra.get("name_id_encrypted", False),
                "authnRequestsSigned": extra.get("authn_requests_signed", False),
                "logoutRequestSigned": extra.get("logout_request_signed", False),
                "logoutResponseSigned": extra.get("logout_response_signed", False),
                "signMetadata": extra.get("sign_metadata", False),
                "wantMessagesSigned": extra.get("want_messages_signed", False),
                "wantAssertionsSigned": extra.get("want_assertions_signed", True),
                "wantAssertionsEncrypted": extra.get("want_assertions_encrypted", False),
                "wantNameIdEncrypted": extra.get("want_name_id_encrypted", False),
                "requestedAuthnContext": extra.get("requested_authn_context", False),
            },
        }

        # Add SLO if configured
        if conn.idp_slo_url:
            settings["idp"]["singleLogoutService"] = {
                "url": conn.idp_slo_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            }

        # Add SP private key and cert if configured (for signed requests)
        sp_private_key = extra.get("sp_private_key")
        sp_certificate = extra.get("sp_certificate")
        if sp_private_key and sp_certificate:
            settings["sp"]["privateKey"] = sp_private_key
            settings["sp"]["x509cert"] = sp_certificate

        return settings

    def _prepare_request(self, request) -> dict:
        """
        Prepare request data for python3-saml.

        Args:
            request: Django HTTP request

        Returns:
            Request dict for OneLogin_Saml2_Auth
        """
        # Get the server port
        if "HTTP_X_FORWARDED_PORT" in request.META:
            server_port = request.META["HTTP_X_FORWARDED_PORT"]
        else:
            server_port = request.META.get("SERVER_PORT", "443")

        # Get the server name/host
        if "HTTP_X_FORWARDED_HOST" in request.META:
            http_host = request.META["HTTP_X_FORWARDED_HOST"]
        else:
            http_host = request.META.get("HTTP_HOST", "")

        # Determine if HTTPS
        if "HTTP_X_FORWARDED_PROTO" in request.META:
            https = request.META["HTTP_X_FORWARDED_PROTO"] == "https"
        else:
            https = request.is_secure()

        return {
            "https": "on" if https else "off",
            "http_host": http_host,
            "server_port": server_port,
            "script_name": request.path,
            "get_data": request.GET.copy(),
            "post_data": request.POST.copy(),
            "query_string": request.META.get("QUERY_STRING", ""),
        }

    def get_login_url(self, relay_state: str | None = None) -> str:
        """
        Generate SAML authentication request URL.

        Args:
            relay_state: Optional relay state to pass through IdP

        Returns:
            URL to redirect user to IdP
        """
        self._ensure_saml_installed()
        self._validate_connection()

        settings = self._get_saml_settings()
        saml_settings = OneLogin_Saml2_Settings(settings)

        # Generate the state if not provided
        if relay_state is None:
            relay_state = self.generate_state()

        # Build the AuthnRequest URL
        authn_request = OneLogin_Saml2_Utils.deflate_and_base64_encode(
            saml_settings.get_sp_metadata()  # This gets the actual request
        )

        # For simplicity, construct the redirect URL manually
        # In production, you'd use OneLogin_Saml2_Auth.login()
        params = {
            "SAMLRequest": authn_request,
            "RelayState": relay_state,
        }

        return f"{self.connection.idp_sso_url}?{urlencode(params)}"

    async def process_callback(self, request) -> SSOUserInfo:
        """
        Process SAML response from IdP.

        Args:
            request: Django HTTP request with SAMLResponse

        Returns:
            Normalized SSOUserInfo

        Raises:
            SSOAuthenticationError: If SAML validation fails
        """
        self._ensure_saml_installed()
        self._validate_connection()

        # Check for SAMLResponse
        saml_response = request.POST.get("SAMLResponse")
        if not saml_response:
            raise SSOAuthenticationError("No SAMLResponse in request")

        # Verify relay state
        relay_state = request.POST.get("RelayState")
        if relay_state:
            state_data = self.verify_state(relay_state)
            if not state_data:
                raise SSOAuthenticationError("Invalid or expired relay state")

        try:
            # Initialize SAML auth
            settings = self._get_saml_settings()
            req_data = self._prepare_request(request)
            auth = OneLogin_Saml2_Auth(req_data, settings)

            # Process the response
            auth.process_response()

            # Check for errors
            errors = auth.get_errors()
            if errors:
                error_reason = auth.get_last_error_reason()
                raise SSOAuthenticationError(
                    f"SAML validation failed: {', '.join(errors)}. {error_reason}"
                )

            if not auth.is_authenticated():
                raise SSOAuthenticationError("SAML authentication failed")

            # Get user attributes
            name_id = auth.get_nameid()
            attributes = auth.get_attributes()

            # Add NameID to attributes for mapping
            attributes["nameId"] = name_id
            attributes["NameID"] = name_id

            # Map attributes to user info
            user_info = self.map_attributes(attributes)

            # Ensure we have an IdP user ID
            if not user_info.idp_user_id:
                user_info.idp_user_id = name_id

            return user_info

        except SSOAuthenticationError:
            raise
        except Exception as e:
            raise SSOAuthenticationError(f"SAML processing error: {e!s}")

    def get_metadata(self) -> str:
        """
        Generate SP metadata XML.

        Returns:
            SAML SP metadata XML string
        """
        self._ensure_saml_installed()

        settings = self._get_saml_settings()
        saml_settings = OneLogin_Saml2_Settings(settings)

        metadata = saml_settings.get_sp_metadata()
        errors = saml_settings.validate_metadata(metadata)

        if errors:
            raise SSOConfigError(f"Invalid SP metadata: {', '.join(errors)}")

        return metadata

    def get_logout_url(self, relay_state: str | None = None) -> str | None:
        """
        Generate SAML logout request URL.

        Args:
            relay_state: Optional relay state

        Returns:
            Logout URL, or None if SLO not configured
        """
        if not self.connection.idp_slo_url:
            return None

        self._ensure_saml_installed()

        # For single logout, we'd need the current session's NameID and SessionIndex
        # This is a simplified implementation
        params = {}
        if relay_state:
            params["RelayState"] = relay_state

        if params:
            return f"{self.connection.idp_slo_url}?{urlencode(params)}"
        return self.connection.idp_slo_url
