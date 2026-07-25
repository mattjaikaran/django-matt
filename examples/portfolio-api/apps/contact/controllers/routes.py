from django_matt import DjangoMattAPI

from apps.contact.schemas import ContactMessageSchema

from .contact_controller import ContactController


def register_contact_routes(api: DjangoMattAPI) -> None:
    api.post("contact", response_model=ContactMessageSchema, status_code=201, tags=["Contact"])(
        ContactController.submit_contact
    )

    api.get("contact", tags=["Contact"])(ContactController.list_messages)

    api.patch("contact/<str:msg_id>/read", response_model=ContactMessageSchema, tags=["Contact"])(
        ContactController.mark_read
    )
