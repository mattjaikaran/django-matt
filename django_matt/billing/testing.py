"""
Mock event factories for billing webhook testing.

These helpers produce valid signed payloads that pass the real provider
signature-verification logic, so tests can exercise the full code path
without hitting live APIs or needing real secrets.

Usage::

    from django_matt.billing.testing import (
        mock_stripe_event,
        mock_paypal_event,
        mock_polar_event,
    )

    # Stripe
    payload, sig_header = mock_stripe_event(
        "customer.subscription.created",
        data={"id": "sub_123", "status": "active"},
        secret="whsec_test_secret",
    )
    request.META["HTTP_STRIPE_SIGNATURE"] = sig_header
    request._body = payload

    # Polar
    payload, sig_header = mock_polar_event(
        "subscription.created",
        data={"id": "sub_456"},
        secret="polar_test_secret",
    )

    # PayPal
    payload, headers = mock_paypal_event(
        "BILLING.SUBSCRIPTION.CREATED",
        data={"id": "I-PAYPAL123"},
    )
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
import uuid
import zlib

import orjson

__all__ = [
    "mock_stripe_event",
    "mock_paypal_event",
    "mock_polar_event",
]


def mock_stripe_event(
    event_type: str,
    data: dict,
    secret: str = "whsec_test_secret",
    event_id: str | None = None,
) -> tuple[bytes, str]:
    """
    Produce a Stripe webhook payload + signature header.

    The signature format matches what StripeProvider.verify_webhook() expects:
    ``t={timestamp},v1={hmac_sha256_hex}``

    Returns:
        (payload_bytes, stripe-signature_header_value)
    """
    timestamp = int(time.time())
    evt_id = event_id or f"evt_{uuid.uuid4().hex[:16]}"

    event_body = {
        "id": evt_id,
        "type": event_type,
        "object": "event",
        "created": timestamp,
        "data": {"object": data},
    }
    payload = orjson.dumps(event_body)

    # Stripe HMAC: sign "{timestamp}.{payload_str}"
    signed_payload = f"{timestamp}.".encode() + payload
    signature = hmac.new(
        secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()

    sig_header = f"t={timestamp},v1={signature}"
    return payload, sig_header


def mock_paypal_event(
    event_type: str,
    data: dict,
    client_secret: str = "test_client_secret",
    webhook_id: str = "test_webhook_id",
    event_id: str | None = None,
) -> tuple[bytes, dict[str, str]]:
    """
    Produce a PayPal webhook payload + verification headers dict.

    The headers dict matches what PayPalProvider.verify_webhook() expects:
    - PAYPAL-TRANSMISSION-ID
    - PAYPAL-TRANSMISSION-TIME
    - PAYPAL-TRANSMISSION-SIG  (base64-encoded HMAC-SHA256)

    Returns:
        (payload_bytes, headers_dict)
    """
    transmission_id = event_id or str(uuid.uuid4())
    transmission_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    event_body = {
        "id": transmission_id,
        "event_type": event_type,
        "create_time": transmission_time,
        "resource": data,
    }
    payload = orjson.dumps(event_body)

    # Build signature message: transmission_id|transmission_time|webhook_id|crc32(body)
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    message = f"{transmission_id}|{transmission_time}|{webhook_id}|{crc}"

    sig_bytes = hmac.new(
        client_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    sig_b64 = base64.b64encode(sig_bytes).decode("ascii")

    headers = {
        "PAYPAL-TRANSMISSION-ID": transmission_id,
        "PAYPAL-TRANSMISSION-TIME": transmission_time,
        "PAYPAL-TRANSMISSION-SIG": sig_b64,
    }
    return payload, headers


def mock_polar_event(
    event_type: str,
    data: dict,
    secret: str = "test_webhook_secret",
    event_id: str | None = None,
) -> tuple[bytes, str]:
    """
    Produce a Polar webhook payload + signature header.

    The signature format matches what PolarProvider.verify_webhook() expects:
    ``sha256={hmac_sha256_hex}``

    Returns:
        (payload_bytes, x-polar-signature_header_value)
    """
    evt_id = event_id or str(uuid.uuid4())

    event_body = {
        "id": evt_id,
        "type": event_type,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data": data,
    }
    payload = orjson.dumps(event_body)

    signature = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    sig_header = f"sha256={signature}"
    return payload, sig_header
