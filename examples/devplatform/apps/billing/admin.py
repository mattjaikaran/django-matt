from django.contrib import admin

from apps.billing.models import Invoice, Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["id", "organization", "plan", "status", "api_calls_used", "api_calls_limit", "created_at"]
    list_filter = ["plan", "status"]
    search_fields = ["organization__name"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["id", "organization", "amount", "currency", "status", "period_start", "period_end", "paid_at"]
    list_filter = ["status", "currency"]
    search_fields = ["organization__name", "stripe_invoice_id"]
    readonly_fields = ["id", "created_at", "updated_at"]
