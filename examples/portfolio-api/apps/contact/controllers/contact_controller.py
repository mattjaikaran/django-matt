import logging

from django.conf import settings
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError

from apps.contact.models import ContactMessage
from apps.contact.schemas import ContactCreateSchema, ContactMessageSchema

logger = logging.getLogger(__name__)


def _serialize(msg: ContactMessage) -> dict:
    return ContactMessageSchema(
        id=str(msg.id),
        name=msg.name,
        email=msg.email,
        subject=msg.subject,
        message=msg.message,
        is_read=msg.is_read,
        created_at=msg.created_at,
        updated_at=msg.updated_at,
    ).model_dump(mode="json")


async def _send_notification(msg: ContactMessage) -> None:
    api_key = getattr(settings, "RESEND_API_KEY", "")
    if not api_key:
        logger.info("RESEND_API_KEY not set — skipping email notification")
        return

    try:
        import resend

        resend.api_key = api_key
        subject = msg.subject or "New contact form message"
        body = (
            f"<h2>New message from {msg.name}</h2>"
            f"<p><strong>From:</strong> {msg.name} &lt;{msg.email}&gt;</p>"
            f"<p><strong>Subject:</strong> {subject}</p>"
            f"<hr>"
            f"<p>{msg.message.replace(chr(10), '<br>')}</p>"
        )
        resend.Emails.send(
            {
                "from": settings.CONTACT_FROM_EMAIL,
                "to": [settings.CONTACT_TO_EMAIL],
                "reply_to": msg.email,
                "subject": f"[Portfolio] {subject}",
                "html": body,
            }
        )
        logger.info("Contact notification sent for message %s", msg.id)
    except Exception:
        logger.exception("Failed to send Resend notification for message %s", msg.id)


class ContactController(APIController):
    tags = ["Contact"]

    @staticmethod
    async def submit_contact(request, body: ContactCreateSchema) -> dict:
        msg = await ContactMessage.objects.acreate(
            name=body.name,
            email=body.email,
            subject=body.subject or "",
            message=body.message,
        )
        await _send_notification(msg)
        return _serialize(msg)

    @staticmethod
    @jwt_required
    async def list_messages(request) -> dict:
        items = []
        async for msg in ContactMessage.objects.all():
            items.append(_serialize(msg))
        return {"items": items, "total": len(items)}

    @staticmethod
    @jwt_required
    async def mark_read(request, msg_id: str) -> dict:
        msg = await ContactMessage.objects.filter(id=msg_id).afirst()
        if not msg:
            raise NotFoundAPIError("Message not found")
        msg.is_read = True
        await msg.asave(update_fields=["is_read", "updated_at"])
        return _serialize(msg)
