"""
Centrifugo backend for django-matt WebSockets.

Provides:
- CentrifugoConfig / get_centrifugo_config
- CentrifugoClient / get_centrifugo_client / CentrifugoAPIError
- generate_connection_token / generate_subscription_token
- Proxy views: CentrifugoConnectProxy, CentrifugoSubscribeProxy,
  CentrifugoPublishProxy, CentrifugoRPCProxy, get_centrifugo_urls

Requires: uv add 'django-matt[centrifugo]'  (pulls in httpx)
"""

from django_matt.websockets.centrifugo.client import (
    CentrifugoAPIError,
    CentrifugoClient,
    get_centrifugo_client,
)
from django_matt.websockets.centrifugo.config import (
    CentrifugoConfig,
    get_centrifugo_config,
)
from django_matt.websockets.centrifugo.proxy import (
    CentrifugoConnectProxy,
    CentrifugoPublishProxy,
    CentrifugoRPCProxy,
    CentrifugoSubscribeProxy,
    get_centrifugo_urls,
)
from django_matt.websockets.centrifugo.tokens import (
    generate_connection_token,
    generate_subscription_token,
)

__all__ = [
    # Config
    "CentrifugoConfig",
    "get_centrifugo_config",
    # Client
    "CentrifugoClient",
    "CentrifugoAPIError",
    "get_centrifugo_client",
    # Tokens
    "generate_connection_token",
    "generate_subscription_token",
    # Proxy views
    "CentrifugoConnectProxy",
    "CentrifugoSubscribeProxy",
    "CentrifugoPublishProxy",
    "CentrifugoRPCProxy",
    "get_centrifugo_urls",
]
