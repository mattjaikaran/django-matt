from django.db import models

from apps.core.models import BaseModel


class Experience(BaseModel):
    company = models.CharField(max_length=255)
    role = models.CharField(max_length=255)
    company_url = models.URLField(blank=True, null=True)
    location = models.CharField(max_length=100, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    description = models.TextField()
    tech_used = models.JSONField(default=list)
    order = models.IntegerField(default=0)

    class Meta:
        db_table = "experience"
        ordering = ["order", "-start_date"]

    def __str__(self) -> str:
        return f"{self.role} at {self.company}"
