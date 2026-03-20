from django_matt import MattAPI

from apps.payments.schemas import PaymentIntentSchema

from .payment_controller import PaymentController


def register_payment_routes(api: MattAPI) -> None:
    api.post(
        "payments/create-intent",
        response_model=PaymentIntentSchema,
        tags=["Payments"],
    )(PaymentController.create_payment_intent)

    api.post(
        "payments/webhook",
        status_code=200,
        tags=["Payments"],
    )(PaymentController.webhook)
