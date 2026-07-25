from django_matt import DjangoMattAPI

from apps.billing.schemas import SubscriptionSchema

from .billing_controller import BillingController


def register_billing_routes(api: DjangoMattAPI) -> None:
    api.get(
        "organizations/<str:org_id>/billing/subscription",
        response_model=SubscriptionSchema,
        tags=["Billing"],
    )(BillingController.get_subscription)

    api.patch(
        "organizations/<str:org_id>/billing/subscription",
        response_model=SubscriptionSchema,
        tags=["Billing"],
    )(BillingController.update_subscription)

    api.get(
        "organizations/<str:org_id>/billing/usage",
        tags=["Billing"],
    )(BillingController.get_usage)

    api.get(
        "organizations/<str:org_id>/billing/invoices",
        tags=["Billing"],
    )(BillingController.list_invoices)
