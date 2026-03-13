import uuid

from django.db import models

from apps.core.models import BaseModel
from apps.organizations.models import Organization


class Invoice(BaseModel):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("open", "Open"),
        ("paid", "Paid"),
        ("void", "Void"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="invoices",
    )
    stripe_invoice_id = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="usd")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="draft")
    period_start = models.DateField()
    period_end = models.DateField()
    paid_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ["-period_end"]

    def __str__(self) -> str:
        return f"Invoice {self.amount} {self.currency} - {self.status}"
