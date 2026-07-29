"""Contact controller — public submit, admin read."""

from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import PermissionAPIError
from django_matt.core.router import get, post

from {{ project_name }}_app.contact.models import ContactMessage
from {{ project_name }}_app.contact.schemas import ContactCreateSchema, ContactMessageSchema


class ContactController(APIController):
    prefix = "/contact"
    tags = ["Contact"]

    @post("/")
    async def submit_contact(self, request, body: ContactCreateSchema) -> dict:
        contact = await ContactMessage.objects.acreate(**body.model_dump())
        return {"success": True, "id": str(contact.id)}

    @get("/")
    @jwt_required
    async def list_messages(self, request) -> list[ContactMessageSchema]:
        if not request.user.is_staff:
            raise PermissionAPIError("Only staff can view contact messages.")
        return [
            ContactMessageSchema.model_validate(m)
            async for m in ContactMessage.objects.all()
        ]
