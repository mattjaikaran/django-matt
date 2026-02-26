"""
Centrifugo JWT token generation.

Generates connection and subscription tokens that clients pass to
Centrifugo for authentication. Signs with the Centrifugo secret
(DJANGO_MATT_CENTRIFUGO["SECRET"]) using HS256.

No external dependencies — reuses django_matt.auth.jwt_builtin.
"""

from __future__ import annotations

from django_matt.auth.jwt_builtin import encode_jwt
from django_matt.websockets.centrifugo.config import get_centrifugo_config


def generate_connection_token(
    user_id: str,
    expire_in: int | None = None,
    info: dict | None = None,
) -> str:
    """
    Generate a Centrifugo connection JWT.

    The client passes this token when connecting to Centrifugo's
    WebSocket endpoint (``connection/websocket``).

    Args:
        user_id: The authenticated user's ID (becomes ``sub`` claim).
        expire_in: Token lifetime in seconds. Defaults to
            ``CentrifugoConfig.token_expire``.
        info: Optional extra metadata included in the ``info`` claim.

    Returns:
        Signed JWT string.
    """
    cfg = get_centrifugo_config()
    payload: dict = {"sub": user_id}
    if info:
        payload["info"] = info

    return encode_jwt(
        payload=payload,
        secret=cfg.secret,
        algorithm="HS256",
        expires_in=expire_in if expire_in is not None else cfg.token_expire,
    )


def generate_subscription_token(
    user_id: str,
    channel: str,
    expire_in: int | None = None,
) -> str:
    """
    Generate a Centrifugo subscription JWT for private channels.

    Args:
        user_id: The authenticated user's ID (``sub`` claim).
        channel: The private channel name (``channel`` claim).
        expire_in: Token lifetime in seconds. Defaults to
            ``CentrifugoConfig.token_expire``.

    Returns:
        Signed JWT string.
    """
    cfg = get_centrifugo_config()
    payload: dict = {"sub": user_id, "channel": channel}

    return encode_jwt(
        payload=payload,
        secret=cfg.secret,
        algorithm="HS256",
        expires_in=expire_in if expire_in is not None else cfg.token_expire,
    )
