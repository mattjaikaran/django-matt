from __future__ import annotations

import logging
from typing import Any

import jwt
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse

from django_matt_clerk_auth.config import get_clerk_config
from django_matt_clerk_auth.sync import sync_clerk_user

logger = logging.getLogger("django_matt.plugins.clerk")

_jwks_client: jwt.PyJWKClient | None = None


def _get_jwks_client() -> jwt.PyJWKClient:
    global _jwks_client
    if _jwks_client is not None:
        return _jwks_client

    config = get_clerk_config()
    jwks_url = config.jwks_url
    if not jwks_url and config.publishable_key:
        # derive JWKS URL from publishable key
        # pk_test_xxx... or pk_live_xxx...
        parts = config.publishable_key.split("_")
        if len(parts) >= 3:
            domain = parts[2]
            jwks_url = f"https://{domain}.clerk.accounts.dev/.well-known/jwks.json"

    if not jwks_url:
        raise ValueError(
            "Cannot determine JWKS URL. Set MATT_CLERK.JWKS_URL or "
            "MATT_CLERK.PUBLISHABLE_KEY."
        )

    _jwks_client = jwt.PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


def reset_jwks_client() -> None:
    global _jwks_client
    _jwks_client = None


class ClerkAuthMiddleware:
    """Django middleware that verifies Clerk session JWTs.

    Extracts the JWT from the Authorization header, verifies it using
    Clerk's JWKS endpoint, and sets request.user to the corresponding
    Django user (creating one if AUTO_CREATE_USER is enabled).
    """

    def __init__(self, get_response: Any) -> None:
        self.get_response = get_response

    async def __call__(self, request: HttpRequest) -> HttpResponse:
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            request.user = AnonymousUser()  # type: ignore[assignment]
            return await self.get_response(request)

        token = auth_header[7:]  # strip "Bearer "
        claims = await self._verify_token(token)

        if claims is None:
            request.user = AnonymousUser()  # type: ignore[assignment]
            return await self.get_response(request)

        config = get_clerk_config()
        if config.auto_create_user:
            user = await sync_clerk_user(claims)
            request.user = user  # type: ignore[assignment]
        else:
            # attach claims without user sync
            request.clerk_claims = claims  # type: ignore[attr-defined]
            User = get_user_model()  # noqa: N806
            clerk_id = claims.get("sub", "")
            try:
                from asgiref.sync import sync_to_async

                user = await sync_to_async(User.objects.get)(username=clerk_id)
                request.user = user  # type: ignore[assignment]
            except User.DoesNotExist:
                request.user = AnonymousUser()  # type: ignore[assignment]

        return await self.get_response(request)

    async def _verify_token(self, token: str) -> dict[str, Any] | None:
        """Verify a Clerk JWT and return claims, or None on failure."""
        try:
            client = _get_jwks_client()
            signing_key = client.get_signing_key_from_jwt(token)
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                options={"verify_aud": False},
            )
            return claims
        except jwt.ExpiredSignatureError:
            logger.debug("Clerk JWT expired")
            return None
        except jwt.InvalidTokenError as exc:
            logger.debug("Clerk JWT invalid: %s", exc)
            return None
        except Exception as exc:
            logger.warning("Clerk JWT verification error: %s", exc)
            return None
