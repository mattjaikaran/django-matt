from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model

logger = logging.getLogger("django_matt.plugins.clerk")


async def sync_clerk_user(claims: dict[str, Any]) -> Any:
    """Sync a Clerk user to the Django User model.

    Uses the Clerk `sub` claim as the username. Updates email and name
    fields from JWT claims on each authentication.

    Returns the Django User instance.
    """
    User = get_user_model()  # noqa: N806
    clerk_id = claims.get("sub", "")
    email = claims.get("email", "") or claims.get("primary_email_address", "")
    first_name = claims.get("first_name", "") or ""
    last_name = claims.get("last_name", "") or ""

    user, created = await sync_to_async(User.objects.update_or_create)(
        username=clerk_id,
        defaults={
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
        },
    )

    if created:
        logger.info("Created Django user for Clerk ID: %s", clerk_id)
    else:
        logger.debug("Updated Django user for Clerk ID: %s", clerk_id)

    return user


async def sync_clerk_user_from_webhook(
    event_data: dict[str, Any],
) -> Any | None:
    """Sync a Clerk user from a webhook payload.

    Handles `user.created` and `user.updated` events.
    Returns the Django User instance or None if the event is a deletion.
    """
    event_type = event_data.get("type", "")
    user_data = event_data.get("data", {})
    clerk_id = user_data.get("id", "")

    if not clerk_id:
        logger.warning("Clerk webhook missing user ID")
        return None

    User = get_user_model()  # noqa: N806

    if event_type == "user.deleted":
        try:
            user = await sync_to_async(User.objects.get)(username=clerk_id)
            user.is_active = False
            await sync_to_async(user.save)(update_fields=["is_active"])
            logger.info("Deactivated user for Clerk ID: %s", clerk_id)
        except User.DoesNotExist:
            logger.debug("No user to deactivate for Clerk ID: %s", clerk_id)
        return None

    # user.created or user.updated
    email_addresses = user_data.get("email_addresses", [])
    primary_email = ""
    primary_email_id = user_data.get("primary_email_address_id")
    for addr in email_addresses:
        if addr.get("id") == primary_email_id:
            primary_email = addr.get("email_address", "")
            break
    if not primary_email and email_addresses:
        primary_email = email_addresses[0].get("email_address", "")

    first_name = user_data.get("first_name", "") or ""
    last_name = user_data.get("last_name", "") or ""

    user, created = await sync_to_async(User.objects.update_or_create)(
        username=clerk_id,
        defaults={
            "email": primary_email,
            "first_name": first_name,
            "last_name": last_name,
            "is_active": True,
        },
    )

    action = "Created" if created else "Updated"
    logger.info("%s Django user from Clerk webhook: %s", action, clerk_id)
    return user
