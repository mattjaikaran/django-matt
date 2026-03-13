from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field


class SubscriptionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    stripe_subscription_id: str | None
    plan: str
    status: str
    current_period_start: datetime | None
    current_period_end: datetime | None
    api_calls_limit: int
    api_calls_used: int
    created_at: datetime

    @computed_field
    @property
    def usage_percentage(self) -> float:
        if self.api_calls_limit == 0:
            return 0.0
        return round((self.api_calls_used / self.api_calls_limit) * 100, 2)


class SubscriptionUpdateSchema(BaseModel):
    plan: str | None = None


class InvoiceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    stripe_invoice_id: str | None
    amount: float
    currency: str
    status: str
    period_start: str
    period_end: str
    paid_at: datetime | None
    created_at: datetime


class UsageSchema(BaseModel):
    api_calls_used: int
    api_calls_limit: int
    usage_percentage: float
    period_start: datetime | None
    period_end: datetime | None
