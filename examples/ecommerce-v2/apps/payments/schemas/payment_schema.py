from pydantic import BaseModel


class CreatePaymentIntentSchema(BaseModel):
    order_id: str


class PaymentIntentSchema(BaseModel):
    client_secret: str
    payment_intent_id: str
    amount: int
    currency: str = "usd"


class WebhookEventSchema(BaseModel):
    type: str
    data: dict
