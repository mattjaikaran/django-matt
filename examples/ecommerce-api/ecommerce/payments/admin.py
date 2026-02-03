"""Django admin configuration for payments app."""

from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action, display

from ecommerce.payments.models import Payment, PaymentWebhookLog, Refund


class RefundInline(TabularInline):
    """Inline for refunds."""

    model = Refund
    extra = 0
    readonly_fields = [
        "amount",
        "reason",
        "status",
        "stripe_refund_id",
        "refunded_at",
        "created_by",
    ]
    can_delete = False


@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    """Admin for Payment model."""

    list_display = [
        "id_short",
        "order_number",
        "status_display",
        "amount_display",
        "payment_method",
        "card_display",
        "paid_at",
        "created_at",
    ]
    list_filter = ["status", "payment_method", "created_at"]
    search_fields = [
        "order__order_number",
        "stripe_payment_intent_id",
        "stripe_charge_id",
    ]
    readonly_fields = [
        "order",
        "stripe_payment_intent_id",
        "stripe_charge_id",
        "stripe_customer_id",
        "card_brand",
        "card_last4",
        "card_exp_month",
        "card_exp_year",
        "error_code",
        "error_message",
        "created_at",
        "updated_at",
        "paid_at",
    ]
    inlines = [RefundInline]
    date_hierarchy = "created_at"
    fieldsets = [
        (
            "Order",
            {
                "fields": [
                    "order",
                ]
            },
        ),
        (
            "Payment Details",
            {
                "fields": [
                    "status",
                    "payment_method",
                    "amount",
                    "currency",
                ]
            },
        ),
        (
            "Stripe",
            {
                "fields": [
                    "stripe_payment_intent_id",
                    "stripe_charge_id",
                    "stripe_customer_id",
                ]
            },
        ),
        (
            "Card Details",
            {
                "fields": [
                    "card_brand",
                    "card_last4",
                    "card_exp_month",
                    "card_exp_year",
                ]
            },
        ),
        (
            "Errors",
            {
                "fields": [
                    "error_code",
                    "error_message",
                ],
                "classes": ["collapse"],
            },
        ),
        (
            "Metadata",
            {
                "fields": [
                    "metadata",
                ],
                "classes": ["collapse"],
            },
        ),
        (
            "Timestamps",
            {
                "fields": [
                    "created_at",
                    "updated_at",
                    "paid_at",
                ]
            },
        ),
    ]

    @display(description="ID")
    def id_short(self, obj):
        return str(obj.id)[:8]

    @display(description="Order")
    def order_number(self, obj):
        return obj.order.order_number

    @display(description="Status")
    def status_display(self, obj):
        colors = {
            "pending": "gray",
            "processing": "orange",
            "succeeded": "green",
            "failed": "red",
            "cancelled": "gray",
            "refunded": "purple",
            "partially_refunded": "purple",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    @display(description="Amount")
    def amount_display(self, obj):
        return f"${obj.amount} {obj.currency}"

    @display(description="Card")
    def card_display(self, obj):
        if obj.card_brand and obj.card_last4:
            return f"{obj.card_brand} ****{obj.card_last4}"
        return "-"


@admin.register(Refund)
class RefundAdmin(ModelAdmin):
    """Admin for Refund model."""

    list_display = [
        "id_short",
        "order_number",
        "status_display",
        "amount_display",
        "reason",
        "created_at",
    ]
    list_filter = ["status", "reason", "created_at"]
    search_fields = ["payment__order__order_number", "stripe_refund_id"]
    readonly_fields = [
        "payment",
        "order",
        "stripe_refund_id",
        "error_code",
        "error_message",
        "created_at",
        "updated_at",
        "refunded_at",
        "created_by",
    ]
    date_hierarchy = "created_at"

    @display(description="ID")
    def id_short(self, obj):
        return str(obj.id)[:8]

    @display(description="Order")
    def order_number(self, obj):
        return obj.order.order_number

    @display(description="Status")
    def status_display(self, obj):
        colors = {
            "pending": "orange",
            "succeeded": "green",
            "failed": "red",
            "cancelled": "gray",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_status_display(),
        )

    @display(description="Amount")
    def amount_display(self, obj):
        return f"${obj.amount}"


@admin.register(PaymentWebhookLog)
class PaymentWebhookLogAdmin(ModelAdmin):
    """Admin for PaymentWebhookLog model."""

    list_display = [
        "event_id_short",
        "provider",
        "event_type",
        "processed_display",
        "received_at",
    ]
    list_filter = ["provider", "event_type", "processed", "received_at"]
    search_fields = ["event_id", "event_type"]
    readonly_fields = [
        "provider",
        "event_type",
        "event_id",
        "payload",
        "processed",
        "error_message",
        "received_at",
        "processed_at",
    ]
    date_hierarchy = "received_at"

    @display(description="Event ID")
    def event_id_short(self, obj):
        return obj.event_id[:20] + "..." if len(obj.event_id) > 20 else obj.event_id

    @display(description="Processed", boolean=True)
    def processed_display(self, obj):
        return obj.processed
